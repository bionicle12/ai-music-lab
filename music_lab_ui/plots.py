from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from scipy.ndimage import gaussian_filter

from .comparison import FeatureComparison
from .contracts import AudioFeatures
from .i18n import Translator, get_translator


#: Kept in step with styles.css by hand — these are the same palette, and a
#: chart drawn in a slightly different cyan than the chrome around it reads as
#: two products.
PAPER = "#090d14"
PANEL = "#101722"
GRID = "#263244"
TEXT = "#d8e2ef"
MUTED = "#8190a5"
CYAN = "#23b7e5"
AMBER = "#f4ad28"
VIOLET = "#9d7bf5"

#: Charts must use the same families as the interface. The previous value asked
#: for Inter, which is loaded nowhere, so Plotly silently fell back to a system
#: font while the rest of the page rendered in the theme font.
FONT_UI = "Manrope, Segoe UI, system-ui, sans-serif"
#: Every tick label and hover read-out is a measurement, so it gets the tabular
#: monospace rather than the UI face.
FONT_MONO = "JetBrains Mono, Consolas, monospace"

SPECTROGRAM_SCALE = [
    [0.0, "#060a11"],
    [0.18, "#111b2a"],
    [0.42, "#17384a"],
    [0.68, "#1aa6b7"],
    [0.86, "#e2a03d"],
    [1.0, "#fff1c2"],
]

DIFFERENCE_SCALE = [
    [0.0, "#168fa1"],
    [0.5, "#151b25"],
    [1.0, "#ef9f3f"],
]

DETAIL_PRESETS = {
    "preview": (96, 160),
    "high": (256, 480),
}


def _smooth_3d_levels(levels: np.ndarray) -> np.ndarray:
    values = np.asarray(levels, dtype=np.float32).copy()
    frequency_sigma = 1.25 * max(values.shape[0] / 96.0, 1.0)
    time_sigma = 2.0 * max(values.shape[1] / 160.0, 1.0)
    smoothed = gaussian_filter(
        values,
        sigma=(frequency_sigma, time_sigma),
        mode="nearest",
    )
    return np.clip(smoothed, -100.0, 0.0).astype(np.float32, copy=False)


def _zone_hint(frequency: float, t: Translator) -> str:
    if frequency < 60:
        return t("zone.sub_bass")
    if frequency < 250:
        return t("zone.bass")
    if frequency < 500:
        return t("zone.low_mid")
    if frequency < 2_000:
        return t("zone.mid")
    if frequency < 6_000:
        return t("zone.presence")
    if frequency < 12_000:
        return t("zone.highs")
    return t("zone.air")


def _base_layout(
    figure: go.Figure,
    title: str,
    height: int = 420,
    *,
    time_axis: bool = False,
) -> go.Figure:
    """`time_axis` opts the chart into playback sync (see static/playback_sync.js).

    An empty title is left off the figure entirely rather than set to "".
    Gradio 6.20 renders a labelled plot with

        layout.title && show_label && (margin.t = Math.max(100, margin.t))

    and an empty title object still passes that test, so a chart asking for a
    6px top margin was given 100. The whole-track strip is 118px tall: the
    trace was being drawn into the two pixels left over, which looked exactly
    like a chart that had never received any data.
    """
    figure.update_layout(
        meta={"time_axis": bool(time_axis)},
        paper_bgcolor=PAPER,
        plot_bgcolor=PANEL,
        font={"color": TEXT, "family": FONT_UI},
        hoverlabel={
            "bgcolor": "#151e2b",
            "font": {"color": TEXT, "family": FONT_MONO},
        },
        margin={"l": 70, "r": 26, "t": 58, "b": 55},
        height=height,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    )
    if title:
        figure.update_layout(title={"text": title, "x": 0.02, "xanchor": "left"})
    figure.update_xaxes(
        gridcolor=GRID, zerolinecolor=GRID, tickfont={"family": FONT_MONO}
    )
    figure.update_yaxes(
        gridcolor=GRID, zerolinecolor=GRID, tickfont={"family": FONT_MONO}
    )
    return figure


def spectrogram_figure(
    features: AudioFeatures,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    zones = np.array(
        [
            _zone_hint(float(frequency), translate)
            for frequency in features.frequency_axis
        ],
        dtype=object,
    )
    customdata = np.repeat(zones[:, np.newaxis], features.time_axis.size, axis=1)
    figure = go.Figure(
        go.Heatmap(
            x=features.time_axis,
            y=features.frequency_axis,
            z=features.spectrogram_db,
            customdata=customdata,
            zmin=-100,
            zmax=0,
            colorscale=SPECTROGRAM_SCALE,
            colorbar={"title": "dBFS", "outlinewidth": 0},
            hovertemplate=(
                f"{translate('plot.hover.time')}: %{{x:.2f}} {translate('unit.seconds')}<br>"
                f"{translate('plot.hover.frequency')}: %{{y:.0f}} {translate('unit.hertz')}<br>"
                f"{translate('plot.hover.level')}: %{{z:.1f}} dBFS<br>"
                f"{translate('plot.hover.zone')}: %{{customdata}}<extra></extra>"
            ),
        )
    )
    _base_layout(figure, translate("plot.spectrogram"), time_axis=True)
    figure.update_xaxes(title=translate("plot.axis.time"))
    figure.update_yaxes(title=translate("plot.axis.frequency"), type="log")
    return figure


def spectrogram_3d_figure(
    features: AudioFeatures,
    detail: str = "preview",
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    try:
        frequency_limit, time_limit = DETAIL_PRESETS[detail]
    except KeyError as error:
        raise ValueError(f"unknown 3D detail preset: {detail}") from error
    frequency_indices = np.unique(
        np.linspace(
            0,
            features.frequency_axis.size - 1,
            min(frequency_limit, features.frequency_axis.size),
            dtype=int,
        )
    )
    time_indices = np.unique(
        np.linspace(
            0,
            features.time_axis.size - 1,
            min(time_limit, features.time_axis.size),
            dtype=int,
        )
    )
    times = features.time_axis[time_indices]
    frequencies = features.frequency_axis[frequency_indices]
    levels = _smooth_3d_levels(
        features.spectrogram_db[np.ix_(frequency_indices, time_indices)]
    )
    x_grid, y_grid = np.meshgrid(times, np.log10(frequencies))

    figure = go.Figure(
        go.Surface(
            x=x_grid,
            y=y_grid,
            z=levels,
            surfacecolor=levels,
            cmin=-100,
            cmax=0,
            colorscale=SPECTROGRAM_SCALE,
            colorbar={"title": "dBFS", "outlinewidth": 0},
            hovertemplate=(
                f"{translate('plot.hover.time')}: %{{x:.2f}} {translate('unit.seconds')}<br>"
                f"{translate('plot.hover.frequency')}: %{{customdata:.0f}} {translate('unit.hertz')}<br>"
                f"{translate('plot.hover.level')}: %{{z:.1f}} dBFS<extra></extra>"
            ),
            customdata=np.broadcast_to(
                frequencies[:, np.newaxis],
                levels.shape,
            ),
            connectgaps=True,
        )
    )
    frequency_ticks = np.array([20, 50, 100, 200, 500, 1_000, 2_000, 5_000, 10_000, 20_000])
    frequency_ticks = frequency_ticks[
        (frequency_ticks >= frequencies.min())
        & (frequency_ticks <= frequencies.max())
    ]
    figure.update_layout(
        title={
            "text": translate("plot.spectrogram_3d"),
            "x": 0.02,
            "xanchor": "left",
        },
        paper_bgcolor=PAPER,
        font={"color": TEXT, "family": FONT_UI},
        height=590,
        margin={"l": 20, "r": 20, "t": 58, "b": 20},
        scene={
            "bgcolor": PANEL,
            "camera": {"eye": {"x": 1.55, "y": -1.55, "z": 1.2}},
            "xaxis": {
                "title": translate("plot.axis.time"),
                "gridcolor": GRID,
                "backgroundcolor": PANEL,
            },
            "yaxis": {
                "title": translate("plot.axis.frequency"),
                "gridcolor": GRID,
                "backgroundcolor": PANEL,
                "tickvals": np.log10(frequency_ticks).tolist(),
                "ticktext": [f"{value:g}" for value in frequency_ticks],
            },
            "zaxis": {
                "title": translate("plot.axis.level"),
                "range": [-100, 0],
                "gridcolor": GRID,
                "backgroundcolor": PANEL,
            },
        },
    )
    return figure


def waveform_figure(
    features: AudioFeatures,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    figure = go.Figure(
        go.Scatter(
            x=features.time_axis,
            y=features.waveform_rms_db,
            mode="lines",
            name="RMS",
            line={"color": CYAN, "width": 1.6},
            fill="tozeroy",
            fillcolor="rgba(36, 200, 219, 0.12)",
            hovertemplate=(
                f"{translate('plot.hover.time')}: %{{x:.2f}} {translate('unit.seconds')}"
                "<br>RMS: %{y:.1f} dBFS<extra></extra>"
            ),
        )
    )
    # Sized as a strip beside the player rather than as a chart in its own
    # right: it is the full-track scrub bar Gradio cannot draw.
    _base_layout(figure, "", height=118, time_axis=True)
    # Top margin clears the floating "whole track" label, which Gradio draws
    # over the top-left of the canvas rather than above it.
    figure.update_layout(
        margin={"l": 8, "r": 8, "t": 20, "b": 20}, showlegend=False
    )
    figure.update_xaxes(title=None)
    figure.update_yaxes(title=None, range=[-100, 0], showticklabels=False)
    return figure


def spectrum_figure(
    current: AudioFeatures,
    baseline: AudioFeatures | None = None,
    current_label: str | None = None,
    baseline_label: str | None = None,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    current_label = current_label or translate("plot.current")
    baseline_label = baseline_label or translate("plot.baseline")
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=current.frequency_axis,
            y=current.average_spectrum_db,
            mode="lines",
            name=current_label,
            line={"color": CYAN, "width": 2},
            hovertemplate=(
                f"{translate('plot.hover.frequency')}: %{{x:.0f}} "
                f"{translate('unit.hertz')}<br>{current_label}: "
                "%{y:.1f} dBFS<extra></extra>"
            ),
        )
    )
    if baseline is not None:
        figure.add_trace(
            go.Scatter(
                x=baseline.frequency_axis,
                y=baseline.average_spectrum_db,
                mode="lines",
                name=baseline_label,
                line={"color": AMBER, "width": 1.8},
                hovertemplate=(
                    f"{translate('plot.hover.frequency')}: %{{x:.0f}} "
                    f"{translate('unit.hertz')}<br>{baseline_label}: "
                    "%{y:.1f} dBFS<extra></extra>"
                ),
            )
        )
    _base_layout(figure, translate("plot.average_spectrum"))
    figure.update_xaxes(title=translate("plot.axis.frequency"), type="log")
    figure.update_yaxes(title=translate("plot.axis.level"), range=[-100, 0])
    return figure


def difference_figure(
    comparison: FeatureComparison,
    t: Translator | None = None,
) -> go.Figure:
    translate = t or get_translator()
    absolute = np.abs(comparison.spectrogram_delta_db)
    finite = absolute[np.isfinite(absolute)]
    percentile = float(np.percentile(finite, 98)) if finite.size else 1.0
    limit = max(1.0, min(24.0, percentile))

    figure = go.Figure(
        go.Heatmap(
            x=comparison.current.time_axis,
            y=comparison.current.frequency_axis,
            z=comparison.spectrogram_delta_db,
            zmin=-limit,
            zmax=limit,
            zmid=0,
            colorscale=DIFFERENCE_SCALE,
            colorbar={"title": "Δ dB", "outlinewidth": 0},
            hovertemplate=(
                f"{translate('plot.hover.time')}: %{{x:.2f}} {translate('unit.seconds')}<br>"
                f"{translate('plot.hover.frequency')}: %{{y:.0f}} {translate('unit.hertz')}<br>"
                f"{translate('plot.hover.change')}: %{{z:+.1f}} dB<extra></extra>"
            ),
        )
    )
    _base_layout(figure, translate("plot.difference"), time_axis=True)
    figure.update_xaxes(title=translate("plot.axis.time"))
    figure.update_yaxes(title=translate("plot.axis.frequency"), type="log")
    return figure


def empty_figure(message: str, height: int = 280) -> go.Figure:
    """`height` so a placeholder occupies what the real chart will.

    The track-overview strip is 118px tall; a 280px empty state in its place
    made the sidebar look like it was mostly waiting for something.
    """
    figure = go.Figure()
    _base_layout(figure, "", height=height)
    figure.update_layout(margin={"l": 8, "r": 8, "t": 6, "b": 6})
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": MUTED, "size": 13},
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return figure
