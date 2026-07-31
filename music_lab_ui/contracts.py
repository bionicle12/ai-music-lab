from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class AudioMetadata:
    filename: str
    suffix: str
    size_bytes: int
    sample_rate: int
    channels: int
    frames: int
    duration_seconds: float
    sha256: str


@dataclass(frozen=True)
class AudioMetrics:
    peak_dbfs: float
    rms_dbfs: float
    crest_factor_db: float
    stereo_correlation: float | None
    mid_side_ratio_db: float | None


@dataclass(frozen=True)
class AudioFeatures:
    metadata: AudioMetadata
    metrics: AudioMetrics
    time_axis: np.ndarray
    frequency_axis: np.ndarray
    spectrogram_db: np.ndarray
    waveform_rms_db: np.ndarray
    average_spectrum_db: np.ndarray
    analysis_settings: dict[str, int | float] = field(default_factory=dict)


@dataclass(frozen=True)
class DetectorResult:
    detector: str
    status: str
    probability: float | None
    label: str
    confidence: float | None
    runtime_seconds: float
    device: str | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LayerResult:
    """One stem or layer in a diagnostic sweep — not a saved version."""

    name: str
    status: str
    probability: float | None
    mean_residue_db: float | None
    duration_seconds: float | None
    error: str | None = None


@dataclass(frozen=True)
class AnalysisRun:
    run_id: str
    created_at: str
    filename: str
    audio_path: Path
    features_path: Path
    result_path: Path
    note: str
    selected_detectors: tuple[str, ...]
    results: tuple[DetectorResult, ...]
    is_baseline: bool
