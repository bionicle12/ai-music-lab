from pathlib import Path
import sys

import numpy as np
import pytest

from music_lab_ui import detectors

from adapters import fst_cli
from adapters.fst_cli import (
    DEFAULT_BACKBONE_BATCH,
    DetectorPaths,
    build_parser,
    mean_fusion_gate,
    self_similarity_matrix,
    stage1_class_probabilities,
    upstream_import_context,
    validate_paths,
    validate_segments,
)


def test_validate_paths_accepts_complete_layout(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    for name in ("model.py", "inference.py", "preprocess.py"):
        (upstream / name).write_text("", encoding="utf-8")
    stage1 = tmp_path / "Stage-1.ckpt"
    stage2 = tmp_path / "Stage-2.ckpt"
    audio = tmp_path / "stem.wav"
    for path in (stage1, stage2, audio):
        path.write_bytes(b"x")

    validate_paths(DetectorPaths(upstream, stage1, stage2, audio))


def test_validate_paths_lists_every_missing_input(tmp_path: Path) -> None:
    paths = DetectorPaths(
        tmp_path / "upstream",
        tmp_path / "Stage-1.ckpt",
        tmp_path / "Stage-2.ckpt",
        tmp_path / "stem.wav",
    )

    with pytest.raises(FileNotFoundError) as error:
        validate_paths(paths)

    message = str(error.value)
    assert "upstream/model.py" in message.replace("\\", "/")
    assert "Stage-1.ckpt" in message
    assert "Stage-2.ckpt" in message
    assert "stem.wav" in message


def test_validate_segments_rejects_fully_masked_audio() -> None:
    torch = pytest.importorskip("torch")

    with pytest.raises(RuntimeError, match="no beat-aligned segments"):
        validate_segments(torch.ones(1, dtype=torch.bool))


def test_upstream_import_context_restores_python_state(tmp_path: Path) -> None:
    original_flag = sys.dont_write_bytecode
    original_path = list(sys.path)

    with upstream_import_context(tmp_path):
        assert sys.path[0] == str(tmp_path.resolve())
        assert sys.dont_write_bytecode is True

    assert sys.dont_write_bytecode is original_flag
    assert sys.path == original_path


def test_stage1_probabilities_preserve_both_native_classes() -> None:
    probabilities = stage1_class_probabilities(
        np.array([[0.0, 1.0], [2.0, -1.0]], dtype=np.float32)
    )

    assert probabilities.shape == (2, 2)
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert probabilities[0, 1] > probabilities[0, 0]


def test_self_similarity_matches_stage2_expression() -> None:
    embeddings = np.array([[0.0, 0.0], [1.0, 1.0]], dtype=np.float32)

    similarity = self_similarity_matrix(embeddings)

    assert np.diag(similarity) == pytest.approx([1.0, 1.0])
    assert similarity[0, 1] == pytest.approx(np.exp(-1.0))


def test_mean_fusion_gate_ignores_padded_segments() -> None:
    gates = np.array(
        [[[0.2, 0.4], [0.8, 1.0], [0.0, 0.0]]],
        dtype=np.float32,
    )

    means = mean_fusion_gate(gates, valid_segments=2)

    assert means == pytest.approx([0.3, 0.9])


def test_backbone_batch_defaults_to_eight_not_to_the_upstream_batch() -> None:
    """Upstream sends all 48 segments through the backbone at once and peaks at
    16 GB of VRAM, which is more than most cards have. Measured on three tracks,
    eights peak at 4.8 GB in the same time."""
    parsed = build_parser().parse_args(
        ["--upstream", "u", "--stage1", "a", "--stage2", "b", "--audio", "c"]
    )

    assert parsed.backbone_batch == DEFAULT_BACKBONE_BATCH == 8


def test_the_upstream_batch_is_still_reachable() -> None:
    """Zero means "all of them", so a run can be reproduced exactly as upstream
    would have done it."""
    parsed = build_parser().parse_args(
        [
            "--upstream", "u", "--stage1", "a", "--stage2", "b", "--audio", "c",
            "--backbone-batch", "0",
        ]
    )

    assert parsed.backbone_batch == 0


def test_the_run_records_which_batch_size_produced_it() -> None:
    """The batch size can move the raw logit by one float16 ulp, so a saved
    score that cannot say which one it used is not reproducible."""
    source = Path(fst_cli.__file__).read_text(encoding="utf-8")

    assert '"backbone_batch": step' in source


def test_the_interface_passes_the_batch_size_explicitly() -> None:
    """Relying on the adapter default would leave the value out of the command
    line, and the command line is what documents a run."""
    source = Path(detectors.__file__).read_text(encoding="utf-8")

    assert "--backbone-batch" in source
    assert detectors.FST_BACKBONE_BATCH == DEFAULT_BACKBONE_BATCH
