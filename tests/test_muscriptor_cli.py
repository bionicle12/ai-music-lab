"""The adapter runs in its own environment; only its pure half is tested here.

Which is also the point of the first test: if a heavy import ever leaks to
module scope, the UI environment stops being able to import this file at all.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from adapters.muscriptor_cli import (
    MODEL_SIZES,
    build_parser,
    classify_error,
    classify_http_error,
    directory_bytes,
    emit,
    parse_instruments,
    repo_id,
    weights_url,
)


def test_the_adapter_imports_without_muscriptor_or_torch() -> None:
    """Reaching this line at all is the assertion — the import is at the top."""
    assert MODEL_SIZES == ("small", "medium", "large")


def test_repo_ids_follow_the_published_naming() -> None:
    assert repo_id("large") == "MuScriptor/muscriptor-large"
    assert weights_url("small") == (
        "hf://MuScriptor/muscriptor-small/model.safetensors"
    )
    with pytest.raises(ValueError):
        repo_id("enormous")


def test_instrument_lists_tolerate_human_typing() -> None:
    assert parse_instruments("drums, acoustic_piano") == ["drums", "acoustic_piano"]
    assert parse_instruments(" , ,") is None
    assert parse_instruments("") is None
    assert parse_instruments(None) is None


@pytest.mark.parametrize(
    ("status", "message", "expected"),
    [
        (401, "Unauthorized", "token_missing"),
        (403, "Access to model is gated", "gated_repo"),
        (403, "Forbidden", "token_scope"),
        (404, "Repo not found", "repo_missing"),
        (None, "Failed to resolve host huggingface.co", "offline"),
        (500, "Internal error", "http_error"),
    ],
)
def test_http_failures_map_to_stable_codes(status, message, expected) -> None:
    assert classify_http_error(status, message) == expected


def test_local_failures_map_to_stable_codes() -> None:
    assert classify_error(ModuleNotFoundError("muscriptor")) == "package_missing"
    assert classify_error(FileNotFoundError("audio.wav")) == "file_missing"
    assert classify_error(RuntimeError("CUDA out of memory")) == "cuda_oom"

    class GatedRepoError(Exception):
        pass

    assert classify_error(GatedRepoError("no access")) == "gated_repo"


def test_transcribe_mode_demands_an_audio_file_and_a_destination() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["--mode", "transcribe", "--json-output", "out.json"]
    )
    from adapters.muscriptor_cli import validate

    with pytest.raises(SystemExit):
        validate(args, parser)


def test_the_default_model_is_the_one_the_interface_preselects() -> None:
    args = build_parser().parse_args(["--mode", "probe", "--json-output", "o.json"])

    assert args.model == "large"
    assert args.beam_size == 1  # greedy: same input, same parameters, same output
    assert not hasattr(args, "token")


def test_events_are_one_json_object_per_line() -> None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        emit("progress", stage="download", fraction=0.5)
        emit("result", payload={"mode": "probe"})
    lines = buffer.getvalue().strip().splitlines()

    assert [json.loads(line)["event"] for line in lines] == ["progress", "result"]


def test_directory_size_ignores_a_missing_directory(tmp_path: Path) -> None:
    assert directory_bytes(tmp_path / "nothing") == 0

    (tmp_path / "blobs").mkdir()
    (tmp_path / "blobs" / "part.incomplete").write_bytes(b"x" * 128)

    assert directory_bytes(tmp_path) == 128
