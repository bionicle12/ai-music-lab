import sys
from dataclasses import replace
from pathlib import Path

import pytest

from music_lab_ui.config import LabPaths
from music_lab_ui.detectors import run_fst, run_lofcz


def base_paths(tmp_path: Path) -> LabPaths:
    root = tmp_path / "ai-music-lab"
    root.mkdir()
    paths = LabPaths.from_root(root)
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"audio")
    for path in (paths.lofcz_model, paths.fst_stage1, paths.fst_stage2):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"model")
    lofcz_python_dir = paths.lofcz_upstream / "src" / "python"
    lofcz_python_dir.mkdir(parents=True)
    (lofcz_python_dir / "inference.py").write_text("", encoding="utf-8")
    paths.fst_upstream.mkdir()
    for name in ("model.py", "inference.py", "preprocess.py"):
        (paths.fst_upstream / name).write_text("", encoding="utf-8")
    return paths


def test_run_lofcz_normalizes_real_csv_subprocess(tmp_path: Path) -> None:
    paths = base_paths(tmp_path)
    script = tmp_path / "fake_lofcz.py"
    script.write_text(
        """
import argparse
import json
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--upstream")
parser.add_argument("--model")
parser.add_argument("--audio")
parser.add_argument("--json-output")
parser.add_argument("--npz-output")
args = parser.parse_args()
np.savez_compressed(
    args.npz_output,
    frequency_hz=np.array([1000, 2000], dtype=np.float32),
    fakeprint=np.array([0.2, 0.8], dtype=np.float32),
)
with open(args.json_output, "w", encoding="utf-8") as target:
    json.dump({
        "probability": "0.625",
        "is_ai": "True",
        "label": "AI-Generated",
        "confidence": 0.25,
        "telemetry": {
            "detector": "lofcz",
            "scalars": {"n_fft": 8192},
            "warnings": [],
        },
    }, target)
""".strip(),
        encoding="utf-8",
    )
    paths = replace(
        paths, lofcz_python=Path(sys.executable), lofcz_adapter=script
    )

    result = run_lofcz(tmp_path / "input.wav", paths)

    assert result.detector == "lofcz"
    assert result.status == "ok"
    assert result.probability == 0.625
    assert result.confidence == 0.25
    assert result.label == "AI-Generated"
    assert result.raw["telemetry"]["arrays"]["fakeprint"] == pytest.approx(
        [0.2, 0.8]
    )


def test_run_fst_maps_no_segments_to_not_applicable(tmp_path: Path) -> None:
    paths = base_paths(tmp_path)
    script = tmp_path / "fake_fst.py"
    script.write_text(
        """
import sys

print("FST preprocessing found no beat-aligned segments", file=sys.stderr)
raise SystemExit(1)
""".strip(),
        encoding="utf-8",
    )
    paths = replace(paths, fst_python=Path(sys.executable), fst_adapter=script)

    result = run_fst(tmp_path / "input.wav", paths)

    assert result.status == "not_applicable"
    assert result.probability is None
    assert "no beat-aligned segments" in result.error


def test_run_fst_rejects_non_finite_probability(tmp_path: Path) -> None:
    paths = base_paths(tmp_path)
    script = tmp_path / "fake_fst_nan.py"
    script.write_text(
        """
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("--upstream")
parser.add_argument("--stage1")
parser.add_argument("--stage2")
parser.add_argument("--audio")
parser.add_argument("--json-output")
parser.add_argument("--npz-output")
args = parser.parse_args()
with open(args.json_output, "w", encoding="utf-8") as target:
    json.dump({
        "prediction": "Real",
        "confidence": "nan",
        "fake_probability": "nan",
        "real_probability": "nan",
        "device": "test",
    }, target)
""".strip(),
        encoding="utf-8",
    )
    paths = replace(paths, fst_python=Path(sys.executable), fst_adapter=script)

    result = run_fst(tmp_path / "input.wav", paths)

    assert result.status == "error"
    assert result.probability is None
    assert "non-finite" in result.error
