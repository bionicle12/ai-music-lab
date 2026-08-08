from __future__ import annotations

import html
from dataclasses import asdict
from typing import Any

from collections.abc import Sequence

from .artifact_metrics import ArtifactMetrics
from .contracts import AnalysisRun, AudioFeatures, DetectorResult, LayerResult
from .disclosure import disclosure_html
from .i18n import Translator, get_translator
from .readiness import DETECTOR_REQUIREMENTS, ReadinessReport, can_transcribe
from .repositories import REPOSITORIES_BY_KEY, PullOutcome, RepoStatus
from .sunofix import Recommendation, SunoFixResult
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
        # The caveat used to be the widest of three columns, repeated per card,
        # sitting between the reader and the number they came for. It is now a
        # badge in the head — amber when the result is one you should not take
        # at face value, cyan otherwise.
        caveat = disclosure_html(
            "detector/caveat",
            translate,
            body=f"<p>{html.escape(_detector_caveat(result, translate))}</p>",
        )
        if status_class in ("result-high", "result-error", "result-warning"):
            caveat = caveat.replace("tone-info", "tone-warn")
        cards.append(
            f"""
            <article class="detector-card {status_class}">
              <div class="detector-head">
                <div>
                  <span class="detector-name">{html.escape(result.detector)}</span>
                  <span class="detector-kind">{translate("detector.kind")}</span>
                </div>
                {caveat}
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
              </div>
              <div class="detector-foot">
                <span class="detector-device">{html.escape(result.device or translate("detector.unknown_device"))}</span>
                <span class="detector-runtime">{translate("detector.seconds", value=f"{result.runtime_seconds:.1f}")}</span>
              </div>
            </article>
            """
        )
    return '<div class="detector-grid">' + "".join(cards) + "</div>"


def file_card_html(
    features: AudioFeatures | None,
    t: Translator | None = None,
) -> str:
    """The loaded file as a card, not an eleven-row table in a 330px column.

    Identity as chips, the three levels you actually glance at as a small
    definition list, and the stereo figures behind a badge — they are ``None``
    for mono, and a column of dashes is noise. Nothing is lost: the full table
    is on the Technical data tab and every value stays in the run JSON.
    """
    translate = t or get_translator()
    if features is None:
        return f'<div class="file-card is-empty">{translate("meta.empty")}</div>'

    metadata = features.metadata
    metrics = features.metrics
    minutes, seconds = divmod(int(round(metadata.duration_seconds)), 60)
    chips = [
        metadata.suffix.upper().lstrip("."),
        f"{metadata.sample_rate / 1000:g} {translate('unit.kilohertz')}",
        translate("unit.mono")
        if metadata.channels == 1
        else translate("unit.stereo"),
        f"{minutes}:{seconds:02d}",
        f"{metadata.size_bytes / (1024 * 1024):.1f} {translate('unit.megabytes')}",
    ]
    levels = [
        (translate("meta.peak"), f"{metrics.peak_dbfs:.1f} dBFS"),
        (translate("meta.rms"), f"{metrics.rms_dbfs:.1f} dBFS"),
        (translate("meta.crest"), f"{metrics.crest_factor_db:.1f} dB"),
    ]

    stereo = []
    if metrics.stereo_correlation is not None:
        stereo.append(
            f"{translate('meta.stereo_correlation')}: "
            f"{metrics.stereo_correlation:.3f}"
        )
    if metrics.mid_side_ratio_db is not None:
        stereo.append(
            f"{translate('meta.mid_side')}: {metrics.mid_side_ratio_db:.2f} dB"
        )
    stereo_badge = (
        disclosure_html(
            "file/stereo",
            translate,
            body="".join(f"<p>{html.escape(item)}</p>" for item in stereo),
        )
        if stereo
        else ""
    )

    return f"""
    <div class="file-card">
      <p class="file-card-name" title="{html.escape(metadata.filename)}">{html.escape(metadata.filename)}</p>
      <ul class="file-chips">{"".join(f"<li>{html.escape(chip)}</li>" for chip in chips)}</ul>
      <dl class="file-levels">{"".join(
          f"<div><dt>{html.escape(name)}</dt><dd>{html.escape(value)}</dd></div>"
          for name, value in levels
      )}</dl>
      {stereo_badge}
    </div>
    """


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
        # The settings the run was measured with — never the token, which is
        # not in `detector_options` for exactly this reason.
        "settings": dict(outcome.settings),
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


def _strongest_peak_db(metrics: ArtifactMetrics) -> float:
    return max((peak.prominence_db for peak in metrics.tonal_peaks), default=0.0)


def sunofix_reasons(
    recommendations: Sequence[Recommendation],
    t: Translator | None = None,
) -> dict[str, str]:
    """One sentence per repair module, quoting the number that decided it.

    The interface has to be able to say *why* a box is ticked. A tick with no
    figure behind it is the interface asserting that it knows better, which is
    the habit this half of the app exists to avoid.
    """
    translate = t or get_translator()
    lines: dict[str, str] = {}
    for item in recommendations:
        suffix = "" if item.recommended else ".none"
        evidence = item.evidence
        if item.module == "de_artifact":
            frequencies = evidence.get("frequencies_hz", ())
            values = {
                "prominence": _format_number(evidence.get("prominence_db"), 1),
                "frequencies": ", ".join(
                    f"{value / 1000.0:.1f}" for value in frequencies
                )
                or "—",
            }
        elif item.module == "restore_air":
            values = {
                "cutoff": _format_number(evidence.get("cutoff_hz", 0.0) / 1000.0, 1),
                "slope": _format_number(evidence.get("slope_db_per_octave"), 0),
            }
        elif item.module == "fix_transients":
            values = {"attack": _format_number(evidence.get("attack_db"), 1)}
        elif item.module == "restore_floor":
            values = {
                "floor": _format_number(evidence.get("floor_dbfs"), 1),
                "flatness": _format_number(evidence.get("flatness"), 2),
            }
        else:
            values = {"correlation": _format_number(evidence.get("correlation_high"), 2)}
        lines[item.module] = translate(f"sunofix.why.{item.module}{suffix}", **values)
    return lines


def sunofix_delta_rows(
    before: ArtifactMetrics,
    after: ArtifactMetrics,
    t: Translator | None = None,
) -> list[list[Any]]:
    """The A/B an edit has to justify itself with.

    Read as `after − before`, on the same measurements the Artifacts tab uses,
    so a repair that claims to have fixed something has to show it as a number.
    """
    translate = t or get_translator()
    readings: list[tuple[str, float | None, float | None, int]] = [
        ("table.artifact.attack", before.attack_sharpness_db, after.attack_sharpness_db, 1),
        (
            "table.artifact.rolloff",
            before.rolloff_95_hz / 1000.0,
            after.rolloff_95_hz / 1000.0,
            2,
        ),
        (
            "table.artifact.cutoff",
            before.hf_cutoff_hz / 1000.0,
            after.hf_cutoff_hz / 1000.0,
            2,
        ),
        (
            "table.artifact.cliff",
            before.hf_cliff_db_per_octave,
            after.hf_cliff_db_per_octave,
            1,
        ),
        ("table.artifact.tonal", _strongest_peak_db(before), _strongest_peak_db(after), 1),
        ("table.artifact.noise_floor", before.noise_floor_dbfs, after.noise_floor_dbfs, 1),
        (
            "table.artifact.flatness",
            before.noise_floor_flatness,
            after.noise_floor_flatness,
            3,
        ),
        (
            "table.artifact.corr_low",
            before.stereo_correlation_low,
            after.stereo_correlation_low,
            2,
        ),
        (
            "table.artifact.corr_high",
            before.stereo_correlation_high,
            after.stereo_correlation_high,
            2,
        ),
    ]
    rows: list[list[Any]] = []
    for key, left, right, digits in readings:
        delta = (
            _format_number(right - left, digits)
            if left is not None and right is not None
            else translate("unit.mono")
        )
        rows.append(
            [
                translate(key),
                _format_number(left, digits),
                _format_number(right, digits),
                delta,
            ]
        )
    return rows


def sunofix_summary(result: SunoFixResult, t: Translator | None = None) -> str:
    """What ran, in the order it ran, and what the level policy decided."""
    translate = t or get_translator()
    applied = [step.module for step in result.steps if step.applied]
    if not applied:
        return translate("sunofix.status.nothing")
    gain = result.output_gain_db
    level = (
        translate("sunofix.status.level_kept")
        if gain == 0.0
        else translate("sunofix.status.level_pulled", gain=f"{gain:.1f}")
    )
    return translate(
        "sunofix.status.done",
        name=result.output_path.name,
        modules=", ".join(translate(f"sunofix.module.{module}") for module in applied),
        level=level,
    )


#: ok -> glyph. `None` is "not checked yet", which deserves its own mark:
#: rendering unknown as a red cross would accuse a working setup of being broken.
_READINESS_MARKS: dict[bool | None, tuple[str, str]] = {
    True: ("✓", "ready-ok"),
    False: ("✕", "ready-bad"),
    None: ("•", "ready-unknown"),
}


def readiness_summary(report: ReadinessReport, t: Translator | None = None) -> str:
    """One line: ready, blocked, or ready-but-unverified.

    The middle case matters. `can_transcribe` deliberately ignores the package
    probe — it costs a subprocess and a real run fails loudly enough — so a
    setup with everything but that check done is usable, and calling it "not set
    up" would send someone hunting for a problem they do not have.
    """
    translate = t or get_translator()
    problem = report.first_problem()
    if problem is None:
        return translate("readiness.ready")
    if can_transcribe(report):
        return translate("readiness.unverified")
    return translate(
        "readiness.blocked", detail=translate(f"readiness.fix.{problem.key}")
    )


def readiness_html(
    report: ReadinessReport,
    t: Translator | None = None,
    *,
    footer: bool = True,
) -> str:
    """One row per requirement, plus what to do about the first failing one.

    ``footer=False`` when the caller already shows that line — nesting the
    checklist under its own summary otherwise says the same sentence twice.
    """
    translate = t or get_translator()
    rows = []
    for item in report.items:
        glyph, css = _READINESS_MARKS[item.ok]
        detail = item.detail if item.ok is not None else translate(
            "readiness.not_checked"
        )
        rows.append(
            f'<li class="{css}"><span class="ready-mark">{glyph}</span>'
            f'<span class="ready-name">{html.escape(translate(f"readiness.item.{item.key}"))}</span>'
            f'<span class="ready-detail">{html.escape(detail)}</span></li>'
        )
    tail = (
        f'<p class="readiness-next">'
        f"{html.escape(readiness_summary(report, translate))}</p>"
        if footer
        else ""
    )
    return (
        '<div class="readiness">'
        f'<h4>{html.escape(translate("readiness.heading"))}</h4>'
        f'<ul class="readiness-list">{"".join(rows)}</ul>{tail}</div>'
    )


_DETECTOR_REPO_KEYS: dict[str, str] = {
    item.detector: item.repo_key for item in DETECTOR_REQUIREMENTS
}


def detector_readiness_html(
    detector: str,
    report: ReadinessReport,
    t: Translator | None = None,
) -> str:
    """The three-row checklist, for a detector's own settings dialog.

    Deliberately not :func:`readiness_html`: that one's row labels name
    muscriptor ("muscriptor clone") and its summary runs through
    ``can_transcribe``, which asks about a licence and a token no detector has.
    Sharing it would have meant a parameter deciding which half applies.
    """
    translate = t or get_translator()
    rows = []
    for item in report.items:
        glyph, css = _READINESS_MARKS[item.ok]
        rows.append(
            f'<li class="{css}"><span class="ready-mark">{glyph}</span>'
            f'<span class="ready-name">'
            f'{html.escape(translate(f"detector.ready.item.{item.key}"))}</span>'
            f'<span class="ready-detail">{html.escape(item.detail)}</span></li>'
        )
    problem = report.first_problem()
    tail = (
        translate("detector.ready.ok")
        if problem is None
        else translate(
            "detector.ready.blocked",
            detail=translate(f"detector.ready.fix.{problem.key}"),
        )
    )
    return (
        f'<div class="readiness" data-detector-readiness="{html.escape(detector)}">'
        f'<ul class="readiness-list">{"".join(rows)}</ul>'
        f'<p class="readiness-next">{html.escape(tail)}</p></div>'
    )


def detector_upstream_html(
    detector: str,
    status: RepoStatus | None,
    t: Translator | None = None,
) -> str:
    """Which clone, at which commit, and whether that is the verified one.

    A score is only comparable across runs if the code behind it did not move,
    so the commit belongs beside the settings that produced the score.
    """
    translate = t or get_translator()
    repo = REPOSITORIES_BY_KEY[_DETECTOR_REPO_KEYS[detector]]
    head = (
        status.head[:7]
        if status and status.head
        else translate("detector.upstream.missing")
    )
    state = (
        translate("detector.upstream.match")
        if status and status.matches_pin
        else translate("detector.upstream.drift", pinned=repo.pinned_commit[:7])
    )
    return (
        '<dl class="detector-upstream">'
        f'<div><dt>{html.escape(translate("detector.upstream.repository"))}</dt>'
        f'<dd><a href="{html.escape(repo.url.removesuffix(".git"))}" target="_blank" '
        f'rel="noopener">{html.escape(repo.folder)}</a></dd></div>'
        f'<div><dt>{html.escape(translate("detector.upstream.head"))}</dt>'
        f'<dd><code>{html.escape(head)}</code> · {html.escape(state)}</dd></div>'
        "</dl>"
    )


def readiness_disclosure(
    report: ReadinessReport,
    t: Translator | None = None,
) -> str:
    """The same checklist, collapsed to one line for the transcription tab.

    Opens itself when the setup is incomplete — so someone who is blocked sees
    more than they do today, and someone who is ready sees three words instead
    of six rows.
    """
    translate = t or get_translator()
    body = (
        f'<p class="readiness-line">'
        f"{html.escape(readiness_summary(report, translate))}</p>"
        + readiness_html(report, translate, footer=False)
    )
    # Opens itself only when something actually blocks a run — an unrun package
    # probe is not a reason to greet everyone with an open checklist.
    return disclosure_html(
        "midi/setup", translate, body=body, open=not can_transcribe(report)
    )


def _repo_state(status: RepoStatus, t: Translator) -> str:
    if not status.present:
        return t("repo.state.missing")
    if not status.is_git:
        return t("repo.state.not_git")
    if status.error:
        return status.error
    if status.dirty:
        return t("repo.state.dirty")
    if status.behind:
        return t("repo.state.behind", count=status.behind)
    if status.behind == 0:
        return t("repo.state.current")
    return t("repo.state.clean")


def repo_status_rows(
    statuses: Sequence[RepoStatus],
    t: Translator | None = None,
) -> list[list[Any]]:
    """The upstream clones as a table: where they are and whether they moved."""
    translate = t or get_translator()
    rows: list[list[Any]] = []
    for status in statuses:
        repo = REPOSITORIES_BY_KEY[status.key]
        pinned = translate("repo.pin.match")
        if status.head and not status.matches_pin:
            pinned = translate("repo.pin.drift", commit=repo.pinned_commit[:7])
        elif not status.head:
            pinned = "—"
        rows.append(
            [
                repo.folder,
                (status.head or "—")[:7],
                status.branch or translate("repo.state.detached"),
                _repo_state(status, translate),
                pinned,
            ]
        )
    return rows


def pull_message(outcome: PullOutcome, t: Translator | None = None) -> str:
    """What a pull actually did, or precisely why it declined to do anything."""
    translate = t or get_translator()
    if not outcome.performed:
        reason = translate(f"repo.pull.{outcome.refused_reason}")
        return f"{reason}\n\n```\n{outcome.log}\n```" if outcome.log else reason
    if outcome.previous_head == outcome.new_head:
        return translate("repo.pull.unchanged", commit=(outcome.new_head or "")[:7])
    lines = [
        translate(
            "repo.pull.done",
            previous=(outcome.previous_head or "")[:7],
            current=(outcome.new_head or "")[:7],
            subject=outcome.subject or "",
        ),
        translate("repo.pull.comparability"),
        translate("repo.pull.pin_line", commit=outcome.new_head or ""),
    ]
    if outcome.dependencies_changed:
        lines.insert(1, translate("repo.pull.dependencies"))
    return "\n\n".join(lines)
