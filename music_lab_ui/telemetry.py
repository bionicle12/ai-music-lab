from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class DetectorTelemetry:
    detector: str
    scalars: dict[str, Any]
    arrays: dict[str, np.ndarray]
    warnings: tuple[str, ...] = ()


def validate_telemetry(payload: dict[str, Any]) -> DetectorTelemetry:
    detector = str(payload.get("detector", "")).strip()
    if not detector:
        raise ValueError("telemetry detector is required")
    arrays: dict[str, np.ndarray] = {}
    for name, values in dict(payload.get("arrays", {})).items():
        array = np.asarray(values)
        if array.dtype.kind not in "biuf":
            raise ValueError(f"telemetry array {name} must be numeric")
        if not np.isfinite(array).all():
            raise ValueError(f"telemetry array {name} must contain finite values")
        arrays[str(name)] = array.copy()
    scalars = dict(payload.get("scalars", {}))
    json.dumps(scalars, ensure_ascii=False)
    warnings = tuple(str(item) for item in payload.get("warnings", ()))
    return DetectorTelemetry(
        detector=detector,
        scalars=scalars,
        arrays=arrays,
        warnings=warnings,
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

