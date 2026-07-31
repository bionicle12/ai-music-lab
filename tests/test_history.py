from pathlib import Path

from music_lab_ui.audio_features import extract_audio_features
from music_lab_ui.contracts import DetectorResult
from music_lab_ui.history import HistoryStore
from scripts.make_smoke_wav import write_tone


def detector_result(probability: float) -> DetectorResult:
    return DetectorResult(
        detector="lofcz",
        status="ok",
        probability=probability,
        label="AI-Generated" if probability >= 0.5 else "Real Music",
        confidence=abs(probability - 0.5) * 2,
        runtime_seconds=0.2,
        device="test",
    )


def test_new_run_is_not_automatically_baseline_and_survives_reopen(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "tone.wav"
    write_tone(audio, seconds=1, sample_rate=16_000)
    features = extract_audio_features(audio)
    store = HistoryStore(tmp_path / "history.sqlite3", tmp_path / "runs")

    saved = store.save_run(audio, features, [detector_result(0.625)], "original")
    reopened = HistoryStore(tmp_path / "history.sqlite3", tmp_path / "runs")

    loaded = reopened.get_run(saved.run_id)
    assert loaded.is_baseline is False
    assert reopened.get_baseline() is None
    assert loaded.note == "original"
    assert loaded.audio_path.is_file()
    loaded_features = reopened.load_features(saved.run_id)
    assert loaded_features.spectrogram_db.shape == (768, 1536)
    assert loaded_features.analysis_settings["n_fft"] == 4096


def test_set_baseline_moves_single_baseline_flag(tmp_path: Path) -> None:
    first_audio = tmp_path / "first.wav"
    second_audio = tmp_path / "second.wav"
    write_tone(first_audio, seconds=1, sample_rate=16_000)
    write_tone(second_audio, seconds=1, sample_rate=16_000)
    store = HistoryStore(tmp_path / "history.sqlite3", tmp_path / "runs")

    first = store.save_run(
        first_audio, extract_audio_features(first_audio), [], "original"
    )
    second = store.save_run(
        second_audio, extract_audio_features(second_audio), [], "EQ"
    )
    store.set_baseline(second.run_id)

    assert first.run_id != second.run_id
    assert store.get_baseline().run_id == second.run_id
    assert sum(run.is_baseline for run in store.list_runs()) == 1


def test_clear_baseline_removes_explicit_reference(tmp_path: Path) -> None:
    audio = tmp_path / "first.wav"
    write_tone(audio, seconds=1, sample_rate=16_000)
    store = HistoryStore(tmp_path / "history.sqlite3", tmp_path / "runs")
    run = store.save_run(audio, extract_audio_features(audio), [], "")
    store.set_baseline(run.run_id)

    store.clear_baseline()

    assert store.get_baseline() is None
    assert all(not item.is_baseline for item in store.list_runs())
