from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from scripts.bootstrap_macos import (
    BootstrapError,
    download_verified,
    verify_required_file,
    validate_clone_target,
    validate_existing_clone,
)


def test_required_checkpoint_returns_matching_digest(tmp_path: Path) -> None:
    path = tmp_path / "Stage.ckpt"
    path.write_bytes(b"checkpoint")
    expected = hashlib.sha256(b"checkpoint").hexdigest()

    assert verify_required_file(path, expected) == expected


def test_required_checkpoint_rejects_missing_bytes(tmp_path: Path) -> None:
    with pytest.raises(BootstrapError, match="missing required file"):
        verify_required_file(tmp_path / "missing.ckpt", "0" * 64)


def test_required_checkpoint_rejects_wrong_bytes_without_replacing_them(
    tmp_path: Path,
) -> None:
    path = tmp_path / "wrong.ckpt"
    path.write_bytes(b"wrong")

    with pytest.raises(BootstrapError, match="checksum"):
        verify_required_file(path, "0" * 64)

    assert path.read_bytes() == b"wrong"


def init_repository(path: Path) -> str:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Bootstrap Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
    )
    (path / "tracked.txt").write_text("known\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "tracked.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-qm", "fixture"], check=True
    )
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_nonempty_non_git_clone_target_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "occupied"
    target.mkdir()
    (target / "mine.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(BootstrapError, match="not an existing Git clone"):
        validate_clone_target(target)

    assert (target / "mine.txt").read_text(encoding="utf-8") == "keep"


def test_clean_clone_at_expected_commit_is_accepted(tmp_path: Path) -> None:
    target = tmp_path / "upstream"
    commit = init_repository(target)

    assert validate_existing_clone(target, commit) == commit


def test_dirty_clone_is_refused_without_modifying_it(tmp_path: Path) -> None:
    target = tmp_path / "upstream"
    commit = init_repository(target)
    tracked = target / "tracked.txt"
    tracked.write_text("my local change\n", encoding="utf-8")

    with pytest.raises(BootstrapError, match="uncommitted changes"):
        validate_existing_clone(target, commit)

    assert tracked.read_text(encoding="utf-8") == "my local change\n"


def test_existing_matching_file_is_accepted(tmp_path: Path) -> None:
    destination = tmp_path / "model.onnx"
    destination.write_bytes(b"known")

    download_verified(
        "https://invalid.example/model",
        destination,
        hashlib.sha256(b"known").hexdigest(),
    )

    assert destination.read_bytes() == b"known"


def test_existing_wrong_file_is_never_replaced(tmp_path: Path) -> None:
    destination = tmp_path / "model.onnx"
    destination.write_bytes(b"mine")

    with pytest.raises(BootstrapError, match="checksum"):
        download_verified(
            "https://invalid.example/model",
            destination,
            hashlib.sha256(b"expected").hexdigest(),
        )

    assert destination.read_bytes() == b"mine"


def test_download_is_verified_before_it_becomes_visible(tmp_path: Path) -> None:
    source = tmp_path / "source.onnx"
    destination = tmp_path / "models" / "model.onnx"
    source.write_bytes(b"downloaded bytes")

    download_verified(
        source.as_uri(),
        destination,
        hashlib.sha256(b"downloaded bytes").hexdigest(),
    )

    assert destination.read_bytes() == b"downloaded bytes"
    assert not destination.with_name(destination.name + ".part").exists()
