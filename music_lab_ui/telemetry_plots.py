from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import plotly.graph_objects as go

from .plots import AMBER, CYAN, DIFFERENCE_SCALE, MUTED, _base_layout, empty_figure
from .contracts import LayerResult
from .i18n import Translator, get_translator
from .telemetry import DetectorTelemetry


def lofcz_spectrum_figure(
    telemetry: DetectorTelemetry,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    arrays = telemetry.arrays
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=arrays["frequency_hz"],
            y=arrays["mean_spectrum_db"],
            name="Mean spectrum",
            line={"color": CYAN},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=arrays["frequency_hz"],
            y=arrays["lower_hull_db"],
            name="Lower hull",
            line={"color": AMBER},
        )
    )
    _base_layout(figure, translate("telemetry.lofcz.spectrum"), height=330)
    figure.update_xaxes(title=translate("plot.axis.frequency"))
    figure.update_yaxes(title=translate("plot.axis.level"))
    return figure


def lofcz_fakeprint_figure(
    telemetry: DetectorTelemetry,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    arrays = telemetry.arrays
    figure = go.Figure(
        go.Scatter(
            x=arrays["frequency_hz"],
            y=arrays["fakeprint"],
            name="Native fakeprint",
            line={"color": CYAN},
            fill="tozeroy",
        )
    )
    _base_layout(figure, "lofcz · native fakeprint", height=330)
    figure.update_xaxes(title=translate("plot.axis.frequency"))
    figure.update_yaxes(title=translate("telemetry.lofcz.residue"), range=[0, 1])
    return figure


def fst_segment_figure(
    telemetry: DetectorTelemetry,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    starts = telemetry.arrays["segment_start_seconds"]
    probabilities = telemetry.arrays["stage1_class_probabilities"]
    figure = go.Figure()
    for index, color in ((0, CYAN), (1, AMBER)):
        figure.add_trace(
            go.Scatter(
                x=starts,
                y=probabilities[:, index],
                mode="lines+markers",
                name=f"Stage-1 class {index}",
                line={"color": color},
            )
        )
    _base_layout(figure, translate("telemetry.fst.stage1"), height=340)
    figure.update_xaxes(title=translate("telemetry.axis.segment_start"))
    figure.update_yaxes(title="Softmax class value", range=[0, 1])
    return figure


def fst_similarity_figure(
    telemetry: DetectorTelemetry,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    starts = telemetry.arrays["segment_start_seconds"]
    figure = go.Figure(
        go.Heatmap(
            x=starts,
            y=starts,
            z=telemetry.arrays["self_similarity"],
            zmin=0,
            zmax=1,
            colorscale=DIFFERENCE_SCALE,
            colorbar={"title": "Similarity"},
        )
    )
    _base_layout(figure, "FST · self-similarity matrix", height=440)
    figure.update_xaxes(title=translate("telemetry.axis.segment"))
    figure.update_yaxes(title=translate("telemetry.axis.segment"))
    return figure


def fst_gate_figure(
    telemetry: DetectorTelemetry,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    starts = telemetry.arrays["segment_start_seconds"]
    figure = go.Figure(
        go.Bar(
            x=starts,
            y=telemetry.arrays["fusion_content_gate"],
            name="Content gate",
            marker_color=AMBER,
        )
    )
    _base_layout(figure, "FST · fusion gate content/structure", height=330)
    figure.update_xaxes(title=translate("telemetry.axis.segment_start"))
    figure.update_yaxes(title="Content mixing weight", range=[0, 1])
    return figure


def layer_ranking_figure(
    results: Sequence[LayerResult],
    t: Translator | None = None,
) -> go.Figure:
    """Which layer carries the fakeprint — the production to-do list, ranked."""
    translate = t or get_translator()
    scored = [item for item in results if item.probability is not None]
    if not scored:
        return empty_figure(translate("telemetry.layers.empty"))

    # Plotly draws horizontal bars bottom-up, so reverse to put the worst on top.
    ordered = list(reversed(scored))
    names = [item.name for item in ordered]
    values = [float(item.probability) * 100.0 for item in ordered]
    colours = [AMBER if value >= 50 else CYAN for value in values]

    figure = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker={"color": colours},
            hovertemplate="%{y}<br>lofcz: %{x:.1f}%<extra></extra>",
        )
    )
    figure.add_vline(
        x=50,
        line={"color": MUTED, "width": 1, "dash": "dot"},
    )
    _base_layout(
        figure,
        translate("telemetry.layers.title"),
        height=max(280, 60 + 38 * len(ordered)),
    )
    figure.update_xaxes(title="lofcz, %", range=[0, 100])
    figure.update_yaxes(title="")
    return figure


def timeline_figure(
    timeline: DetectorTelemetry,
    fst: DetectorTelemetry | None = None,
    t: Translator | None = None,
) -> go.Figure:
    """Where along the track the fakeprint shows up, with FST's gate for contrast."""
    translate = t or get_translator()
    centres = np.asarray(timeline.arrays["window_center_seconds"], dtype=float)
    probability = np.asarray(timeline.arrays["probability"], dtype=float) * 100.0
    starts = np.asarray(timeline.arrays["window_start_seconds"], dtype=float)
    ends = np.asarray(timeline.arrays["window_end_seconds"], dtype=float)
    residue = np.asarray(timeline.arrays.get("mean_residue_db", []), dtype=float)
    if residue.size != centres.size:
        residue = np.full(centres.size, np.nan)
    customdata = np.stack([starts, ends, residue], axis=-1)

    figure = go.Figure(
        go.Scatter(
            x=centres,
            y=probability,
            mode="lines+markers",
            name=translate("telemetry.timeline.name"),
            line={"color": AMBER, "width": 2},
            marker={"size": 5},
            fill="tozeroy",
            fillcolor="rgba(240, 164, 67, 0.14)",
            customdata=customdata,
            hovertemplate=(
                f"{translate('telemetry.timeline.window')}<br>"
                "lofcz: %{y:.1f}%<br>"
                f"{translate('telemetry.timeline.residue')}<extra></extra>"
            ),
        )
    )
    figure.add_hline(
        y=50,
        line={"color": MUTED, "width": 1, "dash": "dot"},
        annotation_text=translate("telemetry.timeline.threshold"),
        annotation_position="top left",
    )

    # FST's gate is a raw model signal, not a per-segment AI probability, so it
    # gets its own axis and is never relabelled as one.
    if fst is not None and "segment_start_seconds" in fst.arrays:
        segment_starts = np.asarray(fst.arrays["segment_start_seconds"], dtype=float)
        gate = np.asarray(fst.arrays.get("fusion_content_gate", []), dtype=float)
        if gate.size and gate.size == segment_starts.size:
            figure.add_trace(
                go.Scatter(
                    x=segment_starts,
                    y=gate,
                    mode="lines+markers",
                    name=translate("telemetry.timeline.gate"),
                    yaxis="y2",
                    line={"color": CYAN, "width": 1.4, "dash": "dot"},
                    marker={"size": 6, "symbol": "diamond"},
                    hovertemplate=(
                        f"{translate('telemetry.timeline.gate_hover')}"
                        "<br>fusion gate: %{y:.3f}<extra></extra>"
                    ),
                )
            )
            figure.update_layout(
                yaxis2={
                    "title": "FST fusion gate",
                    "overlaying": "y",
                    "side": "right",
                    "showgrid": False,
                    "color": CYAN,
                }
            )

    _base_layout(
        figure,
        translate("telemetry.timeline.title"),
        height=360,
        time_axis=True,
    )
    figure.update_xaxes(title=translate("plot.axis.time"))
    figure.update_yaxes(title=translate("telemetry.timeline.axis"), range=[0, 100])
    return figure


def lofcz_fakeprint_comparison_figure(
    baseline: DetectorTelemetry,
    current: DetectorTelemetry,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    figure = go.Figure()
    for telemetry, name, color in (
        (baseline, translate("telemetry.version_a"), AMBER),
        (current, translate("telemetry.version_b"), CYAN),
    ):
        figure.add_trace(
            go.Scatter(
                x=telemetry.arrays["frequency_hz"],
                y=telemetry.arrays["fakeprint"],
                name=name,
                line={"color": color},
            )
        )
    _base_layout(figure, "lofcz · native fakeprint A/B", height=340)
    figure.update_xaxes(title=translate("plot.axis.frequency"))
    figure.update_yaxes(title=translate("telemetry.lofcz.residue"), range=[0, 1])
    return figure


def fst_segment_comparison_figure(
    baseline: DetectorTelemetry,
    current: DetectorTelemetry,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    figure = go.Figure()
    for class_index in (0, 1):
        for telemetry, version, color, dash in (
            (baseline, "A", AMBER, "dot"),
            (current, "B", CYAN, "solid"),
        ):
            figure.add_trace(
                go.Scatter(
                    x=telemetry.arrays["segment_start_seconds"],
                    y=telemetry.arrays["stage1_class_probabilities"][:, class_index],
                    mode="lines+markers",
                    name=f"{version} · class {class_index}",
                    line={"color": color, "dash": dash},
                )
            )
    _base_layout(figure, "FST · Stage-1 A/B", height=360)
    figure.update_xaxes(title=translate("telemetry.axis.segment_start"))
    figure.update_yaxes(title="Softmax class value", range=[0, 1])
    return figure


def fst_gate_comparison_figure(
    baseline: DetectorTelemetry,
    current: DetectorTelemetry,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    figure = go.Figure()
    for telemetry, name, color, dash in (
        (baseline, translate("telemetry.version_a"), AMBER, "dot"),
        (current, translate("telemetry.version_b"), CYAN, "solid"),
    ):
        figure.add_trace(
            go.Scatter(
                x=telemetry.arrays["segment_start_seconds"],
                y=telemetry.arrays["fusion_content_gate"],
                mode="lines+markers",
                name=name,
                line={"color": color, "dash": dash},
            )
        )
    _base_layout(figure, "FST · fusion gate A/B", height=340)
    figure.update_xaxes(title=translate("telemetry.axis.segment_start"))
    figure.update_yaxes(title="Content mixing weight", range=[0, 1])
    return figure


def fst_similarity_difference_figure(
    baseline: DetectorTelemetry,
    current: DetectorTelemetry,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    starts_a = baseline.arrays["segment_start_seconds"]
    starts_b = current.arrays["segment_start_seconds"]
    matrix_a = baseline.arrays["self_similarity"]
    matrix_b = current.arrays["self_similarity"]
    if (
        starts_a.shape != starts_b.shape
        or matrix_a.shape != matrix_b.shape
        or not np.allclose(starts_a, starts_b, atol=0.05)
    ):
        return empty_figure(translate("telemetry.similarity.mismatch"))
    delta = matrix_b - matrix_a
    limit = max(float(np.max(np.abs(delta))), 1e-6)
    figure = go.Figure(
        go.Heatmap(
            x=starts_b,
            y=starts_b,
            z=delta,
            zmin=-limit,
            zmax=limit,
            zmid=0,
            colorscale=DIFFERENCE_SCALE,
            colorbar={"title": "Δ B−A"},
        )
    )
    _base_layout(figure, "FST · self-similarity Δ B−A", height=440)
    figure.update_xaxes(title=translate("telemetry.axis.segment_b"))
    figure.update_yaxes(title=translate("telemetry.axis.segment_b"))
    return figure
