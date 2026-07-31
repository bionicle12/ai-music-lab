from pathlib import Path

import numpy as np
import soundfile as sf
import pytest

from music_lab_ui.config import LabPaths
from music_lab_ui.contracts import DetectorResult
from music_lab_ui.history import HistoryStore
from music_lab_ui.ui_service import AnalysisService
import re
from music_lab_ui.i18n import get_translator

t = get_translator()


def write_tone(path: Path, seconds: float = 1.0, amplitude: float = 0.1) -> None:
    sample_rate = 48_000
    time = np.arange(int(seconds * sample_rate), dtype=np.float32) / sample_rate
    samples = amplitude * np.sin(2 * np.pi * 440 * time)
    sf.write(path, samples, sample_rate)


def fake_runner(audio, selected, paths, progress=None):
    return [
        DetectorResult(
            detector=name,
            status="ok",
            probability=0.75,
            label="AI-Generated",
            confidence=0.5,
            runtime_seconds=0.1,
            device="test",
        )
        for name in selected
    ]


def service_fixture(tmp_path: Path) -> AnalysisService:
    paths = LabPaths.from_root(tmp_path)
    history = HistoryStore(tmp_path / "data" / "history.sqlite3", tmp_path / "data" / "runs")
    return AnalysisService(paths=paths, history=history, detector_runner=fake_runner)


def test_analysis_service_saves_run_without_automatic_comparison(tmp_path: Path) -> None:
    service = service_fixture(tmp_path)
    audio = tmp_path / "version.wav"
    write_tone(audio)

    outcome = service.analyze(str(audio), ["lofcz", "FST"], "правка")

    assert len(service.history.list_runs()) == 1
    assert outcome.run.note == "правка"
    assert outcome.run.is_baseline is False
    assert not hasattr(outcome, "comparison")
    assert [result.detector for result in outcome.run.results] == ["lofcz", "FST"]


def test_load_features_for_3d_does_not_rerun_detectors(tmp_path: Path) -> None:
    service = service_fixture(tmp_path)
    audio = tmp_path / "version.wav"
    write_tone(audio)
    detector_calls = 0

    def counting_runner(audio, selected, paths, progress=None):
        nonlocal detector_calls
        detector_calls += 1
        return fake_runner(audio, selected, paths, progress)

    service.detector_runner = counting_runner
    outcome = service.analyze(str(audio), ["lofcz"], "")

    loaded = service.load_features(outcome.run.run_id)

    assert loaded.metadata.sha256 == outcome.features.metadata.sha256
    assert detector_calls == 1


def test_analysis_service_persists_transient_detector_telemetry(
    tmp_path: Path,
) -> None:
    service = service_fixture(tmp_path)
    audio = tmp_path / "telemetry.wav"
    write_tone(audio)

    def telemetry_runner(audio, selected, paths, progress=None):
        return [
            DetectorResult(
                detector="lofcz",
                status="ok",
                probability=0.75,
                label="AI-Generated",
                confidence=0.5,
                runtime_seconds=0.1,
                raw={
                    "payload": {"probability": 0.75},
                    "telemetry": {
                        "detector": "lofcz",
                        "scalars": {"n_fft": 8192},
                        "arrays": {
                            "frequency_hz": [1000.0, 2000.0],
                            "fakeprint": [0.2, 0.8],
                        },
                        "warnings": [],
                    },
                },
            )
        ]

    service.detector_runner = telemetry_runner
    outcome = service.analyze(str(audio), ["lofcz"], "")

    assert outcome.telemetry["lofcz"].scalars["n_fft"] == 8192
    assert "telemetry" not in outcome.run.results[0].raw
    assert "lofcz" in service.history.load_telemetry(outcome.run.run_id)


def test_analysis_service_requires_audio_and_detector(tmp_path: Path) -> None:
    service = service_fixture(tmp_path)
    audio = tmp_path / "tone.wav"
    write_tone(audio)

    with pytest.raises(ValueError, match=re.escape(t("error.no_audio"))):
        service.analyze(None, ["lofcz"], "")
    with pytest.raises(ValueError, match=re.escape(t("error.no_detector"))):
        service.analyze(str(audio), [], "")


def test_version_choices_do_not_mark_a_baseline(tmp_path: Path) -> None:
    service = service_fixture(tmp_path)
    audio = tmp_path / "tone.wav"
    write_tone(audio)
    outcome = service.analyze(str(audio), ["lofcz"], "")

    choices = service.version_choices()

    assert choices[0][1] == outcome.run.run_id
    assert "baseline" not in choices[0][0].lower()


def test_pinned_version_a_survives_new_runs(tmp_path: Path) -> None:
    service = service_fixture(tmp_path)
    first_audio = tmp_path / "original.wav"
    second_audio = tmp_path / "repair-1.wav"
    third_audio = tmp_path / "repair-2.wav"
    for audio in (first_audio, second_audio, third_audio):
        write_tone(audio)

    original = service.analyze(str(first_audio), ["lofcz"], "")
    service.analyze(str(second_audio), ["lofcz"], "")
    service.pin_version_a(original.run.run_id)
    newest = service.analyze(str(third_audio), ["lofcz"], "")

    assert service.default_version_pair() == (
        original.run.run_id,
        newest.run.run_id,
    )
    assert service.history.get_baseline().run_id == original.run.run_id
    assert service.version_choices()[-1][0].startswith("★ A ·")


def test_clear_version_a_falls_back_to_two_latest(tmp_path: Path) -> None:
    service = service_fixture(tmp_path)
    audios = [tmp_path / f"version-{index}.wav" for index in range(3)]
    runs = []
    for audio in audios:
        write_tone(audio)
        runs.append(service.analyze(str(audio), ["lofcz"], "").run)
    service.pin_version_a(runs[0].run_id)

    service.pin_version_a(None)

    assert service.default_version_pair() == (runs[1].run_id, runs[2].run_id)
    assert service.history.get_baseline() is None


def test_compare_runs_uses_b_minus_a_without_rerunning_detectors(
    tmp_path: Path,
) -> None:
    service = service_fixture(tmp_path)
    audio_a = tmp_path / "version-a.wav"
    audio_b = tmp_path / "version-b.wav"
    write_tone(audio_a, amplitude=0.05)
    write_tone(audio_b, amplitude=0.1)
    run_a = service.analyze(str(audio_a), ["lofcz"], "A")
    run_b = service.analyze(str(audio_b), ["lofcz"], "B")

    def unexpected_runner(*args, **kwargs):
        raise AssertionError("comparison must not rerun detectors")

    service.detector_runner = unexpected_runner
    outcome = service.compare_runs(run_a.run.run_id, run_b.run.run_id)

    assert outcome.run_a.run_id == run_a.run.run_id
    assert outcome.run_b.run_id == run_b.run.run_id
    assert outcome.comparison is not None
    rms_row = next(
        row for row in outcome.comparison.metric_rows if row["metric"] == "RMS"
    )
    assert rms_row["delta"] > 5.9


def test_compare_runs_rejects_same_run(tmp_path: Path) -> None:
    service = service_fixture(tmp_path)
    audio = tmp_path / "version.wav"
    write_tone(audio)
    run = service.analyze(str(audio), ["lofcz"], "")

    with pytest.raises(ValueError, match=re.escape(t("error.same_version"))):
        service.compare_runs(run.run.run_id, run.run.run_id)


def test_compare_runs_keeps_metadata_when_duration_mismatch_blocks_heatmap(
    tmp_path: Path,
) -> None:
    service = service_fixture(tmp_path)
    short_audio = tmp_path / "short.wav"
    long_audio = tmp_path / "long.wav"
    write_tone(short_audio, seconds=1.0)
    write_tone(long_audio, seconds=1.2)
    short = service.analyze(str(short_audio), ["lofcz"], "")
    long = service.analyze(str(long_audio), ["lofcz"], "")

    outcome = service.compare_runs(short.run.run_id, long.run.run_id)

    assert outcome.run_a.run_id == short.run.run_id
    assert outcome.run_b.run_id == long.run.run_id
    assert outcome.comparison is None
    assert "duration differs by more than 5%" in outcome.comparison_note


def fake_timeline_runner(audio, paths, *, window_seconds, hop_seconds):
    return {
        "telemetry": {
            "detector": "lofcz-timeline",
            "scalars": {
                "window_seconds": window_seconds,
                "hop_seconds": hop_seconds,
            },
            "arrays": {
                "window_start_seconds": [0.0, 5.0],
                "window_end_seconds": [15.0, 20.0],
                "window_center_seconds": [7.5, 12.5],
                "probability": [0.1, 0.9],
                "mean_residue_db": [1.1, 1.4],
            },
            "warnings": ["relative map"],
        }
    }


def timeline_service(tmp_path: Path) -> AnalysisService:
    paths = LabPaths.from_root(tmp_path)
    history = HistoryStore(tmp_path / "data" / "history.sqlite3", tmp_path / "data" / "runs")
    return AnalysisService(
        paths=paths,
        history=history,
        detector_runner=fake_runner,
        timeline_runner=fake_timeline_runner,
    )


def test_build_timeline_persists_map_without_creating_a_new_run(tmp_path: Path) -> None:
    service = timeline_service(tmp_path)
    audio = tmp_path / "version.wav"
    write_tone(audio)
    outcome = service.analyze(str(audio), ["lofcz"], "")
    runs_before = len(service.history.list_runs())

    timeline = service.build_timeline(outcome.run.run_id, window_seconds=15, hop_seconds=5)

    assert timeline.detector == "lofcz-timeline"
    assert len(service.history.list_runs()) == runs_before
    # Survives a round-trip through the checksum-validated telemetry store.
    reloaded = service.load_timeline(outcome.run.run_id)
    assert reloaded is not None
    assert list(reloaded.arrays["probability"]) == pytest.approx([0.1, 0.9])


def test_build_timeline_requires_a_run(tmp_path: Path) -> None:
    service = timeline_service(tmp_path)

    with pytest.raises(ValueError, match=re.escape(t("error.no_run"))):
        service.build_timeline(None)


def test_load_timeline_is_none_before_the_map_is_built(tmp_path: Path) -> None:
    service = timeline_service(tmp_path)
    audio = tmp_path / "version.wav"
    write_tone(audio)
    outcome = service.analyze(str(audio), ["lofcz"], "")

    assert service.load_timeline(outcome.run.run_id) is None
