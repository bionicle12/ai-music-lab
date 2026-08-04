from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from music_lab_ui.config import LabPaths
from music_lab_ui.contracts import DetectorResult, LayerResult
from music_lab_ui.history import HistoryStore
from music_lab_ui.telemetry_plots import layer_ranking_figure
from music_lab_ui.ui_presenters import layer_rows
from music_lab_ui.ui_service import AnalysisService
import re
from music_lab_ui.i18n import get_translator

t = get_translator()


def write_tone(path: Path) -> None:
    sample_rate = 48_000
    time = np.arange(sample_rate, dtype=np.float32) / sample_rate
    sf.write(path, 0.1 * np.sin(2 * np.pi * 440 * time), sample_rate)


SCORES = {"drums.wav": 0.97, "guitar.wav": 0.15, "bass.wav": 0.60}


def fake_layer_runner(audio: Path, paths: LabPaths) -> DetectorResult:
    return DetectorResult(
        detector="lofcz",
        status="ok",
        probability=SCORES[audio.name],
        label="x",
        confidence=0.5,
        runtime_seconds=0.1,
        raw={
            "telemetry": {
                "scalars": {"analyzed_duration_seconds": 1.0},
                "arrays": {"residue_db": [1.0, 2.0]},
            }
        },
    )


def layer_service(tmp_path: Path) -> AnalysisService:
    return AnalysisService(
        paths=LabPaths.from_root(tmp_path),
        history=HistoryStore(
            tmp_path / "data" / "history.sqlite3", tmp_path / "data" / "runs"
        ),
        layer_runner=fake_layer_runner,
    )


def test_sweep_ranks_layers_by_score_and_creates_no_runs(tmp_path: Path) -> None:
    service = layer_service(tmp_path)
    files = []
    for name in ("guitar.wav", "drums.wav", "bass.wav"):
        path = tmp_path / name
        write_tone(path)
        files.append(str(path))

    results = service.sweep_layers(files)

    assert [item.name for item in results] == ["drums.wav", "bass.wav", "guitar.wav"]
    assert results[0].mean_residue_db == pytest.approx(1.5)
    # A sweep is a diagnostic, not a version: history must stay untouched.
    assert service.history.list_runs() == []
    # …but the path survives, or there would be nothing to send to MIDI.
    assert results[0].path == str((tmp_path / "drums.wav").resolve())


def test_layer_paths_stay_aligned_with_the_table_rows(tmp_path: Path) -> None:
    """A row index only means something against the list built from the same
    sorted results — sweep_layers re-orders by score."""
    service = layer_service(tmp_path)
    files = []
    for name in ("guitar.wav", "drums.wav"):
        path = tmp_path / name
        write_tone(path)
        files.append(str(path))

    results = service.sweep_layers(files)
    rows = layer_rows(results)
    paths = [item.path for item in results]

    assert [row[0] for row in rows] == ["drums.wav", "guitar.wav"]
    assert [Path(path).name for path in paths] == ["drums.wav", "guitar.wav"]


def test_two_stems_with_the_same_name_stay_distinguishable() -> None:
    """The reason the handoff carries a list and not a name-keyed map."""
    results = [
        LayerResult("bass.wav", "ok", 0.9, 1.0, 8.0, None, "C:/take1/bass.wav"),
        LayerResult("bass.wav", "ok", 0.2, 1.0, 8.0, None, "C:/take2/bass.wav"),
    ]

    assert len({item.path for item in results}) == 2


def test_sweep_rejects_unsupported_files_without_failing_the_batch(tmp_path: Path) -> None:
    service = layer_service(tmp_path)
    good = tmp_path / "drums.wav"
    write_tone(good)
    bad = tmp_path / "notes.txt"
    bad.write_text("x", encoding="utf-8")

    results = service.sweep_layers([str(good), str(bad)])

    assert [item.status for item in results] == ["ok", "error"]
    assert results[1].probability is None


def test_sweep_requires_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=re.escape(t("error.no_layers"))):
        layer_service(tmp_path).sweep_layers([])


def test_layer_ranking_puts_the_worst_layer_on_top() -> None:
    results = [
        LayerResult("drums.wav", "ok", 0.97, 1.5, 10.0),
        LayerResult("guitar.wav", "ok", 0.15, 1.1, 10.0),
    ]

    figure = layer_ranking_figure(results)

    # Horizontal bars render bottom-up, so the worst layer must be drawn last.
    assert list(figure.data[0].y) == ["guitar.wav", "drums.wav"]
    assert list(figure.data[0].x) == pytest.approx([15.0, 97.0])


def test_layer_ranking_handles_a_batch_where_nothing_was_measured() -> None:
    figure = layer_ranking_figure([LayerResult("x.wav", "error", None, None, None, "no")])

    assert figure.data == ()


def test_layer_rows_flag_what_to_redo_first() -> None:
    rows = layer_rows(
        [
            LayerResult("drums.wav", "ok", 0.97, 1.5, 12.0),
            LayerResult("guitar.wav", "ok", 0.15, 1.1, 12.0),
            LayerResult("bad.txt", "error", None, None, None, "не тот формат"),
        ]
    )

    assert rows[0][1] == "97.0%"
    assert rows[0][4] == t("layer.high_priority")
    assert rows[1][4] == t("layer.low_priority")
    assert rows[2][1] == "—"
    assert rows[2][4] == "не тот формат"
