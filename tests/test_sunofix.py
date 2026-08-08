"""What SunoFix promises, asserted rather than trusted.

Two of these matter more than the rest: a preset must never reach into the
repair layer, and the chain must not change the level. Both are load-bearing
for reading an A/B afterwards.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from scipy import signal

from music_lab_ui.artifact_metrics import ArtifactMetrics, TonalPeak, measure_artifacts
from music_lab_ui.sunofix import (
    PRESETS,
    CleanupSettings,
    RepairSettings,
    SunoFixSettings,
    WarmthSettings,
    apply_level_policy,
    de_artifact,
    fix_stereo,
    fix_transients,
    hf_cleanup,
    measure_array,
    preset_settings,
    process_audio,
    recommend,
    recommended_repair,
    restore_air,
    run,
    tone_tilt,
    true_peak_dbtp,
    warmth,
)

SAMPLE_RATE = 44_100


def stereo_noise(seconds: float = 3.0, level: float = 0.1, seed: int = 5) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = int(seconds * SAMPLE_RATE)
    return rng.normal(0, level, (length, 2))


def with_whistle(audio: np.ndarray, frequency: float, level: float = 0.25) -> np.ndarray:
    time = np.arange(audio.shape[0]) / SAMPLE_RATE
    return audio + (level * np.sin(2 * np.pi * frequency * time))[:, None]


def lowpassed(audio: np.ndarray, cutoff_hz: float) -> np.ndarray:
    sos = signal.butter(12, cutoff_hz / (SAMPLE_RATE / 2), btype="lowpass", output="sos")
    return signal.sosfiltfilt(sos, audio, axis=0)


def band_energy_db(audio: np.ndarray, low_hz: float, high_hz: float) -> float:
    sos = signal.butter(
        6,
        [low_hz / (SAMPLE_RATE / 2), min(high_hz, SAMPLE_RATE / 2 * 0.99) / (SAMPLE_RATE / 2)],
        btype="bandpass",
        output="sos",
    )
    band = signal.sosfiltfilt(sos, audio, axis=0)
    return float(20 * np.log10(np.sqrt(np.mean(np.square(band))) + 1e-12))


def rms_db(audio: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(np.square(audio))) + 1e-12))


def metrics_of(audio: np.ndarray, name: str = "probe") -> ArtifactMetrics:
    return measure_array(audio, SAMPLE_RATE, name)


# ---- the layer boundary --------------------------------------------------


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_no_preset_can_touch_the_repair_layer(name: str) -> None:
    """The measurement drives the repair. A taste control never may."""
    assert preset_settings(name).repair == RepairSettings()


def test_an_unknown_preset_falls_back_to_repair_only() -> None:
    settings = preset_settings("no_such_preset")

    assert settings.preset == "repair_only"
    assert settings.warmth.enabled is False


def test_every_preset_keeps_mix_above_drive() -> None:
    """Blending back less than was driven in would only ever lose signal."""
    for warmth_settings, _ in PRESETS.values():
        assert warmth_settings.mix > warmth_settings.drive


def test_only_the_pass_that_opens_the_top_leaves_tone_flat() -> None:
    assert PRESETS["open_top"][0].tone == 0.0
    darker = [name for name, (w, _) in PRESETS.items() if w.tone < 0.0]
    assert set(darker) == set(PRESETS) - {"open_top"}


# ---- recommendations -----------------------------------------------------


def test_a_planted_whistle_recommends_de_artifact() -> None:
    metrics = metrics_of(with_whistle(stereo_noise(), 8_000.0))

    suggestions = {item.module: item for item in recommend(metrics)}

    assert suggestions["de_artifact"].recommended
    assert suggestions["de_artifact"].evidence["prominence_db"] > 4.0
    assert suggestions["de_artifact"].evidence["frequencies_hz"][0] == pytest.approx(
        8_000.0, abs=100.0
    )


def test_clean_noise_recommends_no_de_artifact() -> None:
    suggestions = {item.module: item for item in recommend(metrics_of(stereo_noise()))}

    assert not suggestions["de_artifact"].recommended


def test_a_lowpass_wall_recommends_restoring_air() -> None:
    metrics = metrics_of(lowpassed(stereo_noise(), 15_000.0))

    suggestions = {item.module: item for item in recommend(metrics)}

    assert suggestions["restore_air"].recommended
    assert suggestions["restore_air"].evidence["cutoff_hz"] < 17_500.0


def test_restoring_air_is_flagged_as_a_masking_risk() -> None:
    """It removes a signal detectors read easily; that is not the same as better."""
    risky = {item.module for item in recommend(metrics_of(stereo_noise())) if item.masking_risk}

    assert "restore_air" in risky
    assert "de_artifact" not in risky


def test_recommended_repair_mirrors_the_recommendations() -> None:
    metrics = metrics_of(with_whistle(lowpassed(stereo_noise(), 15_000.0), 8_000.0))

    repair = recommended_repair(metrics)

    assert repair.de_artifact
    assert repair.restore_air


# ---- repair modules ------------------------------------------------------


def test_de_artifact_pulls_the_planted_whistle_down() -> None:
    audio = with_whistle(stereo_noise(), 8_000.0)
    peaks = metrics_of(audio).tonal_peaks

    cleaned, report = de_artifact(audio, SAMPLE_RATE, peaks)

    before = max(peak.prominence_db for peak in peaks)
    after = max(
        (peak.prominence_db for peak in metrics_of(cleaned).tonal_peaks), default=0.0
    )
    assert report["notches"] >= 1
    assert after < before


def test_a_notch_cuts_by_the_depth_it_was_asked_for() -> None:
    """Forward-backward filtering runs the response twice; the design halves it."""
    time = np.arange(2 * SAMPLE_RATE) / SAMPLE_RATE
    tone = np.stack([np.sin(2 * np.pi * 8_000 * time)] * 2, axis=1)
    # Standing 11 dB proud, cut back to the 3 dB the module leaves behind: -8 dB.
    peaks = (TonalPeak(frequency_hz=8_000.0, prominence_db=11.0),)

    cut, _ = de_artifact(tone, SAMPLE_RATE, peaks)

    assert rms_db(cut) - rms_db(tone) == pytest.approx(-8.0, abs=0.7)


def test_the_deepest_notch_is_capped() -> None:
    """A ridge 40 dB proud still only gets a repair, not a hole."""
    time = np.arange(2 * SAMPLE_RATE) / SAMPLE_RATE
    tone = np.stack([np.sin(2 * np.pi * 8_000 * time)] * 2, axis=1)
    peaks = (TonalPeak(frequency_hz=8_000.0, prominence_db=40.0),)

    cut, _ = de_artifact(tone, SAMPLE_RATE, peaks)

    assert rms_db(cut) - rms_db(tone) == pytest.approx(-12.0, abs=1.0)


def test_de_artifact_leaves_material_without_ridges_alone() -> None:
    audio = stereo_noise()

    cleaned, report = de_artifact(audio, SAMPLE_RATE, ())

    assert report["notches"] == 0
    assert np.array_equal(cleaned, audio)


def test_restore_air_fills_the_band_above_the_wall() -> None:
    audio = lowpassed(stereo_noise(), 14_000.0)

    restored, report = restore_air(audio, SAMPLE_RATE, 14_000.0)

    assert report["cutoff_hz"] == 14_000.0
    assert band_energy_db(restored, 15_000.0, 19_000.0) > band_energy_db(
        audio, 15_000.0, 19_000.0
    )


def test_restore_air_keeps_the_new_band_below_the_source_band() -> None:
    """A rolloff that continues, not a new shelf announcing itself."""
    audio = lowpassed(stereo_noise(), 14_000.0)

    restored, _ = restore_air(audio, SAMPLE_RATE, 14_000.0)

    assert band_energy_db(restored, 15_000.0, 19_000.0) < band_energy_db(
        restored, 8_000.0, 13_000.0
    )


def test_restore_air_does_nothing_when_there_is_no_room_above_the_cutoff() -> None:
    audio = stereo_noise()

    restored, report = restore_air(audio, SAMPLE_RATE, 21_000.0)

    assert report["added_db"] == 0.0
    assert np.array_equal(restored, audio)


def test_fix_transients_sharpens_a_smeared_attack() -> None:
    length = int(2.0 * SAMPLE_RATE)
    rng = np.random.default_rng(13)
    hit = rng.normal(0, 0.3, int(0.05 * SAMPLE_RATE))
    hit *= np.exp(-np.linspace(0, 12, hit.size))
    ramp = np.linspace(0, 1, int(0.04 * SAMPLE_RATE))
    smeared = np.convolve(hit, ramp / ramp.sum())[: hit.size]
    track = np.zeros(length)
    for start in range(0, length - smeared.size, int(0.4 * SAMPLE_RATE)):
        track[start : start + smeared.size] += smeared
    audio = np.stack([track, track], axis=1)

    sharpened, report = fix_transients(audio, SAMPLE_RATE)

    assert report["peak_boost_db"] > 0.0
    assert metrics_of(sharpened).attack_sharpness_db > metrics_of(audio).attack_sharpness_db


def test_fix_stereo_narrows_a_phasey_top_end() -> None:
    rng = np.random.default_rng(17)
    length = int(2.0 * SAMPLE_RATE)
    common = rng.normal(0, 0.1, length)
    audio = np.stack([common, -common], axis=1)

    narrowed, report = fix_stereo(audio, SAMPLE_RATE, correlation_high=-0.9)

    assert report["side_gain_db"] < 0.0
    assert rms_db(narrowed[:, 0] - narrowed[:, 1]) < rms_db(audio[:, 0] - audio[:, 1])


def test_fix_stereo_leaves_an_ordinary_stereo_image_alone() -> None:
    """Most music sits in the acceptable window and must come back untouched."""
    audio = stereo_noise()

    out, report = fix_stereo(audio, SAMPLE_RATE, correlation_high=0.4)

    assert report["side_gain_db"] == 0.0
    assert np.array_equal(out, audio)


def test_the_stereo_correction_fades_to_nothing_at_the_thresholds() -> None:
    from music_lab_ui.sunofix import stereo_side_gain_db

    assert stereo_side_gain_db(-0.01) == pytest.approx(0.0, abs=0.1)
    assert stereo_side_gain_db(0.98) == pytest.approx(0.0, abs=1.5)
    assert stereo_side_gain_db(-0.9) < -4.0
    assert stereo_side_gain_db(1.0) > 2.0


def test_fix_stereo_widens_a_collapsed_top_end() -> None:
    rng = np.random.default_rng(31)
    length = int(2.0 * SAMPLE_RATE)
    common = rng.normal(0, 0.1, length)
    barely_stereo = np.stack(
        [common + rng.normal(0, 0.002, length), common + rng.normal(0, 0.002, length)],
        axis=1,
    )

    widened, report = fix_stereo(barely_stereo, SAMPLE_RATE, correlation_high=0.995)

    assert report["side_gain_db"] > 0.0
    assert rms_db(widened[:, 0] - widened[:, 1]) > rms_db(
        barely_stereo[:, 0] - barely_stereo[:, 1]
    )


def test_fix_stereo_leaves_mono_material_untouched() -> None:
    mono = stereo_noise()[:, :1]

    out, report = fix_stereo(mono, SAMPLE_RATE, correlation_high=None)

    assert report["side_gain_db"] == 0.0
    assert np.array_equal(out, mono)


# ---- taste modules -------------------------------------------------------


def test_hf_cleanup_pulls_quiet_debris_down_and_leaves_loud_material() -> None:
    quiet = stereo_noise(level=0.0006)
    loud = stereo_noise(level=0.2, seed=6)

    cleaned_quiet, report = hf_cleanup(quiet, SAMPLE_RATE, "strong")
    cleaned_loud, _ = hf_cleanup(loud, SAMPLE_RATE, "strong")

    assert report["deepest_cut_db"] > 0.0
    assert band_energy_db(cleaned_quiet, 9_000.0, 16_000.0) < band_energy_db(
        quiet, 9_000.0, 16_000.0
    ) - 1.0
    assert band_energy_db(cleaned_loud, 9_000.0, 16_000.0) == pytest.approx(
        band_energy_db(loud, 9_000.0, 16_000.0), abs=0.5
    )


def test_air_clean_works_higher_up_than_soft() -> None:
    from music_lab_ui.sunofix import CLEANUP_PROFILES

    assert CLEANUP_PROFILES["air_clean"][0] > CLEANUP_PROFILES["soft"][0]
    assert CLEANUP_PROFILES["strong"][3] > CLEANUP_PROFILES["soft"][3]


def test_warmth_is_a_colour_control_not_a_volume_control() -> None:
    audio = stereo_noise(level=0.2)

    subtle, _ = warmth(audio, SAMPLE_RATE, WarmthSettings(enabled=True, drive=0.08, mix=0.12))
    heavy, _ = warmth(audio, SAMPLE_RATE, WarmthSettings(enabled=True, drive=0.22, mix=0.30))

    assert rms_db(subtle) == pytest.approx(rms_db(audio), abs=0.5)
    assert rms_db(heavy) == pytest.approx(rms_db(audio), abs=0.5)


@pytest.mark.parametrize("character", ["tape", "tube", "console", "warm"])
def test_every_warmth_character_changes_the_signal(character: str) -> None:
    audio = stereo_noise(level=0.3)

    coloured, _ = warmth(
        audio,
        SAMPLE_RATE,
        WarmthSettings(enabled=True, character=character, drive=0.3, mix=0.5),
    )

    assert not np.allclose(coloured, audio)


def test_tape_loses_more_top_end_than_the_plain_character() -> None:
    audio = stereo_noise(level=0.3)
    settings = {"enabled": True, "drive": 0.4, "mix": 1.0}

    tape, _ = warmth(audio, SAMPLE_RATE, WarmthSettings(character="tape", **settings))
    plain, _ = warmth(audio, SAMPLE_RATE, WarmthSettings(character="warm", **settings))

    assert band_energy_db(tape, 14_000.0, 20_000.0) < band_energy_db(
        plain, 14_000.0, 20_000.0
    )


def test_negative_tone_darkens_and_positive_brightens() -> None:
    audio = stereo_noise(level=0.2)

    darker, dark_report = tone_tilt(audio, SAMPLE_RATE, -0.10)
    brighter, bright_report = tone_tilt(audio, SAMPLE_RATE, 0.10)

    assert dark_report["tilt_db"] < 0 < bright_report["tilt_db"]
    assert band_energy_db(darker, 8_000.0, 16_000.0) < band_energy_db(
        brighter, 8_000.0, 16_000.0
    )


def test_the_tone_tilt_delivers_the_tilt_it_reports() -> None:
    audio = stereo_noise(level=0.2)

    tilted, report = tone_tilt(audio, SAMPLE_RATE, -0.2)

    low_delta = band_energy_db(tilted, 60.0, 200.0) - band_energy_db(audio, 60.0, 200.0)
    high_delta = band_energy_db(tilted, 12_000.0, 18_000.0) - band_energy_db(
        audio, 12_000.0, 18_000.0
    )
    assert report["tilt_db"] == pytest.approx(-6.0)
    assert low_delta - high_delta == pytest.approx(6.0, abs=1.0)


def test_a_tone_of_zero_is_a_no_op() -> None:
    audio = stereo_noise()

    out, report = tone_tilt(audio, SAMPLE_RATE, 0.0)

    assert report["tilt_db"] == 0.0
    assert np.array_equal(out, audio)


# ---- level policy --------------------------------------------------------


def test_a_track_inside_the_ceiling_keeps_its_level_exactly() -> None:
    audio = stereo_noise(level=0.1)

    out, gain_db = apply_level_policy(audio)

    assert gain_db == 0.0
    assert np.array_equal(out, audio)


def test_a_track_over_the_ceiling_is_pulled_back_to_it() -> None:
    audio = np.clip(stereo_noise(level=0.9), -1.0, 1.0)

    out, gain_db = apply_level_policy(audio)

    assert gain_db < 0.0
    assert true_peak_dbtp(out) == pytest.approx(-1.0, abs=0.2)


def test_true_peak_sees_what_sample_peak_misses() -> None:
    """A tone between the bins peaks higher than any sample it lands on."""
    time = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    between_bins = (0.98 * np.sin(2 * np.pi * 11_025.5 * time + 0.78))[:, None]
    sample_peak_db = 20 * np.log10(np.max(np.abs(between_bins)))

    assert true_peak_dbtp(between_bins) > sample_peak_db


# ---- the chain -----------------------------------------------------------


def test_the_chain_reports_every_module_whether_it_ran_or_not() -> None:
    audio = stereo_noise()
    metrics = metrics_of(audio)

    _, steps, _ = process_audio(audio, SAMPLE_RATE, preset_settings("repair_only"), metrics)

    assert [step.module for step in steps] == [
        "de_artifact",
        "fix_transients",
        "hf_cleanup",
        "restore_air",
        "restore_floor",
        "fix_stereo",
        "warmth",
        "tone_tilt",
        "level_policy",
    ]


def test_cleanup_runs_before_air_is_restored() -> None:
    """Reversed, the expander would eat the band that was just synthesised."""
    audio = stereo_noise()
    order = [
        step.module
        for step in process_audio(audio, SAMPLE_RATE, preset_settings("de_harsh"), metrics_of(audio))[1]
    ]

    assert order.index("hf_cleanup") < order.index("restore_air")


def test_tone_does_not_apply_when_warmth_is_switched_off() -> None:
    audio = stereo_noise()
    settings = SunoFixSettings(
        preset="manual",
        warmth=WarmthSettings(enabled=False, tone=-0.2),
        cleanup=CleanupSettings(enabled=False),
    )

    processed, steps, _ = process_audio(audio, SAMPLE_RATE, settings, metrics_of(audio))

    assert not next(step for step in steps if step.module == "tone_tilt").applied
    assert np.array_equal(processed, audio)


def test_a_pass_with_everything_off_returns_the_source_untouched() -> None:
    audio = stereo_noise()

    processed, _, gain_db = process_audio(
        audio, SAMPLE_RATE, SunoFixSettings(preset="manual"), metrics_of(audio)
    )

    assert gain_db == 0.0
    assert np.array_equal(processed, audio)


def test_the_chain_is_deterministic() -> None:
    audio = with_whistle(lowpassed(stereo_noise(), 15_000.0), 8_000.0)
    metrics = metrics_of(audio)
    settings = SunoFixSettings(
        preset="manual",
        repair=recommended_repair(metrics),
        warmth=WarmthSettings(enabled=True, drive=0.1, mix=0.14, tone=-0.05),
        cleanup=CleanupSettings(enabled=True, strength="medium"),
    )

    first, _, _ = process_audio(audio, SAMPLE_RATE, settings, metrics)
    second, _, _ = process_audio(audio, SAMPLE_RATE, settings, metrics)

    assert np.array_equal(first, second)


def test_restore_floor_repeats_exactly_despite_using_noise() -> None:
    audio = stereo_noise()
    metrics = metrics_of(audio)
    settings = SunoFixSettings(preset="manual", repair=RepairSettings(restore_floor=True))

    first, _, _ = process_audio(audio, SAMPLE_RATE, settings, metrics)
    second, _, _ = process_audio(audio, SAMPLE_RATE, settings, metrics)

    assert np.array_equal(first, second)


def test_a_full_pass_does_not_run_away_with_the_level() -> None:
    # A quiet whistle, as a real artifact is: loud enough to measure, not loud
    # enough that removing it is itself a level change.
    audio = with_whistle(lowpassed(stereo_noise(level=0.15), 15_000.0), 8_000.0, level=0.02)
    metrics = metrics_of(audio)
    settings = SunoFixSettings(
        preset="manual",
        repair=recommended_repair(metrics),
        warmth=PRESETS["add_body"][0],
        cleanup=CleanupSettings(enabled=True, strength="medium"),
    )

    processed, _, _ = process_audio(audio, SAMPLE_RATE, settings, metrics)

    assert rms_db(processed) == pytest.approx(rms_db(audio), abs=1.5)


# ---- files ---------------------------------------------------------------


def test_run_writes_a_new_file_and_leaves_the_source_alone(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    audio = with_whistle(stereo_noise(), 8_000.0)
    sf.write(source, audio, SAMPLE_RATE)
    before_bytes = source.read_bytes()
    destination = tmp_path / "out" / "fixed.wav"

    metrics = measure_artifacts(source)
    result = run(
        source,
        destination,
        SunoFixSettings(preset="de_harsh", repair=recommended_repair(metrics)),
        metrics,
    )

    assert destination.exists()
    assert source.read_bytes() == before_bytes
    assert result.before.name == "source.wav"
    assert result.after.name == "fixed.wav"
    assert result.output_path == destination


def test_run_measures_the_repair_it_made(tmp_path: Path) -> None:
    source = tmp_path / "whistling.wav"
    sf.write(source, with_whistle(stereo_noise(), 8_000.0), SAMPLE_RATE)

    metrics = measure_artifacts(source)
    result = run(
        source,
        tmp_path / "fixed.wav",
        SunoFixSettings(preset="repair_only", repair=RepairSettings(de_artifact=True)),
        metrics,
    )

    before = max(peak.prominence_db for peak in result.before.tonal_peaks)
    after = max((peak.prominence_db for peak in result.after.tonal_peaks), default=0.0)
    assert after < before


def service_at(tmp_path: Path):
    from music_lab_ui.config import LabPaths
    from music_lab_ui.history import HistoryStore
    from music_lab_ui.ui_service import AnalysisService

    return AnalysisService(
        paths=LabPaths.from_root(tmp_path),
        history=HistoryStore(
            tmp_path / "data" / "history.sqlite3", tmp_path / "data" / "runs"
        ),
    )


def test_the_service_measures_then_repairs(tmp_path: Path) -> None:
    """The path the interface takes, end to end, with no Gradio in the way."""
    source = tmp_path / "track.wav"
    sf.write(source, with_whistle(lowpassed(stereo_noise(), 15_000.0), 8_000.0), SAMPLE_RATE)
    service = service_at(tmp_path)

    metrics, suggestions = service.sunofix_recommendations(source)
    settings = preset_settings("de_harsh")
    result = service.run_sunofix(
        source,
        SunoFixSettings(
            preset=settings.preset,
            repair=recommended_repair(metrics),
            warmth=settings.warmth,
            cleanup=settings.cleanup,
        ),
        metrics,
    )

    assert any(item.recommended for item in suggestions)
    assert result.output_path.is_file()
    assert result.output_path.parent == tmp_path / "output" / "sunofix"
    assert settings.preset in result.output_path.name


def test_the_service_refuses_a_source_it_was_not_given(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        service_at(tmp_path).run_sunofix(None, preset_settings("repair_only"))


def test_measure_array_agrees_with_measuring_the_written_file(tmp_path: Path) -> None:
    audio = with_whistle(stereo_noise(), 8_000.0)
    path = tmp_path / "probe.wav"
    sf.write(path, audio, SAMPLE_RATE, subtype="PCM_24")

    from_memory = measure_array(audio, SAMPLE_RATE, "probe.wav")
    from_disk = measure_artifacts(path)

    assert from_memory.rolloff_95_hz == pytest.approx(from_disk.rolloff_95_hz, rel=0.02)
    assert from_memory.hf_cutoff_hz == pytest.approx(from_disk.hf_cutoff_hz, rel=0.02)
