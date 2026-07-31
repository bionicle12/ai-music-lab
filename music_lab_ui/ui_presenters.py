from __future__ import annotations

import html
from dataclasses import asdict
from typing import Any

from collections.abc import Sequence

from .artifact_metrics import ArtifactMetrics
from .contracts import AnalysisRun, AudioFeatures, DetectorResult, LayerResult
from .i18n import Translator, get_translator
from .telemetry import DetectorTelemetry
from .ui_service import AnalysisOutcome, RunComparisonOutcome


def _format_number(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _score_status(result: DetectorResult, t: Translator) -> tuple[str, str]:
    if result.status == "not_applicable":
        return t("status.not_applicable"), "result-warning"
    if result.status != "ok" or result.probability is None:
        return t("status.error"), "result-error"
    if result.probability >= 0.75:
        return t("status.high"), "result-high"
    if result.probability >= 0.4:
        return t("status.medium"), "result-medium"
    return t("status.low"), "result-low"


def _detector_caveat(result: DetectorResult, t: Translator) -> str:
    if result.detector == "FST" and result.probability is not None:
        if abs(result.probability - 0.011) <= 0.0005:
            return t("caveat.fst.floor")
        if abs(result.probability - 0.989) <= 0.0005:
            return t("caveat.fst.ceiling")
        return t("caveat.fst.general")
    if result.detector == "lofcz":
        return t("caveat.lofcz")
    return result.error or t("caveat.generic")


def detector_cards(
    results: tuple[DetectorResult, ...],
    t: Translator | None = None,
) -> str:
    translate = t or get_translator()
    cards = []
    for result in results:
        probability = (
            f"{result.probability * 100:.1f}%"
            if result.probability is not None
            else "—"
        )
        status, status_class = _score_status(result, translate)
        detail = result.error or result.label
        cards.append(
            f"""
            <article class="detector-card {status_class}">
              <div class="detector-head">
                <div>
                  <span class="detector-name">{html.escape(result.detector)}</span>
                  <span class="detector-kind">{translate("detector.kind")}</span>
                </div>
                <span class="detector-device">{html.escape(result.device or translate("detector.unknown_device"))}</span>
              </div>
              <div class="detector-body">
                <div class="detector-score-block">
                  <span class="metric-label">{translate("detector.probability")}</span>
                  <strong class="detector-score">{probability}</strong>
                </div>
                <div class="detector-status-block">
                  <span class="metric-label">{translate("detector.status")}</span>
                  <strong class="detector-status">{html.escape(status)}</strong>
                  <small>{html.escape(detail)}</small>
                </div>
                <div class="detector-caveat">
                  <span class="metric-label">{translate("detector.caveat")}</span>
                  <p>{html.escape(_detector_caveat(result, translate))}</p>
                </div>
              </div>
              <div class="detector-runtime">{translate("detector.seconds", value=f"{result.runtime_seconds:.1f}")}</div>
            </article>
            """
        )
    return '<div class="detector-grid">' + "".join(cards) + "</div>"


def metadata_rows(
    features: AudioFeatures,
    t: Translator | None = None,
) -> list[list[Any]]:
    translate = t or get_translator()
    metadata = features.metadata
    metrics = features.metrics
    return [
        [translate("meta.file"), metadata.filename, ""],
        [translate("meta.format"), metadata.suffix.upper().lstrip("."), ""],
        [
            translate("meta.duration"),
            round(metadata.duration_seconds, 3),
            translate("unit.seconds"),
        ],
        [
            translate("meta.sample_rate"),
            metadata.sample_rate,
            translate("unit.hertz"),
        ],
        [translate("meta.channels"), metadata.channels, ""],
        [
            translate("meta.size"),
            round(metadata.size_bytes / (1024 * 1024), 2),
            translate("unit.megabytes"),
        ],
        [translate("meta.peak"), round(metrics.peak_dbfs, 2), "dBFS"],
        [translate("meta.rms"), round(metrics.rms_dbfs, 2), "dBFS"],
        [translate("meta.crest"), round(metrics.crest_factor_db, 2), "dB"],
        [
            translate("meta.stereo_correlation"),
            None
            if metrics.stereo_correlation is None
            else round(metrics.stereo_correlation, 3),
            "",
        ],
        [
            translate("meta.mid_side"),
            None
            if metrics.mid_side_ratio_db is None
            else round(metrics.mid_side_ratio_db, 2),
            "dB",
        ],
    ]


def history_rows(
    runs: list[AnalysisRun],
    durations: dict[str, float],
    t: Translator | None = None,
) -> list[list[Any]]:
    translate = t or get_translator()
    rows = []
    for run in runs:
        by_detector = {result.detector: result for result in run.results}

        def score(detector: str) -> str:
            result = by_detector.get(detector)
            if result is None:
                return "—"
            if result.probability is None:
                return result.status
            return f"{result.probability * 100:.1f}%"

        duration = durations.get(run.run_id)
        duration_text = (
            "—"
            if duration is None
            else translate("detector.seconds", value=f"{duration:.1f}")
        )
        rows.append(
            [
                run.created_at[:19].replace("T", " "),
                run.filename,
                duration_text,
                score("lofcz"),
                score("FST"),
                run.note,
                run.run_id,
                "★ A" if run.is_baseline else "",
            ]
        )
    return rows


def comparison_metric_rows(
    outcome: RunComparisonOutcome,
    t: Translator | None = None,
) -> list[list[Any]]:
    translate = t or get_translator()
    if outcome.comparison is not None:
        source_rows = outcome.comparison.metric_rows
    else:
        a = outcome.features_a
        b = outcome.features_b
        pairs = [
            (
                translate("meta.duration"),
                a.metadata.duration_seconds,
                b.metadata.duration_seconds,
                translate("unit.seconds"),
            ),
            (
                translate("meta.peak"),
                a.metrics.peak_dbfs,
                b.metrics.peak_dbfs,
                "dBFS",
            ),
            (
                translate("meta.rms"),
                a.metrics.rms_dbfs,
                b.metrics.rms_dbfs,
                "dBFS",
            ),
            (
                translate("meta.crest"),
                a.metrics.crest_factor_db,
                b.metrics.crest_factor_db,
                "dB",
            ),
            (
                translate("meta.stereo_correlation"),
                a.metrics.stereo_correlation,
                b.metrics.stereo_correlation,
                "",
            ),
            (
                translate("meta.mid_side"),
                a.metrics.mid_side_ratio_db,
                b.metrics.mid_side_ratio_db,
                "dB",
            ),
        ]
        source_rows = [
            {
                "metric": name,
                "baseline": value_a,
                "current": value_b,
                "delta": (
                    None
                    if value_a is None or value_b is None
                    else value_b - value_a
                ),
                "unit": unit,
            }
            for name, value_a, value_b, unit in pairs
        ]

    return [
        [
            row["metric"],
            _format_number(row["baseline"]),
            _format_number(row["current"]),
            _format_number(row["delta"]),
            row["unit"],
        ]
        for row in source_rows
    ]


def detector_delta_rows(
    outcome: RunComparisonOutcome,
    t: Translator | None = None,
) -> list[list[Any]]:
    translate = t or get_translator()
    results_a = {result.detector: result for result in outcome.run_a.results}
    results_b = {result.detector: result for result in outcome.run_b.results}
    order = [
        detector
        for detector in ("lofcz", "FST")
        if detector in results_a or detector in results_b
    ]
    order.extend(
        detector
        for detector in sorted(set(results_a) | set(results_b))
        if detector not in order
    )

    def probability_text(result: DetectorResult | None) -> str:
        if result is None or result.probability is None:
            return "—"
        return f"{result.probability * 100:.1f}%"

    rows = []
    for detector in order:
        result_a = results_a.get(detector)
        result_b = results_b.get(detector)
        delta = "—"
        if (
            result_a is not None
            and result_b is not None
            and result_a.probability is not None
            and result_b.probability is not None
        ):
            shift = (result_b.probability - result_a.probability) * 100
            delta = f"{shift:+.1f} {translate('unit.percentage_points')}"
        rows.append(
            [
                detector,
                probability_text(result_a),
                probability_text(result_b),
                delta,
            ]
        )
    return rows


def technical_payload(outcome: AnalysisOutcome) -> dict[str, Any]:
    return {
        "run_id": outcome.run.run_id,
        "created_at": outcome.run.created_at,
        "input_sha256": outcome.features.metadata.sha256,
        "detectors": [asdict(result) for result in outcome.run.results],
    }


def timeline_summary(
    timeline: DetectorTelemetry,
    t: Translator | None = None,
) -> str:
    """Short readout of the sliding-window scan, hottest windows first."""
    translate = t or get_translator()
    probabilities = [float(value) for value in timeline.arrays["probability"]]
    starts = [float(value) for value in timeline.arrays["window_start_seconds"]]
    ends = [float(value) for value in timeline.arrays["window_end_seconds"]]
    if not probabilities:
        return translate("timeline.empty")

    above = sum(1 for value in probabilities if value >= 0.5)
    order = sorted(range(len(probabilities)), key=lambda i: -probabilities[i])
    hottest = ", ".join(
        translate(
            "timeline.window",
            start=f"{starts[i]:.0f}",
            end=f"{ends[i]:.0f}",
            probability=f"{probabilities[i] * 100:.0f}",
        )
        for i in order[:3]
    )
    return translate(
        "timeline.summary",
        count=len(probabilities),
        window=timeline.scalars.get("window_seconds"),
        hop=timeline.scalars.get("hop_seconds"),
        above=above,
        minimum=f"{min(probabilities) * 100:.1f}",
        maximum=f"{max(probabilities) * 100:.1f}",
        hottest=hottest,
    )


def layer_rows(
    results: Sequence[LayerResult],
    t: Translator | None = None,
) -> list[list[Any]]:
    """Table rows for a layer sweep, keeping the raw residue next to the score."""
    translate = t or get_translator()
    rows: list[list[Any]] = []
    for item in results:
        if item.probability is None:
            score = "—"
            verdict = item.error or translate("layer.not_measured")
        else:
            score = f"{item.probability * 100:.1f}%"
            verdict = (
                translate("layer.high_priority")
                if item.probability >= 0.5
                else translate("layer.low_priority")
            )
        rows.append(
            [
                item.name,
                score,
                _format_number(item.mean_residue_db, 2) if item.mean_residue_db is not None else "—",
                _format_number(item.duration_seconds, 1) if item.duration_seconds is not None else "—",
                verdict,
            ]
        )
    return rows


def artifact_rows(
    results: Sequence[ArtifactMetrics],
    t: Translator | None = None,
) -> list[list[Any]]:
    """One row per file so a track can be read straight against its references."""
    translate = t or get_translator()
    rows: list[list[Any]] = []
    for item in results:
        rows.append(
            [
                item.name,
                _format_number(item.attack_sharpness_db, 1),
                _format_number(item.rolloff_95_hz / 1000.0, 2),
                _format_number(item.hf_cliff_db_per_octave, 1),
                _format_number(item.noise_floor_dbfs, 1),
                _format_number(item.noise_floor_flatness, 3),
                _format_number(item.stereo_correlation_low, 2)
                if item.stereo_correlation_low is not None
                else translate("unit.mono"),
                _format_number(item.stereo_correlation_high, 2)
                if item.stereo_correlation_high is not None
                else translate("unit.mono"),
            ]
        )
    return rows
