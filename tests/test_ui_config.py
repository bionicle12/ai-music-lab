from pathlib import Path

from music_lab_ui.config import LabPaths


def test_lab_paths_resolve_sibling_repositories(tmp_path: Path) -> None:
    root = tmp_path / "ai-music-lab"
    root.mkdir()

    paths = LabPaths.from_root(root)

    assert paths.root == root.resolve()
    assert paths.lofcz_upstream == tmp_path / "ai-music-detector"
    assert paths.fst_upstream == tmp_path / "FST-AI-Music-Detection"
    assert paths.muscriptor_upstream == tmp_path / "muscriptor"
    assert paths.history_db == root / "data" / "history.sqlite3"
    assert paths.runs_dir == root / "data" / "runs"


def test_lab_paths_keep_local_state_inside_the_repository(tmp_path: Path) -> None:
    """Settings, MIDI output and the weight cache are all git-ignored paths."""
    root = tmp_path / "ai-music-lab"
    root.mkdir()

    paths = LabPaths.from_root(root)

    assert paths.settings_path == root / "data" / "settings.json"
    assert paths.midi_dir == root / "output" / "midi"
    assert paths.muscriptor_cache == root / "models" / "muscriptor-cache"


def test_lab_paths_allow_detector_python_overrides(
    tmp_path: Path, monkeypatch
) -> None:
    lofcz_python = tmp_path / "lofcz-python.exe"
    fst_python = tmp_path / "fst-python.exe"
    muscriptor_python = tmp_path / "muscriptor-python.exe"
    monkeypatch.setenv("AI_MUSIC_LOFCZ_PYTHON", str(lofcz_python))
    monkeypatch.setenv("AI_MUSIC_FST_PYTHON", str(fst_python))
    monkeypatch.setenv("AI_MUSIC_MUSCRIPTOR_PYTHON", str(muscriptor_python))

    paths = LabPaths.from_root(tmp_path / "ai-music-lab")

    assert paths.lofcz_python == lofcz_python
    assert paths.fst_python == fst_python
    assert paths.muscriptor_python == muscriptor_python
