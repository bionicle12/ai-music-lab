"""Git is driven through an injected runner, so every branch is testable dry.

The assertion that matters most is negative: a refused pull must never let a
mutating command reach git at all.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from music_lab_ui.config import LabPaths
from music_lab_ui.repositories import (
    REPOSITORIES,
    REPOSITORIES_BY_KEY,
    all_statuses,
    parse_behind,
    parse_dirty,
    pull,
    read_status,
    repo_path,
)

MUSCRIPTOR = REPOSITORIES_BY_KEY["muscriptor"]
LOFCZ = REPOSITORIES_BY_KEY["lofcz"]


class FakeGit:
    """Answers by the exact command, and records every argv it was handed.

    Keyed on the whole command rather than the subcommand: `rev-parse HEAD` and
    `rev-parse --abbrev-ref HEAD` are different questions with very different
    answers, and conflating them hides the detached-HEAD case entirely.
    """

    def __init__(self, answers: dict[str, tuple[int, str]] | None = None) -> None:
        self.answers = answers or {}
        self.calls: list[list[str]] = []

    def __call__(self, argv, **_kwargs):
        self.calls.append(list(argv))
        command = " ".join(argv[3:])
        for prefix, (code, out) in self.answers.items():
            if command.startswith(prefix):
                return subprocess.CompletedProcess(argv, code, out, "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    @property
    def commands(self) -> list[str]:
        return [" ".join(call[3:]) for call in self.calls]

    def ran(self, prefix: str) -> bool:
        return any(command.startswith(prefix) for command in self.commands)


def make_clone(tmp_path: Path, repo=MUSCRIPTOR) -> LabPaths:
    """A directory that looks like the clone, without being a git repository."""
    root = tmp_path / "ai-music-lab"
    root.mkdir()
    clone = tmp_path / repo.folder
    for name in repo.required_files:
        target = clone / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    return LabPaths.from_root(root)


def healthy(head: str = "a" * 40, branch: str = "main") -> dict:
    """A clean clone on a branch, up to date with its upstream."""
    return {
        "rev-parse --git-dir": (0, ".git"),
        "rev-parse --abbrev-ref HEAD": (0, branch),
        "rev-parse HEAD": (0, head),
        "status --porcelain": (0, ""),
        "fetch": (0, ""),
        "rev-list": (0, "0"),
        "log": (0, "Add beat detection"),
        "diff": (0, ""),
        "pull --ff-only": (0, "Fast-forward"),
    }


def detached(head: str) -> dict:
    """git spells "detached" as the literal string HEAD."""
    return {**healthy(head=head), "rev-parse --abbrev-ref HEAD": (0, "HEAD")}


def test_parsers_are_pure() -> None:
    assert parse_dirty("") is False
    assert parse_dirty("\n  \n") is False
    assert parse_dirty(" M music_lab_ui/app.py\n") is True
    assert parse_behind("3\n") == 3
    # rev-list fails on a detached HEAD; that is unknown, not zero.
    assert parse_behind("") is None
    assert parse_behind("fatal: no upstream") is None


def test_a_missing_clone_is_reported_not_raised(tmp_path: Path) -> None:
    paths = LabPaths.from_root(tmp_path / "ai-music-lab")
    runner = FakeGit()

    status = read_status(MUSCRIPTOR, paths, runner=runner)

    assert status.present is False
    assert status.can_pull is False
    # Nothing on disk means nothing to ask git about.
    assert runner.calls == []


def test_status_reads_head_branch_and_distance(tmp_path: Path) -> None:
    paths = make_clone(tmp_path)
    answers = healthy()
    answers["rev-list"] = (0, "4")

    status = read_status(MUSCRIPTOR, paths, runner=FakeGit(answers))

    assert status.present and status.is_git
    assert status.head == "a" * 40
    assert status.branch == "main"
    assert status.dirty is False
    assert status.behind == 4
    assert status.can_pull is True


def test_a_detached_head_cannot_be_pulled(tmp_path: Path) -> None:
    """The detectors are parked on purpose; a pull there is never right."""
    paths = make_clone(tmp_path, LOFCZ)
    runner = FakeGit(detached(head=LOFCZ.pinned_commit))

    status = read_status(LOFCZ, paths, runner=runner)

    assert status.branch is None
    assert status.can_pull is False
    assert status.matches_pin is True
    # A pinned repo is never fetched: that would be a network call for nothing.
    assert not runner.ran("fetch")


def test_pull_is_refused_for_a_pinned_repository(tmp_path: Path) -> None:
    paths = make_clone(tmp_path, LOFCZ)
    runner = FakeGit(healthy())

    outcome = pull(LOFCZ, paths, runner=runner)

    assert outcome.performed is False
    assert outcome.refused_reason == "pinned"
    assert runner.calls == []


def test_pull_is_refused_on_a_dirty_tree_without_touching_git(
    tmp_path: Path,
) -> None:
    paths = make_clone(tmp_path)
    answers = healthy()
    answers["status --porcelain"] = (0, " M muscriptor/main.py\n?? scratch.py\n")
    runner = FakeGit(answers)

    outcome = pull(MUSCRIPTOR, paths, runner=runner)

    assert outcome.performed is False
    assert outcome.refused_reason == "dirty"
    # The user's own edits are quoted back so they can see what is in the way.
    assert "muscriptor/main.py" in outcome.log
    # The safety property: no mutating command was ever built.
    assert not runner.ran("pull")


def test_pull_is_refused_when_the_directory_is_not_a_repository(
    tmp_path: Path,
) -> None:
    paths = make_clone(tmp_path)
    runner = FakeGit({"rev-parse --git-dir": (128, "")})

    outcome = pull(MUSCRIPTOR, paths, runner=runner)

    assert outcome.refused_reason == "not_a_repository"
    assert not runner.ran("pull")


def test_a_successful_pull_reports_the_move_and_dependency_drift(
    tmp_path: Path,
) -> None:
    paths = make_clone(tmp_path)
    heads = iter(["b" * 40, "c" * 40])

    class Moving(FakeGit):
        """HEAD answers differently before and after the fast-forward."""

        def __call__(self, argv, **kwargs):
            if " ".join(argv[3:]) == "rev-parse HEAD":
                self.calls.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, next(heads), "")
            return super().__call__(argv, **kwargs)

    answers = healthy()
    answers["diff"] = (0, "pyproject.toml\nmuscriptor/main.py\n")

    outcome = pull(MUSCRIPTOR, paths, runner=Moving(answers))

    assert outcome.performed is True
    assert outcome.previous_head == "b" * 40
    assert outcome.new_head == "c" * 40
    assert outcome.subject == "Add beat detection"
    # An editable install picks up code for free but not new dependencies.
    assert outcome.dependencies_changed is True


def test_a_failed_pull_surfaces_git_output_rather_than_claiming_success(
    tmp_path: Path,
) -> None:
    paths = make_clone(tmp_path)
    answers = healthy()
    answers["pull --ff-only"] = (1, "fatal: Not possible to fast-forward")
    runner = FakeGit(answers)

    outcome = pull(MUSCRIPTOR, paths, runner=runner)

    assert outcome.performed is False
    assert outcome.refused_reason == "pull_failed"
    assert "fast-forward" in outcome.log


@pytest.mark.parametrize("repo", REPOSITORIES, ids=lambda repo: repo.key)
def test_every_registered_repository_is_described_completely(repo) -> None:
    assert repo.url.startswith("https://")
    assert len(repo.pinned_commit) == 40
    assert repo.required_files
    assert repo.license_key.startswith("repo.license.")


def test_only_muscriptor_is_allowed_to_move() -> None:
    tracking = {repo.key for repo in REPOSITORIES if repo.track_branch}

    assert tracking == {"muscriptor"}


def test_all_statuses_covers_every_repository(tmp_path: Path) -> None:
    paths = LabPaths.from_root(tmp_path / "ai-music-lab")

    statuses = all_statuses(paths, runner=FakeGit(), fetch=False)

    assert [status.key for status in statuses] == [
        repo.key for repo in REPOSITORIES
    ]


def test_repo_path_is_a_sibling_of_the_wrapper(tmp_path: Path) -> None:
    paths = LabPaths.from_root(tmp_path / "ai-music-lab")

    assert repo_path(MUSCRIPTOR, paths) == tmp_path / "muscriptor"
