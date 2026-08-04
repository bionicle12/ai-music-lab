"""Where the upstream clones are, what state they are in, and how they update.

This project vendors nothing: the detectors and the transcriber are separate
clones sitting beside this repository. Until now, checking and updating them was
documented PowerShell. This module makes the checking part something the
interface can show, and the updating part something it can do for the one
upstream that is meant to move.

SAFETY PROPERTY — worth preserving on every edit: the only mutating git command
in this module is ``pull --ff-only``. No ``checkout``, ``reset``, ``clean``,
``merge``, ``rebase``, ``stash``, ``submodule``, and nothing with ``--force``.
A wrapper has no business rewriting someone's working copy; the worst it may do
is fast-forward a clean tree that is already tracking a branch.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from .config import LabPaths

Runner = Callable[..., "subprocess.CompletedProcess[str]"]

#: Git must never stop to ask for credentials: the prompt would block the git
#: process forever, and the Gradio worker waiting on it with the same patience.
GIT_ENVIRONMENT: Final[dict[str, str]] = {"GIT_TERMINAL_PROMPT": "0"}

GIT_TIMEOUT_SECONDS: Final[float] = 120.0


@dataclass(frozen=True)
class UpstreamRepo:
    key: str
    folder: str
    url: str
    #: The commit this wrapper was last verified against. Informational, not a
    #: constraint — the app reports drift and never enforces it.
    pinned_commit: str
    #: ``None`` means the clone is deliberately parked on a detached HEAD and
    #: pulling is refused. Only a repo with a branch to track can move.
    track_branch: str | None
    required_files: tuple[str, ...]
    license_key: str


REPOSITORIES: Final[tuple[UpstreamRepo, ...]] = (
    UpstreamRepo(
        key="lofcz",
        folder="ai-music-detector",
        url="https://github.com/lofcz/ai-music-detector.git",
        pinned_commit="6ba389e94a179ac90f3eb134b741ef37baa30434",
        track_branch=None,
        required_files=("src/python/inference.py",),
        license_key="repo.license.upstream",
    ),
    UpstreamRepo(
        key="fst",
        folder="FST-AI-Music-Detection",
        url="https://github.com/Mippia/FST-AI-Music-Detection.git",
        pinned_commit="b564f8be8b3db6b7810c2aab61f0b4f86f889579",
        track_branch=None,
        required_files=("model.py", "inference.py", "preprocess.py"),
        license_key="repo.license.upstream",
    ),
    UpstreamRepo(
        key="muscriptor",
        folder="muscriptor",
        url="https://github.com/muscriptor/muscriptor.git",
        pinned_commit="e2bd0fc5994f9acba7c1387ca5df67eb8d95df44",
        track_branch="main",
        required_files=("pyproject.toml", "muscriptor/__init__.py"),
        license_key="repo.license.mit_nc_weights",
    ),
)

REPOSITORIES_BY_KEY: Final[dict[str, UpstreamRepo]] = {
    repo.key: repo for repo in REPOSITORIES
}


@dataclass(frozen=True)
class RepoStatus:
    key: str
    path: Path
    present: bool
    is_git: bool
    head: str | None
    branch: str | None
    dirty: bool
    dirty_summary: str
    behind: int | None
    matches_pin: bool
    can_pull: bool
    error: str | None = None


@dataclass(frozen=True)
class PullOutcome:
    key: str
    performed: bool
    refused_reason: str | None
    previous_head: str | None
    new_head: str | None
    subject: str | None
    dependencies_changed: bool
    log: str


def repo_path(repo: UpstreamRepo, paths: LabPaths) -> Path:
    return paths.root.parent / repo.folder


def parse_dirty(porcelain: str) -> bool:
    """``git status --porcelain`` prints nothing at all when the tree is clean."""
    return bool(porcelain.strip())


def parse_behind(text: str) -> int | None:
    """``rev-list --count`` fails on a detached HEAD, which is not an error here."""
    try:
        return int(text.strip())
    except (TypeError, ValueError):
        return None


def _git(
    path: Path,
    *arguments: str,
    runner: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    return runner(
        ["git", "-C", str(path), *arguments],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
        env={**os.environ, **GIT_ENVIRONMENT},
    )


def _first_line(completed: subprocess.CompletedProcess[str]) -> str | None:
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def read_status(
    repo: UpstreamRepo,
    paths: LabPaths,
    *,
    runner: Runner = subprocess.run,
    fetch: bool = True,
) -> RepoStatus:
    """Describe one clone. Never raises: a broken clone is a status, not a crash."""
    path = repo_path(repo, paths)
    blank = RepoStatus(
        key=repo.key,
        path=path,
        present=False,
        is_git=False,
        head=None,
        branch=None,
        dirty=False,
        dirty_summary="",
        behind=None,
        matches_pin=False,
        can_pull=False,
    )
    if not all((path / name).is_file() for name in repo.required_files):
        return blank

    try:
        if _git(path, "rev-parse", "--git-dir", runner=runner).returncode != 0:
            return replace(blank, present=True)
        porcelain = _git(path, "status", "--porcelain", runner=runner)
        head = _first_line(_git(path, "rev-parse", "HEAD", runner=runner))
        branch_name = _first_line(
            _git(path, "rev-parse", "--abbrev-ref", "HEAD", runner=runner)
        )
        # git spells "detached" as the literal string HEAD.
        branch = None if branch_name == "HEAD" else branch_name
        behind = None
        if repo.track_branch and branch and fetch:
            _git(path, "fetch", "--quiet", "origin", runner=runner)
            behind = parse_behind(
                _git(path, "rev-list", "--count", "HEAD..@{u}", runner=runner).stdout
            )
    except (OSError, subprocess.SubprocessError) as error:
        return replace(blank, present=True, error=str(error))

    dirty = parse_dirty(porcelain.stdout)
    return RepoStatus(
        key=repo.key,
        path=path,
        present=True,
        is_git=True,
        head=head,
        branch=branch,
        dirty=dirty,
        dirty_summary=porcelain.stdout.strip(),
        behind=behind,
        matches_pin=bool(head) and head == repo.pinned_commit,
        can_pull=bool(repo.track_branch) and branch is not None and not dirty,
    )


def all_statuses(
    paths: LabPaths,
    *,
    runner: Runner = subprocess.run,
    fetch: bool = True,
) -> tuple[RepoStatus, ...]:
    return tuple(
        read_status(repo, paths, runner=runner, fetch=fetch) for repo in REPOSITORIES
    )


def pull(
    repo: UpstreamRepo,
    paths: LabPaths,
    *,
    runner: Runner = subprocess.run,
) -> PullOutcome:
    """Fast-forward one clone, or explain precisely why it will not.

    Every refusal returns before any mutating command is built, so a refused
    pull leaves the working copy untouched by construction rather than by
    accident.
    """
    path = repo_path(repo, paths)

    def refuse(reason: str, log: str = "") -> PullOutcome:
        return PullOutcome(
            key=repo.key,
            performed=False,
            refused_reason=reason,
            previous_head=None,
            new_head=None,
            subject=None,
            dependencies_changed=False,
            log=log,
        )

    if repo.track_branch is None:
        return refuse("pinned")
    status = read_status(repo, paths, runner=runner, fetch=False)
    if not status.present:
        return refuse("missing")
    if not status.is_git:
        return refuse("not_a_repository")
    if status.branch is None:
        return refuse("detached")
    if status.dirty:
        return refuse("dirty", status.dirty_summary)

    completed = _git(path, "pull", "--ff-only", runner=runner)
    if completed.returncode != 0:
        return refuse(
            "pull_failed",
            (completed.stderr or completed.stdout).strip(),
        )

    new_head = _first_line(_git(path, "rev-parse", "HEAD", runner=runner))
    subject = _first_line(_git(path, "log", "-1", "--pretty=%s", runner=runner))
    changed = ()
    if status.head and new_head and status.head != new_head:
        diff = _git(
            path,
            "diff",
            "--name-only",
            f"{status.head}..{new_head}",
            runner=runner,
        )
        changed = tuple(diff.stdout.split())
    return PullOutcome(
        key=repo.key,
        performed=True,
        refused_reason=None,
        previous_head=status.head,
        new_head=new_head,
        subject=subject,
        # An editable install picks up new code for free but not new
        # dependencies; without this the environment drifts silently.
        dependencies_changed="pyproject.toml" in changed,
        log=(completed.stdout or "").strip(),
    )
