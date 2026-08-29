"""Create the project-local macOS environments and pristine upstream clones."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


class BootstrapError(RuntimeError):
    """A safe bootstrap precondition or operation failed."""


@dataclass(frozen=True)
class RepositorySpec:
    folder: str
    url: str
    commit: str


REPOSITORIES = (
    RepositorySpec(
        "ai-music-detector",
        "https://github.com/lofcz/ai-music-detector.git",
        "6ba389e94a179ac90f3eb134b741ef37baa30434",
    ),
    RepositorySpec(
        "FST-AI-Music-Detection",
        "https://github.com/Mippia/FST-AI-Music-Detection.git",
        "b564f8be8b3db6b7810c2aab61f0b4f86f889579",
    ),
)

LOFCZ_MODEL_URL = (
    "https://huggingface.co/lofcz/ai-music-detector/resolve/main/"
    "ai_music_detector.onnx?download=true"
)
LOFCZ_MODEL_SHA256 = (
    "af7a75c6ed457bc5b6941c8bc76aa06a66d48de40db944b761ed2bebfc0fbbd3"
)
FST_STAGE1_SHA256 = (
    "f9099df5c618a2f92bcd8f4ba48d1c6606f2e4610385b8eea4a03f1a7319629f"
)
FST_STAGE2_SHA256 = (
    "ed133c261c5d367fc6adf53813a5c93b62a59de5bef546cf5899a5c157eba7a0"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_required_file(path: Path, expected_sha256: str) -> str:
    target = Path(path)
    if not target.is_file():
        raise BootstrapError(f"missing required file: {target}")
    actual = sha256(target)
    if actual != expected_sha256:
        raise BootstrapError(
            f"checksum mismatch for required {target}: {actual}"
        )
    return actual


def run(argv: Sequence[str], cwd: Path | None = None) -> None:
    rendered = " ".join(str(item) for item in argv)
    print(f"+ {rendered}", flush=True)
    subprocess.run(
        [str(item) for item in argv],
        cwd=str(cwd) if cwd else None,
        check=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def git_output(path: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return completed.stdout.strip()


def validate_clone_target(path: Path) -> None:
    target = Path(path)
    if not target.exists() or not any(target.iterdir()):
        return
    try:
        git_output(target, "rev-parse", "--git-dir")
    except (OSError, subprocess.CalledProcessError) as error:
        raise BootstrapError(
            f"refusing occupied target {target}: not an existing Git clone"
        ) from error


def validate_existing_clone(path: Path, commit: str) -> str:
    target = Path(path)
    try:
        git_output(target, "rev-parse", "--git-dir")
        status = git_output(
            target,
            "status",
            "--porcelain",
            "--untracked-files=all",
        )
        dirty = "\n".join(
            line
            for line in status.splitlines()
            if not (
                line.startswith("?? ")
                and Path(line[3:]).name == ".DS_Store"
            )
        )
        head = git_output(target, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError) as error:
        raise BootstrapError(f"{target} is not an existing Git clone") from error
    if dirty:
        raise BootstrapError(f"{target} has uncommitted changes; leaving it untouched")
    if head != commit:
        raise BootstrapError(
            f"{target} is at {head}, expected {commit}; leaving it untouched"
        )
    return head


def download_verified(url: str, destination: Path, expected_sha256: str) -> None:
    target = Path(destination)
    if target.exists():
        actual = sha256(target)
        if actual != expected_sha256:
            raise BootstrapError(
                f"checksum mismatch for existing {target}: {actual}"
            )
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    if partial.exists():
        partial.unlink()
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            with partial.open("wb") as handle:
                shutil.copyfileobj(response, handle, length=1024 * 1024)
        actual = sha256(partial)
        if actual != expected_sha256:
            raise BootstrapError(
                f"checksum mismatch for downloaded {target}: {actual}"
            )
        os.replace(partial, target)
    finally:
        if partial.exists():
            partial.unlink()


def prepare_repository(spec: RepositorySpec, parent: Path) -> str:
    target = Path(parent) / spec.folder
    validate_clone_target(target)
    if target.exists() and any(target.iterdir()):
        return validate_existing_clone(target, spec.commit)
    run(["git", "clone", spec.url, str(target)])
    run(["git", "checkout", "--detach", spec.commit], cwd=target)
    return validate_existing_clone(target, spec.commit)


def ensure_environment(
    project_root: Path,
    environment: str,
    requirements: str,
) -> Path:
    python = project_root / environment / "bin" / "python"
    if not python.is_file():
        run([sys.executable, "-m", "venv", str(project_root / environment)])
    run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "-r",
            str(project_root / "environments" / requirements),
        ]
    )
    return python


def require_host() -> None:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise BootstrapError("this bootstrap targets Apple Silicon macOS")
    if sys.version_info[:2] != (3, 11):
        raise BootstrapError(
            f"Python 3.11 is required, got {platform.python_version()}"
        )
    if shutil.which("git") is None:
        raise BootstrapError("Git is required but was not found on PATH")


def main() -> int:
    try:
        require_host()
        root = Path(__file__).resolve().parent.parent
        parent = root.parent
        ui_python = ensure_environment(
            root, ".venv-ui", "ai-music-ui-macos.txt"
        )
        lofcz_python = ensure_environment(
            root, ".venv-lofcz", "ai-music-lofcz-macos.txt"
        )
        fst_python = ensure_environment(
            root, ".venv-fst", "ai-music-fst-macos.txt"
        )
        run(
            [
                str(fst_python),
                "-c",
                (
                    "import torch; "
                    "assert torch.__version__.startswith('2.8.'); "
                    "assert torch.backends.mps.is_available()"
                ),
            ]
        )
        heads = {
            spec.folder: prepare_repository(spec, parent) for spec in REPOSITORIES
        }
        model = root / "models" / "lofcz" / "ai_music_detector.onnx"
        download_verified(LOFCZ_MODEL_URL, model, LOFCZ_MODEL_SHA256)
        fst_stage1 = root / "models" / "fst" / "Stage-1.ckpt"
        fst_stage2 = root / "models" / "fst" / "Stage-2.ckpt"
        fst_stage1_hash = verify_required_file(fst_stage1, FST_STAGE1_SHA256)
        fst_stage2_hash = verify_required_file(fst_stage2, FST_STAGE2_SHA256)
        print("\nmacOS bootstrap complete")
        print(f"UI Python:    {ui_python}")
        print(f"lofcz Python: {lofcz_python}")
        print(f"FST Python:   {fst_python}")
        for folder, head in heads.items():
            print(f"{folder}: {head}")
        print(f"lofcz model: {sha256(model)}")
        print(f"FST Stage-1: {fst_stage1_hash}")
        print(f"FST Stage-2: {fst_stage2_hash}")
        print("Next: ./start_ui.sh")
        return 0
    except (BootstrapError, OSError, subprocess.CalledProcessError) as error:
        print(f"bootstrap failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
