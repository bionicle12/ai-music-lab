from __future__ import annotations

import json
import math
import subprocess
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .config import LabPaths
from .contracts import DetectorResult
from .i18n import Translator, get_translator

ProgressCallback = Callable[[str, float], None]

#: Segments per FST backbone pass. Upstream sends all 48 at once and peaks at
#: 16 GB of VRAM, which is more than most cards have; in eights the same run
#: peaks at 4.8 GB in the same time. Kept here rather than left to the adapter
#: default so the value appears in the command that produced the score.
FST_BACKBONE_BATCH = 8


def _error_result(
    detector: str,
    message: str,
    runtime_seconds: float,
    raw: dict | None = None,
    status: str = "error",
    t: Translator | None = None,
) -> DetectorResult:
    translate = t or get_translator()
    return DetectorResult(
        detector=detector,
        status=status,
        probability=None,
        label=(
            translate("status.not_applicable")
            if status == "not_applicable"
            else translate("status.error")
        ),
        confidence=None,
        runtime_seconds=runtime_seconds,
        error=message,
        raw=raw or {},
    )


def _finite_probability(value: object) -> float:
    probability = float(value)
    if not math.isfinite(probability):
        raise ValueError("detector returned a non-finite probability")
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"detector probability is outside [0, 1]: {probability}")
    return probability


def run_lofcz(
    audio: Path,
    paths: LabPaths,
    t: Translator | None = None,
) -> DetectorResult:
    translate = t or get_translator()
    started = time.perf_counter()
    required = (
        audio,
        paths.lofcz_python,
        paths.lofcz_adapter,
        paths.lofcz_model,
        paths.lofcz_upstream / "src" / "python" / "inference.py",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        return _error_result(
            "lofcz", "missing files: " + ", ".join(missing), 0.0, t=translate
        )

    with tempfile.TemporaryDirectory(prefix="ai-music-lofcz-") as temp_dir:
        output = Path(temp_dir) / "result.json"
        arrays_output = Path(temp_dir) / "telemetry.npz"
        completed = subprocess.run(
            [
                str(paths.lofcz_python),
                str(paths.lofcz_adapter),
                "--upstream",
                str(paths.lofcz_upstream),
                "--model",
                str(paths.lofcz_model),
                "--audio",
                str(audio),
                "--json-output",
                str(output),
                "--npz-output",
                str(arrays_output),
            ],
            cwd=paths.root,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        runtime = time.perf_counter() - started
        logs = {"stdout": completed.stdout, "stderr": completed.stderr}
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            return _error_result("lofcz", message, runtime, logs, t=translate)
        try:
            payload = json.loads(output.read_text(encoding="utf-8"))
            probability = _finite_probability(payload["probability"])
            with np.load(arrays_output, allow_pickle=False) as source:
                telemetry_arrays = {
                    name: source[name].tolist() for name in source.files
                }
            telemetry = {
                **payload["telemetry"],
                "arrays": telemetry_arrays,
            }
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return _error_result("lofcz", str(error), runtime, logs, t=translate)
        return DetectorResult(
            detector="lofcz",
            status="ok",
            probability=probability,
            label=payload.get("label") or (
                "AI-Generated" if probability >= 0.5 else "Real Music"
            ),
            confidence=float(
                payload.get("confidence", abs(probability - 0.5) * 2.0)
            ),
            runtime_seconds=runtime,
            device="CUDA feature extraction / ONNX",
            raw={**logs, "payload": payload, "telemetry": telemetry},
        )


def run_lofcz_timeline(
    audio: Path,
    paths: LabPaths,
    *,
    window_seconds: float = 15.0,
    hop_seconds: float = 5.0,
) -> dict:
    """Sliding-window lofcz scan; returns the payload with its telemetry block.

    Runs the detector again over the same audio but does not create a new run —
    the map is telemetry about an existing version, not a new measurement of it.
    """
    if window_seconds <= 0 or hop_seconds <= 0:
        raise ValueError(get_translator()("error.window_positive"))
    required = (
        audio,
        paths.lofcz_python,
        paths.lofcz_adapter,
        paths.lofcz_model,
        paths.lofcz_upstream / "src" / "python" / "inference.py",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(
            get_translator()("error.files_missing", files=", ".join(missing))
        )

    with tempfile.TemporaryDirectory(prefix="ai-music-timeline-") as temp_dir:
        output = Path(temp_dir) / "timeline.json"
        arrays_output = Path(temp_dir) / "timeline.npz"
        completed = subprocess.run(
            [
                str(paths.lofcz_python),
                str(paths.lofcz_adapter),
                "--upstream",
                str(paths.lofcz_upstream),
                "--model",
                str(paths.lofcz_model),
                "--audio",
                str(audio),
                "--mode",
                "timeline",
                "--window-seconds",
                str(window_seconds),
                "--hop-seconds",
                str(hop_seconds),
                "--json-output",
                str(output),
                "--npz-output",
                str(arrays_output),
            ],
            cwd=paths.root,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                completed.stderr.strip() or completed.stdout.strip() or "lofcz timeline failed"
            )
        payload = json.loads(output.read_text(encoding="utf-8"))
        with np.load(arrays_output, allow_pickle=False) as source:
            arrays = {name: source[name].tolist() for name in source.files}
        payload["telemetry"] = {**payload["telemetry"], "arrays": arrays}
        return payload


def run_fst(
    audio: Path,
    paths: LabPaths,
    t: Translator | None = None,
    backbone_batch: int = FST_BACKBONE_BATCH,
) -> DetectorResult:
    translate = t or get_translator()
    started = time.perf_counter()
    required = (
        audio,
        paths.fst_python,
        paths.fst_adapter,
        paths.fst_stage1,
        paths.fst_stage2,
        paths.fst_upstream / "model.py",
        paths.fst_upstream / "inference.py",
        paths.fst_upstream / "preprocess.py",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        return _error_result(
            "FST", "missing files: " + ", ".join(missing), 0.0, t=translate
        )

    with tempfile.TemporaryDirectory(prefix="ai-music-fst-") as temp_dir:
        output = Path(temp_dir) / "result.json"
        arrays_output = Path(temp_dir) / "telemetry.npz"
        completed = subprocess.run(
            [
                str(paths.fst_python),
                str(paths.fst_adapter),
                "--upstream",
                str(paths.fst_upstream),
                "--stage1",
                str(paths.fst_stage1),
                "--stage2",
                str(paths.fst_stage2),
                "--audio",
                str(audio),
                "--json-output",
                str(output),
                "--npz-output",
                str(arrays_output),
                "--backbone-batch",
                str(backbone_batch),
            ],
            cwd=paths.root,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        runtime = time.perf_counter() - started
        logs = {"stdout": completed.stdout, "stderr": completed.stderr}
        combined = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            if "no beat-aligned segments" in combined:
                return _error_result(
                    "FST",
                    message,
                    runtime,
                    logs,
                    status="not_applicable",
                    t=translate,
                )
            return _error_result("FST", message, runtime, logs, t=translate)
        try:
            payload = json.loads(output.read_text(encoding="utf-8"))
            probability = _finite_probability(payload["fake_probability"])
            confidence = float(payload.get("confidence", 0.0))
            if confidence > 1.0:
                confidence /= 100.0
            if not math.isfinite(confidence):
                raise ValueError("detector returned a non-finite confidence")
            with np.load(arrays_output, allow_pickle=False) as source:
                telemetry_arrays = {
                    name: source[name].tolist() for name in source.files
                }
            telemetry = {
                **payload["telemetry"],
                "arrays": telemetry_arrays,
            }
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return _error_result("FST", str(error), runtime, logs, t=translate)
        return DetectorResult(
            detector="FST",
            status="ok",
            probability=probability,
            label=str(payload.get("prediction", "Unknown")),
            confidence=confidence,
            runtime_seconds=runtime,
            device=payload.get("device"),
            raw={**logs, "payload": payload, "telemetry": telemetry},
        )


def run_selected(
    audio: Path,
    selected: list[str],
    paths: LabPaths,
    progress: ProgressCallback | None = None,
    t: Translator | None = None,
    options: Mapping[str, Any] | None = None,
) -> list[DetectorResult]:
    """``options`` carries the user's per-detector settings.

    A plain mapping rather than ``LabSettings``: this module reads settings, it
    does not own them, and taking the whole object would let a detector reach
    for the Hugging Face token that sits in the same dataclass.
    """
    translate = t or get_translator()
    chosen = dict(options or {})
    callbacks: dict[str, Callable[..., DetectorResult]] = {
        "lofcz": run_lofcz,
        "FST": lambda audio, paths, translate: run_fst(
            audio,
            paths,
            translate,
            backbone_batch=int(
                chosen.get("fst_backbone_batch", FST_BACKBONE_BATCH)
            ),
        ),
    }
    results: list[DetectorResult] = []
    total = max(len(selected), 1)
    for index, detector in enumerate(selected):
        if detector not in callbacks:
            results.append(_error_result(detector, "unknown detector", 0.0, t=translate))
            continue
        if progress:
            progress(translate("progress.detector", detector=detector), index / total)
        results.append(callbacks[detector](audio, paths, translate))
    if progress:
        progress(translate("progress.detectors_done"), 1.0)
    return results
