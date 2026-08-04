"""Getting a detector from "missing" to "runnable", from inside the interface.

Setting this project up by hand is three clones, four Conda environments and
five files downloaded from four different places. That is fine once and awful
on a second machine, which is what this module is for.

It also widens what the app is allowed to do, so the boundaries are explicit:

* **Commands are built from constants only.** Repository URLs come from
  :mod:`music_lab_ui.repositories`, environment names and requirement files from
  the table below, download URLs from ``models/sources.json``. Nothing here
  interpolates a value that came from a text box, and no command runs through a
  shell.
* **Nothing is overwritten.** A clone into a directory that already has files in
  it is refused rather than merged; a download to an existing file is refused
  rather than replaced. Every step is a no-op when its work is already done, so
  running the whole list twice is safe.
* **Conda is a precondition, not something to install.** If it is not on the
  machine, the interface says so and stops — bootstrapping a package manager
  from a web page is not a thing this project will do.

The last rule is the one that shapes the rest: `conda create` takes minutes and
fails for reasons nobody can predict from here — a proxy, a locked file, a
resolver conflict. So a failure is a first-class outcome with somewhere to go,
not an error message: :func:`agent_prompt` produces the text you can hand to a
coding agent, with the paths and the log already in it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Final

from .config import LabPaths
from .repositories import GIT_ENVIRONMENT, REPOSITORIES_BY_KEY, UpstreamRepo, repo_path

Popener = Callable[..., subprocess.Popen]

#: No output for this long and the step is considered hung. Generous because
#: `pip install` legitimately goes quiet while it builds a wheel.
IDLE_TIMEOUT_SECONDS: Final[float] = 300.0

#: The whole of a step. Past this it stops and hands over to the agent prompt:
#: an install that has been running for twenty minutes is not about to succeed
#: on its own, and watching it forever is worse than being told to take over.
TOTAL_TIMEOUT_SECONDS: Final[float] = 1_200.0

#: Downloads are the exception — a checkpoint is over a gigabyte on a domestic
#: connection, and giving up on it at twenty minutes would be its own bug.
DOWNLOAD_TIMEOUT_SECONDS: Final[float] = 3_600.0

PYTHON_VERSION: Final[str] = "3.11"


@dataclass(frozen=True)
class EnvironmentSpec:
    name: str
    requirements: str


#: Which Conda environment each detector needs, and the pinned requirements that
#: fill it. Both are constants; neither is ever taken from the interface.
ENVIRONMENTS: Final[dict[str, EnvironmentSpec]] = {
    "lofcz": EnvironmentSpec("ai-music-lofcz", "ai-music-lofcz.txt"),
    "FST": EnvironmentSpec("ai-music-fst", "ai-music-fst.txt"),
    "muscriptor": EnvironmentSpec("ai-music-muscriptor", "ai-music-muscriptor.txt"),
}

#: Which download entries belong to which detector, in the order a person would
#: fetch them.
WEIGHT_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "lofcz": ("lofcz",),
    "FST": ("fst_stage1", "fst_stage2"),
}

#: Where each download lands, as an attribute of :class:`LabPaths`.
WEIGHT_DESTINATIONS: Final[dict[str, str]] = {
    "lofcz": "lofcz_model",
    "fst_stage1": "fst_stage1",
    "fst_stage2": "fst_stage2",
}


class ProvisioningError(RuntimeError):
    """A step that could not be run, or that ran and failed.

    ``code`` is what the interface switches on; ``detail`` is what it shows.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Download:
    key: str
    filename: str
    url: str
    automatable: bool
    size_bytes: int
    sha256: str


def load_downloads(root: Path) -> dict[str, Download]:
    """Read ``models/sources.json`` from the repository root.

    Kept as data rather than as constants in here so that the URLs, sizes and
    checksums the documentation quotes and the ones the interface verifies
    against cannot drift apart.
    """
    source = Path(root) / "models" / "sources.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    return {
        key: Download(
            key=key,
            filename=str(entry["filename"]),
            url=str(entry["url"]),
            automatable=bool(entry.get("automatable", False)),
            size_bytes=int(entry.get("size_bytes", 0)),
            sha256=str(entry.get("sha256", "")),
        )
        for key, entry in payload.items()
    }


def conda_executable(environ: Mapping[str, str] | None = None) -> str | None:
    """Where Conda is, or ``None``.

    ``CONDA_EXE`` first: it is set by every activated Conda shell and points at
    the installation actually in use, which a bare ``conda`` on PATH may not.
    """
    source = dict(os.environ if environ is None else environ)
    candidate = source.get("CONDA_EXE", "").strip()
    if candidate and Path(candidate).is_file():
        return candidate
    found = shutil.which("conda", path=source.get("PATH"))
    return found or None


def clone_command(repo: UpstreamRepo, paths: LabPaths) -> list[str]:
    """``git clone`` into the folder beside this repository.

    No ``--depth``: the pinned commit has to stay reachable, and a shallow clone
    of the default branch may not contain it.
    """
    return ["git", "clone", repo.url, str(repo_path(repo, paths))]


def environment_commands(
    detector: str,
    paths: LabPaths,
    conda: str,
) -> list[list[str]]:
    """Create the environment, then fill it from the pinned requirements.

    Two commands rather than one, because they fail differently: the first for
    reasons about Conda itself, the second for reasons about a package. Running
    them separately means the log says which.
    """
    spec = ENVIRONMENTS[detector]
    requirements = paths.root / "environments" / spec.requirements
    return [
        [conda, "create", "-n", spec.name, f"python={PYTHON_VERSION}", "-y"],
        [
            conda,
            "run",
            "-n",
            spec.name,
            "python",
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements),
        ],
    ]


def check_clone_target(repo: UpstreamRepo, paths: LabPaths) -> None:
    """Refuse before cloning rather than let git merge into someone's work."""
    target = repo_path(repo, paths)
    if target.exists() and any(target.iterdir()):
        raise ProvisioningError("occupied", str(target))


def check_download_target(download: Download, paths: LabPaths) -> Path:
    """Refuse to replace a file that is already there, and say where it goes."""
    destination = getattr(paths, WEIGHT_DESTINATIONS[download.key])
    if destination.exists():
        raise ProvisioningError("present", str(destination))
    if not download.automatable:
        raise ProvisioningError("manual", download.url)
    return destination


def verify(path: Path, download: Download) -> bool:
    """Does the file on disk match the checksum this project published?

    Used both after an automated download and after somebody copies in a file
    by hand — a green tick has to mean the bytes are right, not that a file
    with the right name appeared.
    """
    if not path.is_file():
        return False
    if not download.sha256:
        return True
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest() == download.sha256


def stream_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    popener: Popener = subprocess.Popen,
    idle_timeout: float = IDLE_TIMEOUT_SECONDS,
    total_timeout: float = TOTAL_TIMEOUT_SECONDS,
    environ: Mapping[str, str] | None = None,
) -> Iterator[str]:
    """Run one command, yielding its output line by line.

    Two clocks, because they catch different failures. The idle timeout catches
    a process waiting on something that will never come — a credential prompt,
    a dead mirror. The total timeout catches one that is making progress far too
    slowly to be worth waiting for. Without the first, a prompt would hang the
    Gradio worker; without the second, a crawling download would look identical
    to a working one.
    """
    creation_flags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    )
    process = popener(
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(cwd),
        env={**os.environ, **GIT_ENVIRONMENT, **(environ or {})},
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creation_flags,
    )

    lines: Queue[str | None] = Queue()

    def pump() -> None:
        try:
            for line in process.stdout or ():
                lines.put(line)
        finally:
            lines.put(None)

    threading.Thread(target=pump, name="ai-music-provision", daemon=True).start()

    started = time.monotonic()
    try:
        while True:
            try:
                line = lines.get(timeout=idle_timeout)
            except Empty:
                process.kill()
                raise ProvisioningError(
                    "stalled",
                    f"no output for {idle_timeout:.0f} s",
                ) from None
            if line is None:
                break
            if time.monotonic() - started > total_timeout:
                process.kill()
                raise ProvisioningError(
                    "timeout",
                    f"still running after {total_timeout / 60:.0f} min",
                )
            text = line.rstrip()
            if text:
                yield text
        code = process.wait(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
    if code != 0:
        raise ProvisioningError("failed", f"exit code {code}")


def download_weight(
    download: Download,
    paths: LabPaths,
    *,
    opener: Callable[..., Any] | None = None,
    timeout: float = DOWNLOAD_TIMEOUT_SECONDS,
) -> Iterator[str]:
    """Fetch one checkpoint, verify it, and only then put it in place.

    Written to a neighbouring ``.part`` file and renamed at the end, so an
    interrupted download can never be mistaken for a complete one — the
    readiness check looks for the real name, and half a checkpoint that answers
    to it would fail much later and much more confusingly.
    """
    destination = check_download_target(download, paths)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    request = urllib.request.Request(
        download.url,
        headers={"User-Agent": "ai-music-lab"},
    )
    yield f"GET {download.url}"

    fetch = opener or urllib.request.urlopen
    written = 0
    with fetch(request, timeout=timeout) as response, partial.open("wb") as target:
        while True:
            block = response.read(1024 * 256)
            if not block:
                break
            target.write(block)
            written += len(block)
            if download.size_bytes and written % (1024 * 1024 * 8) < 1024 * 256:
                yield f"{written / download.size_bytes:.0%}"
    yield f"{written} bytes"

    if not verify(partial, download):
        partial.unlink(missing_ok=True)
        raise ProvisioningError("checksum", download.filename)
    partial.replace(destination)
    yield f"verified -> {destination}"


def agent_prompt(
    detector: str,
    step: str,
    paths: LabPaths,
    commands: Sequence[Sequence[str]],
    log: str = "",
) -> str:
    """The text to hand a coding agent when a step will not go through.

    An install that has failed twice is not going to succeed on the third
    identical attempt, and the honest next move is a tool that can read the
    error. This gives that tool everything it would otherwise have to be told:
    where the project is, what was being attempted, and what came back.
    """
    rendered = "\n".join(subprocess.list2cmdline(list(command)) for command in commands)
    tail = "\n".join(log.strip().splitlines()[-40:])
    return (
        f"I am setting up the AI Music Lab project at {paths.root} on "
        f"{sys.platform}. The '{step}' step for the {detector} detector fails "
        f"and I would like you to finish it.\n\n"
        f"Commands that were run:\n{rendered}\n\n"
        f"Output:\n{tail or '(no output)'}\n\n"
        "Please diagnose it, complete the step by whatever route works, and "
        "leave the result where the project expects it. The environment names "
        "and the paths above are what the app looks for — do not change them. "
        "The setup is documented in docs/getting-started.md and "
        "docs/agent-setup.md inside the project."
    )
