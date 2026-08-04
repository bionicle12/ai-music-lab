"""Guards for the one part of the app that runs commands of its own.

Everything else here either reads files or spawns an adapter this repository
wrote. Provisioning clones repositories and builds environments, so the tests
that matter are the ones about what it refuses to do.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest

from music_lab_ui.config import LabPaths
from music_lab_ui.provisioning import (
    ENVIRONMENTS,
    PYTHON_VERSION,
    Download,
    ProvisioningError,
    agent_prompt,
    check_clone_target,
    check_download_target,
    clone_command,
    conda_executable,
    environment_commands,
    load_downloads,
    stream_command,
    verify,
)
from music_lab_ui.readiness import DETECTOR_REQUIREMENTS
from music_lab_ui.repositories import REPOSITORIES_BY_KEY


def test_conda_is_found_through_the_variable_an_activated_shell_sets(
    tmp_path: Path,
) -> None:
    """`CONDA_EXE` points at the installation actually in use; a bare `conda`
    on PATH may belong to a different one."""
    executable = tmp_path / "conda.exe"
    executable.write_text("", encoding="utf-8")

    assert conda_executable({"CONDA_EXE": str(executable)}) == str(executable)


def test_no_conda_is_reported_rather_than_assumed(tmp_path: Path) -> None:
    """Without this the interface would offer to build an environment on a
    machine with nothing to build it with."""
    assert conda_executable({"CONDA_EXE": "", "PATH": str(tmp_path)}) is None


def test_a_stale_conda_exe_does_not_count(tmp_path: Path) -> None:
    assert conda_executable({"CONDA_EXE": str(tmp_path / "gone.exe"), "PATH": ""}) is None


def test_cloning_refuses_a_directory_that_already_has_files_in_it(
    tmp_path: Path,
) -> None:
    """git would merge into it. Somebody's edited checkout is not ours to
    merge into, and a wrapper silently changing a working copy is the failure
    this whole project is arranged to avoid."""
    paths = LabPaths.from_root(tmp_path / "ai-music-lab")
    repo = REPOSITORIES_BY_KEY["lofcz"]
    target = tmp_path / repo.folder
    target.mkdir(parents=True)
    (target / "work-in-progress.py").write_text("", encoding="utf-8")

    with pytest.raises(ProvisioningError) as error:
        check_clone_target(repo, paths)

    assert error.value.code == "occupied"


def test_cloning_into_an_empty_or_absent_directory_is_allowed(tmp_path: Path) -> None:
    paths = LabPaths.from_root(tmp_path / "ai-music-lab")
    repo = REPOSITORIES_BY_KEY["lofcz"]

    check_clone_target(repo, paths)
    (tmp_path / repo.folder).mkdir(parents=True)
    check_clone_target(repo, paths)


def test_the_clone_is_not_shallow(tmp_path: Path) -> None:
    """The pinned commit has to stay reachable; a shallow clone of the default
    branch may not contain it."""
    paths = LabPaths.from_root(tmp_path / "ai-music-lab")
    command = clone_command(REPOSITORIES_BY_KEY["fst"], paths)

    assert "--depth" not in command
    assert command[:2] == ["git", "clone"]


def test_commands_are_built_from_constants_and_never_from_input(
    tmp_path: Path,
) -> None:
    """The whole safety argument for running commands at all rests on this."""
    paths = LabPaths.from_root(tmp_path / "ai-music-lab")
    create, install = environment_commands("FST", paths, "conda")

    assert create == [
        "conda", "create", "-n", "ai-music-fst", f"python={PYTHON_VERSION}", "-y"
    ]
    assert install[:7] == [
        "conda", "run", "-n", "ai-music-fst", "python", "-m", "pip"
    ]
    assert install[-1].endswith("ai-music-fst.txt")


def test_every_detector_has_an_environment_to_build() -> None:
    """A detector the checklist can complain about but the installer cannot
    fix would be a dead end in the interface."""
    for item in DETECTOR_REQUIREMENTS:
        assert item.detector in ENVIRONMENTS


def test_a_download_that_cannot_be_automated_says_so(tmp_path: Path) -> None:
    """Google Drive serves large files behind a confirmation page, so there is
    no stable direct URL. A button that pretended otherwise would fail in a way
    nobody could act on."""
    paths = LabPaths.from_root(tmp_path)
    stage1 = load_downloads(Path(__file__).parents[1])["fst_stage1"]

    with pytest.raises(ProvisioningError) as error:
        check_download_target(stage1, paths)

    assert error.value.code == "manual"


def test_an_existing_checkpoint_is_never_replaced(tmp_path: Path) -> None:
    paths = LabPaths.from_root(tmp_path)
    lofcz = load_downloads(Path(__file__).parents[1])["lofcz"]
    paths.lofcz_model.parent.mkdir(parents=True, exist_ok=True)
    paths.lofcz_model.write_bytes(b"already here")

    with pytest.raises(ProvisioningError) as error:
        check_download_target(lofcz, paths)

    assert error.value.code == "present"


def test_verification_is_about_the_bytes_not_the_filename(tmp_path: Path) -> None:
    """A green tick has to mean the checkpoint is right, not that a file with
    the right name appeared."""
    payload = b"weights"
    target = tmp_path / "Stage-1.ckpt"
    target.write_bytes(payload)
    download = Download(
        key="fst_stage1",
        filename="Stage-1.ckpt",
        url="https://example.invalid",
        automatable=False,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )

    assert verify(target, download)
    target.write_bytes(b"something else")
    assert not verify(target, download)


def test_published_checksums_match_the_documentation() -> None:
    """The interface verifies against `models/sources.json`; the Models page
    quotes the same numbers. Two sources of truth for a checksum is one too
    many."""
    root = Path(__file__).parents[1]
    downloads = load_downloads(root)
    documented = (root / "docs" / "models.md").read_text(encoding="utf-8")

    for item in downloads.values():
        assert item.sha256, item.key
        assert item.sha256 in documented, item.key


def test_a_command_that_says_nothing_is_killed_rather_than_waited_on() -> None:
    """A credential prompt produces no output and would otherwise hold the
    Gradio worker until the process is killed by hand."""

    def never_speaks():
        # Blocks the way a process waiting on a credential prompt does, rather
        # than ending: an empty stdout would just look like a finished command.
        time.sleep(5)
        yield "too late\n"

    class SilentProcess:
        stdout = never_speaks()

        def __init__(self) -> None:
            self.killed = False

        def kill(self) -> None:
            self.killed = True

        def poll(self) -> int | None:
            return 0 if self.killed else None

        def wait(self, timeout: float | None = None) -> int:
            return 0

    process = SilentProcess()

    with pytest.raises(ProvisioningError) as error:
        list(
            stream_command(
                ["conda", "create"],
                cwd=Path.cwd(),
                popener=lambda *args, **kwargs: process,
                idle_timeout=0.05,
            )
        )

    assert error.value.code == "stalled"
    assert process.killed


def test_a_failing_command_is_reported_with_its_exit_code() -> None:
    class FailingProcess:
        stdout = ["configuring\n", "boom\n"]

        def kill(self) -> None:  # pragma: no cover - not reached
            pass

        def poll(self) -> int:
            return 1

        def wait(self, timeout: float | None = None) -> int:
            return 1

    lines = []
    with pytest.raises(ProvisioningError) as error:
        for line in stream_command(
            ["conda", "create"],
            cwd=Path.cwd(),
            popener=lambda *args, **kwargs: FailingProcess(),
        ):
            lines.append(line)

    assert lines == ["configuring", "boom"]
    assert error.value.code == "failed"


def test_the_agent_prompt_carries_everything_the_agent_would_have_to_ask_for(
    tmp_path: Path,
) -> None:
    """This is the exit from a step that will not go through, so it has to
    stand on its own — the person pasting it is out of ideas already."""
    paths = LabPaths.from_root(tmp_path)
    commands = environment_commands("FST", paths, "conda")

    prompt = agent_prompt("FST", "env", paths, commands, log="ResolvePackageNotFound")

    assert str(paths.root) in prompt
    assert "ai-music-fst" in prompt
    assert "ResolvePackageNotFound" in prompt
    assert "docs/getting-started.md" in prompt


def test_the_agent_prompt_keeps_only_the_end_of_a_long_log(tmp_path: Path) -> None:
    """pip can produce thousands of lines, and a prompt nobody can paste is
    not an escape route."""
    paths = LabPaths.from_root(tmp_path)
    log = "\n".join(f"line {index}" for index in range(500))

    prompt = agent_prompt("FST", "env", paths, [["conda"]], log=log)

    assert "line 499" in prompt
    assert "line 400" not in prompt
