import re
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from scipy import signal

from music_lab_ui.artifact_metrics import (
    attack_sharpness_db,
    band_stereo_correlation,
    hf_cliff_db_per_octave,
    measure_artifacts,
    noise_floor,
    rms_envelope_db,
    spectral_rolloff_hz,
    tonal_peaks,
)
from music_lab_ui.i18n import get_translator

t = get_translator()

SAMPLE_RATE = 44_100


def clicks(sharp: bool, seconds: float = 4.0) -> np.ndarray:
    """Percussive hits, either with instant attacks or deliberately smeared ones."""
    length = int(seconds * SAMPLE_RATE)
    out = np.zeros(length, dtype=np.float32)
    rng = np.random.default_rng(7)
    hit = rng.normal(0, 0.3, int(0.05 * SAMPLE_RATE)).astype(np.float32)
    hit *= np.exp(-np.linspace(0, 12, hit.size, dtype=np.float32))
    if not sharp:
        # A long attack ramp is exactly what transient smearing does.
        ramp = np.linspace(0, 1, int(0.04 * SAMPLE_RATE), dtype=np.float32)
        hit = np.convolve(hit, ramp / ramp.sum())[: hit.size].astype(np.float32)
    for start in range(0, length - hit.size, int(0.5 * SAMPLE_RATE)):
        out[start : start + hit.size] += hit
    return out


def test_smearing_lowers_attack_sharpness() -> None:
    sharp = attack_sharpness_db(rms_envelope_db(clicks(True), SAMPLE_RATE))
    smeared = attack_sharpness_db(rms_envelope_db(clicks(False), SAMPLE_RATE))

    assert sharp > smeared


def test_rolloff_tracks_where_the_energy_actually_is() -> None:
    frequencies = np.array([0.0, 1_000.0, 2_000.0, 3_000.0, 4_000.0])

    # Almost all energy sits at 1 kHz, so the 95% point is reached right there.
    low_heavy = np.array([0.0, 10.0, 0.1, 0.0, 0.0])
    assert spectral_rolloff_hz(low_heavy, frequencies, 0.95) == pytest.approx(1_000.0)

    # Spread evenly, the top band is needed to cross 95%.
    spread = np.array([0.0, 1.0, 1.0, 1.0, 1.0])
    assert spectral_rolloff_hz(spread, frequencies, 0.95) == pytest.approx(4_000.0)

    # A brighter spectrum must roll off higher than a dark one.
    dark = np.array([0.0, 8.0, 2.0, 0.2, 0.05])
    bright = np.array([0.0, 2.0, 2.0, 3.0, 3.0])
    assert spectral_rolloff_hz(bright, frequencies) > spectral_rolloff_hz(dark, frequencies)


def test_hard_lowpass_reads_as_a_steep_cliff() -> None:
    frequencies = np.geomspace(1_000, 20_000, 200)
    gentle = -6.0 * np.log2(frequencies / 1_000)
    wall = gentle.copy()
    wall[frequencies > 16_000] -= 80.0

    assert hf_cliff_db_per_octave(wall, frequencies) < hf_cliff_db_per_octave(gentle, frequencies)
    assert hf_cliff_db_per_octave(gentle, frequencies) == pytest.approx(-6.0, abs=0.5)


def test_noise_floor_flatness_separates_white_noise_from_a_tone() -> None:
    frequencies = np.linspace(0, 22_050, 512)
    rng = np.random.default_rng(3)
    white = np.abs(rng.normal(0.01, 0.001, (512, 40)))
    tonal = np.full((512, 40), 1e-5)
    tonal[100, :] = 0.5

    _, white_flatness = noise_floor(white, frequencies)
    _, tonal_flatness = noise_floor(tonal, frequencies)

    assert white_flatness > 0.5
    assert tonal_flatness < white_flatness


def test_noise_floor_level_uses_the_quiet_frames_not_the_loud_ones() -> None:
    frequencies = np.linspace(0, 22_050, 128)
    magnitude = np.full((128, 100), 1e-4)
    magnitude[:, :50] = 1.0  # loud half must not drag the floor up

    level, _ = noise_floor(magnitude, frequencies)

    assert level < -60.0


def whistling_noise(
    whistles_hz: tuple[float, ...], seconds: float = 4.0, level: float = 0.25
) -> np.ndarray:
    """Broadband noise with steady sine tones planted on top of it."""
    rng = np.random.default_rng(19)
    length = int(seconds * SAMPLE_RATE)
    out = rng.normal(0, 0.1, length)
    time = np.arange(length) / SAMPLE_RATE
    for frequency in whistles_hz:
        out += level * np.sin(2 * np.pi * frequency * time)
    return out.astype(np.float32)


def averaged_spectrum_db(mono: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    frequencies, _, spectrum = signal.stft(
        mono, fs=SAMPLE_RATE, nperseg=4096, scaling="spectrum"
    )
    power = np.mean(np.square(np.abs(spectrum), dtype=np.float64), axis=1)
    return 20.0 * np.log10(np.maximum(np.sqrt(power), 1e-10)), frequencies


def test_tonal_peaks_locate_planted_whistles() -> None:
    spectrum_db, frequencies = averaged_spectrum_db(whistling_noise((8_000.0, 5_200.0)))

    peaks = tonal_peaks(spectrum_db, frequencies)

    found = sorted(peak.frequency_hz for peak in peaks)
    assert len(found) == 2
    assert found[0] == pytest.approx(5_200.0, abs=100.0)
    assert found[1] == pytest.approx(8_000.0, abs=100.0)
    assert all(peak.prominence_db > 4.0 for peak in peaks)


def test_tonal_peaks_are_sorted_by_how_far_they_stick_out() -> None:
    rng = np.random.default_rng(23)
    length = int(4.0 * SAMPLE_RATE)
    time = np.arange(length) / SAMPLE_RATE
    quiet_then_loud = (
        rng.normal(0, 0.1, length)
        + 0.05 * np.sin(2 * np.pi * 6_000.0 * time)
        + 0.40 * np.sin(2 * np.pi * 9_000.0 * time)
    ).astype(np.float32)
    spectrum_db, frequencies = averaged_spectrum_db(quiet_then_loud)

    peaks = tonal_peaks(spectrum_db, frequencies)

    assert peaks[0].frequency_hz == pytest.approx(9_000.0, abs=100.0)
    assert peaks[0].prominence_db > peaks[-1].prominence_db


def test_broadband_noise_has_no_tonal_peaks() -> None:
    spectrum_db, frequencies = averaged_spectrum_db(whistling_noise(()))

    assert tonal_peaks(spectrum_db, frequencies) == ()


def test_a_real_instrument_partial_does_not_count_as_a_whistle() -> None:
    """Vibrato smears a partial across bins, so it stops standing out."""
    length = int(4.0 * SAMPLE_RATE)
    time = np.arange(length) / SAMPLE_RATE
    rng = np.random.default_rng(29)
    wobbling = (
        rng.normal(0, 0.1, length)
        + 0.25 * np.sin(2 * np.pi * 8_000.0 * time + 40.0 * np.sin(2 * np.pi * 5.0 * time))
    ).astype(np.float32)
    steady = whistling_noise((8_000.0,))

    wobbling_peaks = tonal_peaks(*averaged_spectrum_db(wobbling))
    steady_peaks = tonal_peaks(*averaged_spectrum_db(steady))

    assert steady_peaks[0].prominence_db > max(
        (peak.prominence_db for peak in wobbling_peaks), default=0.0
    )


def test_band_stereo_correlation_is_none_for_mono() -> None:
    mono = np.zeros((SAMPLE_RATE, 1), dtype=np.float32)

    assert band_stereo_correlation(mono, SAMPLE_RATE, (100.0, 1_000.0)) is None


def test_band_stereo_correlation_detects_a_decorrelated_top_end() -> None:
    rng = np.random.default_rng(11)
    length = SAMPLE_RATE * 2
    common = rng.normal(0, 0.1, length)
    sos = signal.butter(4, 1_000 / (SAMPLE_RATE / 2), btype="lowpass", output="sos")
    low = signal.sosfiltfilt(sos, common)
    stereo = np.stack(
        [low + rng.normal(0, 0.05, length), low + rng.normal(0, 0.05, length)],
        axis=1,
    ).astype(np.float32)

    correlated = band_stereo_correlation(stereo, SAMPLE_RATE, (40.0, 500.0))
    decorrelated = band_stereo_correlation(stereo, SAMPLE_RATE, (5_000.0, 16_000.0))

    assert correlated > 0.8
    assert decorrelated < 0.3


def test_measure_artifacts_reads_a_real_file(tmp_path: Path) -> None:
    path = tmp_path / "probe.wav"
    sf.write(path, np.stack([clicks(True), clicks(True)], axis=1), SAMPLE_RATE)

    metrics = measure_artifacts(path)

    assert metrics.name == "probe.wav"
    assert metrics.channels == 2
    assert metrics.duration_seconds == pytest.approx(4.0, abs=0.1)
    assert metrics.attack_sharpness_db > 0
    assert metrics.stereo_correlation_low is not None


def service_with_stub(tmp_path: Path):
    from music_lab_ui.config import LabPaths
    from music_lab_ui.history import HistoryStore
    from music_lab_ui.ui_service import AnalysisService

    def stub(path: Path):
        return measure_artifacts(path)

    return AnalysisService(
        paths=LabPaths.from_root(tmp_path),
        history=HistoryStore(
            tmp_path / "data" / "history.sqlite3", tmp_path / "data" / "runs"
        ),
        artifact_measurer=stub,
    )


def test_batch_measures_references_without_a_run(tmp_path: Path) -> None:
    service = service_with_stub(tmp_path)
    reference = tmp_path / "reference.wav"
    sf.write(reference, np.stack([clicks(True), clicks(True)], axis=1), SAMPLE_RATE)

    results = service.measure_artifacts_batch(None, [str(reference)])

    assert [item.name for item in results] == ["reference.wav"]


def test_batch_needs_something_to_measure(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=re.escape(t("error.no_reference"))):
        service_with_stub(tmp_path).measure_artifacts_batch(None, [])


def test_artifact_rows_mark_mono_files(tmp_path: Path) -> None:
    from music_lab_ui.ui_presenters import artifact_rows

    mono = tmp_path / "mono.wav"
    sf.write(mono, clicks(True), SAMPLE_RATE)

    rows = artifact_rows([measure_artifacts(mono)])

    assert rows[0][0] == "mono.wav"
    assert rows[0][6] == t("unit.mono")
    assert rows[0][7] == t("unit.mono")
