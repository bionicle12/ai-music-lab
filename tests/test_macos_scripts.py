from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def copy_launcher(name: str, destination: Path) -> Path:
    launcher = destination / name
    shutil.copy2(ROOT / name, launcher)
    launcher.chmod(0o755)
    return launcher


def make_recorder(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'cwd=%s\\n' \"$PWD\"\n"
        "printf 'utf8=%s\\n' \"${PYTHONUTF8:-}\"\n"
        "printf 'arg=%s\\n' \"$@\"\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_bootstrap_launcher_resolves_script_from_its_own_directory(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    caller = tmp_path / "elsewhere"
    project.mkdir()
    caller.mkdir()
    launcher = copy_launcher("bootstrap_macos.sh", project)
    recorder = tmp_path / "record-python"
    make_recorder(recorder)

    completed = subprocess.run(
        [str(launcher)],
        cwd=caller,
        env={**os.environ, "AI_MUSIC_BOOTSTRAP_PYTHON": str(recorder)},
        check=True,
        capture_output=True,
        text=True,
    )

    assert f"arg={project / 'scripts' / 'bootstrap_macos.py'}" in completed.stdout


def test_ui_launcher_runs_project_venv_from_project_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    caller = tmp_path / "elsewhere"
    project.mkdir()
    caller.mkdir()
    launcher = copy_launcher("start_ui.sh", project)
    make_recorder(project / ".venv-ui" / "bin" / "python")

    completed = subprocess.run(
        [str(launcher)],
        cwd=caller,
        check=True,
        capture_output=True,
        text=True,
    )

    assert f"cwd={project}" in completed.stdout
    assert "utf8=1" in completed.stdout
    assert "arg=-m" in completed.stdout
    assert "arg=music_lab_ui.app" in completed.stdout


def test_ui_launcher_explains_how_to_create_a_missing_environment(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    launcher = copy_launcher("start_ui.sh", project)

    completed = subprocess.run(
        [str(launcher)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "./bootstrap_macos.sh" in completed.stderr
