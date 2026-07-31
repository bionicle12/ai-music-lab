from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .contracts import AudioFeatures
from .i18n import Translator, get_translator


@dataclass(frozen=True)
class FeatureComparison:
    current: AudioFeatures
    baseline: AudioFeatures
    spectrogram_delta_db: np.ndarray
    waveform_delta_db: np.ndarray
    spectrum_delta_db: np.ndarray
    metric_rows: list[dict[str, float | str | None]]


def _row(
    name: str,
    current: float | None,
    baseline: float | None,
    unit: str,
) -> dict[str, float | str | None]:
    delta = None if current is None or baseline is None else current - baseline
    return {
        "metric": name,
        "current": current,
        "baseline": baseline,
        "delta": delta,
        "unit": unit,
    }


def _resample_1d(
    values: np.ndarray,
    source_axis: np.ndarray,
    target_axis: np.ndarray,
) -> np.ndarray:
    return np.interp(target_axis, source_axis, values).astype(np.float32)


def _resample_spectrogram(
    values: np.ndarray,
    source_frequencies: np.ndarray,
    source_times: np.ndarray,
    target_frequencies: np.ndarray,
    target_times: np.ndarray,
) -> np.ndarray:
    time_aligned = np.vstack(
        [np.interp(target_times, source_times, row) for row in values]
    )
    return np.column_stack(
        [
            np.interp(target_frequencies, source_frequencies, time_aligned[:, index])
            for index in range(time_aligned.shape[1])
        ]
    ).astype(np.float32)


def compare_features(
    current: AudioFeatures,
    baseline: AudioFeatures,
    t: Translator | None = None,
) -> FeatureComparison:
    translate = t or get_translator()
    baseline_duration = max(baseline.metadata.duration_seconds, 1e-9)
    duration_difference = abs(
        current.metadata.duration_seconds - baseline.metadata.duration_seconds
    ) / baseline_duration
    if duration_difference > 0.05:
        raise ValueError("duration differs by more than 5%")

    rows = [
        _row(
            translate("meta.duration"),
            current.metadata.duration_seconds,
            baseline.metadata.duration_seconds,
            translate("unit.seconds"),
        ),
        _row(
            "Peak",
            current.metrics.peak_dbfs,
            baseline.metrics.peak_dbfs,
            "dBFS",
        ),
        _row(
            "RMS",
            current.metrics.rms_dbfs,
            baseline.metrics.rms_dbfs,
            "dBFS",
        ),
        _row(
            "Crest factor",
            current.metrics.crest_factor_db,
            baseline.metrics.crest_factor_db,
            "dB",
        ),
        _row(
            "Stereo correlation",
            current.metrics.stereo_correlation,
            baseline.metrics.stereo_correlation,
            "",
        ),
        _row(
            "Mid / Side",
            current.metrics.mid_side_ratio_db,
            baseline.metrics.mid_side_ratio_db,
            "dB",
        ),
    ]

    baseline_spectrogram = _resample_spectrogram(
        baseline.spectrogram_db,
        baseline.frequency_axis,
        baseline.time_axis,
        current.frequency_axis,
        current.time_axis,
    )
    baseline_waveform = _resample_1d(
        baseline.waveform_rms_db,
        baseline.time_axis,
        current.time_axis,
    )
    baseline_spectrum = _resample_1d(
        baseline.average_spectrum_db,
        baseline.frequency_axis,
        current.frequency_axis,
    )

    return FeatureComparison(
        current=current,
        baseline=baseline,
        spectrogram_delta_db=(
            current.spectrogram_db - baseline_spectrogram
        ).astype(np.float32),
        waveform_delta_db=(
            current.waveform_rms_db - baseline_waveform
        ).astype(np.float32),
        spectrum_delta_db=(
            current.average_spectrum_db - baseline_spectrum
        ).astype(np.float32),
        metric_rows=rows,
    )
