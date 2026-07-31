from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

import gradio as gr
import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .plots import (
    difference_figure,
    empty_figure,
    spectrogram_3d_figure,
    spectrogram_figure,
    spectrum_figure,
    waveform_figure,
)
from .detector_help import help_html
from .i18n import (
    DEFAULT_LOCALE,
    LOCALE_NAMES,
    LOCALE_PATHS,
    LOCALES,
    Translator,
    get_translator,
)
from .interpretation import interpret_run
from .telemetry import DetectorTelemetry
from .telemetry_plots import (
    fst_gate_comparison_figure,
    fst_gate_figure,
    fst_segment_comparison_figure,
    fst_segment_figure,
    fst_similarity_difference_figure,
    fst_similarity_figure,
    lofcz_fakeprint_comparison_figure,
    lofcz_fakeprint_figure,
    layer_ranking_figure,
    lofcz_spectrum_figure,
    timeline_figure,
)
from .ui_presenters import (
    artifact_rows,
    comparison_metric_rows,
    detector_cards,
    detector_delta_rows,
    history_rows,
    layer_rows,
    metadata_rows,
    technical_payload,
    timeline_summary,
)
from .ui_service import AnalysisService

ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "music_lab_ui" / "styles.css"
PLAYBACK_SYNC_PATH = ROOT / "music_lab_ui" / "static" / "playback_sync.js"


#: Key used in localStorage. Bumping it resets everyone's stored choice.
LANGUAGE_STORAGE_KEY = "ai-music-lab.locale"


def playback_sync_head() -> str:
    """Inline the chart/player sync script; Gradio serves no static dir by default."""
    if not PLAYBACK_SYNC_PATH.is_file():
        return ""
    source = PLAYBACK_SYNC_PATH.read_text(encoding="utf-8")
    return f"<script>\n{source}\n</script>"


def language_memory_head() -> str:
    """Send a first-time visitor to the locale they last chose.

    Runs before Gradio boots so the redirect happens without a visible flash of
    the wrong language. localStorage is per-origin, so `localhost:7860` and
    `127.0.0.1:7860` keep separate choices, and changing the port starts fresh.
    Only the root path redirects: a locale path is always an explicit request and
    must never bounce, or the switcher could not leave the remembered language.
    """
    default_path = LOCALE_PATHS[DEFAULT_LOCALE]
    known = ", ".join(f'"{code}": "{LOCALE_PATHS[code]}"' for code in LOCALES)
    return f"""
<script>
(function () {{
  try {{
    var paths = {{{known}}};
    var here = window.location.pathname.replace(/\\/+$/, "") || "/";
    if (here !== "{default_path}") return;
    var stored = window.localStorage.getItem("{LANGUAGE_STORAGE_KEY}");
    if (!stored || !paths[stored]) return;
    var target = paths[stored];
    if (target === "{default_path}") return;
    window.location.replace(target + "/" + window.location.search);
  }} catch (error) {{
    /* Private mode or blocked storage: stay on the default locale. */
  }}
}})();
window.aiMusicLabSetLocale = function (code, path) {{
  try {{
    window.localStorage.setItem("{LANGUAGE_STORAGE_KEY}", code);
  }} catch (error) {{
    /* Remembering is a convenience; navigating still has to work. */
  }}
  window.location.assign(path);
}};
</script>
"""


def _language_switcher_html(locale: str, t: Translator) -> str:
    """Plain links, so the choice survives with JavaScript disabled."""
    items = []
    for code in LOCALES:
        name = html.escape(LOCALE_NAMES[code])
        path = LOCALE_PATHS[code]
        target = path if path.endswith("/") else path + "/"
        if code == locale:
            items.append(f'<strong class="locale-active">{name}</strong>')
        else:
            items.append(
                f'<a class="locale-link" href="{target}" '
                f"onclick=\"event.preventDefault();"
                f"window.aiMusicLabSetLocale('{code}','{target}');\">{name}</a>"
            )
    label = html.escape(t("app.language"))
    return (
        f'<nav class="locale-switcher" aria-label="{label}">'
        + ' <span class="locale-sep">·</span> '.join(items)
        + "</nav>"
    )

THEME = gr.themes.Base(
    primary_hue="cyan",
    secondary_hue="amber",
    neutral_hue="slate",
    radius_size="lg",
).set(
    body_background_fill="#06101a",
    body_background_fill_dark="#06101a",
    body_text_color="#edf5fa",
    body_text_color_dark="#edf5fa",
    body_text_color_subdued="#91a3b3",
    body_text_color_subdued_dark="#91a3b3",
    background_fill_primary="#0b1723",
    background_fill_primary_dark="#0b1723",
    background_fill_secondary="#0e1b28",
    background_fill_secondary_dark="#0e1b28",
    block_background_fill="#0b1723",
    block_background_fill_dark="#0b1723",
    block_border_color="#203344",
    block_border_color_dark="#203344",
    block_label_background_fill="#0b1723",
    block_label_background_fill_dark="#0b1723",
    block_label_text_color="#9db0bf",
    block_label_text_color_dark="#9db0bf",
    input_background_fill="#0d1a27",
    input_background_fill_dark="#0d1a27",
    input_border_color="#294154",
    input_border_color_dark="#294154",
    input_placeholder_color="#718596",
    input_placeholder_color_dark="#718596",
    checkbox_label_background_fill="#0d1a27",
    checkbox_label_background_fill_dark="#0d1a27",
    checkbox_label_background_fill_selected="#103447",
    checkbox_label_background_fill_selected_dark="#103447",
    checkbox_label_text_color="#d2dee7",
    checkbox_label_text_color_dark="#d2dee7",
    button_primary_background_fill="#139fcc",
    button_primary_background_fill_dark="#139fcc",
    button_primary_background_fill_hover="#23b7e5",
    button_primary_background_fill_hover_dark="#23b7e5",
    button_secondary_background_fill="#142433",
    button_secondary_background_fill_dark="#142433",
    button_secondary_text_color="#e7f0f6",
    button_secondary_text_color_dark="#e7f0f6",
    table_even_background_fill="#0b1723",
    table_even_background_fill_dark="#0b1723",
    table_odd_background_fill="#0e1b28",
    table_odd_background_fill_dark="#0e1b28",
    table_border_color="#203344",
    table_border_color_dark="#203344",
)


def _comparison_reset_payload(t: Translator) -> tuple[Any, ...]:
    return (
        t("compare.reset"),
        [],
        empty_figure(t("empty.pick_two")),
        empty_figure(t("empty.pick_two")),
        [],
    )


def _telemetry_comparison_reset_payload(t: Translator) -> tuple[Any, ...]:
    return tuple(
        empty_figure(t("empty.pick_ab_telemetry")) for _ in range(4)
    )


def build_app(
    service: AnalysisService | None = None,
    locale: str = DEFAULT_LOCALE,
) -> gr.Blocks:
    analysis_service = service or AnalysisService()
    t = get_translator(locale)

    def history_snapshot() -> tuple[list[list[Any]], list[tuple[str, str]]]:
        runs = analysis_service.history.list_runs()
        durations: dict[str, float] = {}
        for run in runs:
            try:
                durations[run.run_id] = (
                    analysis_service.history.load_features(
                        run.run_id
                    ).metadata.duration_seconds
                )
            except (KeyError, OSError, ValueError):
                continue
        return (
            history_rows(runs, durations, t),
            analysis_service.version_choices(),
        )

    initial_history, initial_choices = history_snapshot()
    initial_a, initial_b = analysis_service.default_version_pair()

    def telemetry_summary(item: DetectorTelemetry | None) -> dict[str, Any]:
        if item is None:
            return {}
        return {
            "detector": item.detector,
            "scalars": item.scalars,
            "warnings": list(item.warnings),
            "arrays": {
                name: {"shape": list(array.shape), "dtype": str(array.dtype)}
                for name, array in item.arrays.items()
            },
        }

    def telemetry_views(
        telemetry: dict[str, DetectorTelemetry],
        run_id: str | None = None,
    ):
        lofcz = telemetry.get("lofcz")
        fst = telemetry.get("FST")
        if lofcz is None:
            lofcz_spectrum_plot = empty_figure(t("empty.lofcz_telemetry"))
            lofcz_fakeprint_plot = empty_figure(t("empty.fakeprint"))
            peak_rows: list[list[Any]] = []
        else:
            lofcz_spectrum_plot = lofcz_spectrum_figure(lofcz, t)
            lofcz_fakeprint_plot = lofcz_fakeprint_figure(lofcz, t)
            peak_rows = [
                [
                    round(float(item["frequency_hz"]), 2),
                    round(float(item["fakeprint"]), 4),
                ]
                for item in lofcz.scalars.get("strongest_peaks", [])
            ]
        if fst is None:
            fst_segment_plot = empty_figure(t("empty.fst_telemetry"))
            fst_similarity_plot = empty_figure(t("empty.similarity"))
            fst_gate_plot = empty_figure(t("empty.gate"))
        else:
            fst_segment_plot = fst_segment_figure(fst, t)
            fst_similarity_plot = fst_similarity_figure(fst, t)
            fst_gate_plot = fst_gate_figure(fst, t)
        fst_npz = None
        if run_id and fst is not None:
            candidate = (
                analysis_service.history.runs_dir
                / run_id
                / "telemetry"
                / "FST"
                / "arrays.npz"
            )
            if candidate.is_file():
                fst_npz = str(candidate)
        return (
            lofcz_spectrum_plot,
            lofcz_fakeprint_plot,
            peak_rows,
            telemetry_summary(lofcz),
            fst_segment_plot,
            fst_similarity_plot,
            fst_gate_plot,
            telemetry_summary(fst),
            fst_npz,
            interpret_run(telemetry, t),
        )

    def telemetry_comparison_views(outcome):
        lofcz_a = outcome.telemetry_a.get("lofcz")
        lofcz_b = outcome.telemetry_b.get("lofcz")
        fst_a = outcome.telemetry_a.get("FST")
        fst_b = outcome.telemetry_b.get("FST")
        lofcz_plot = (
            lofcz_fakeprint_comparison_figure(lofcz_a, lofcz_b, t)
            if lofcz_a is not None and lofcz_b is not None
            else empty_figure(t("empty.lofcz_ab"))
        )
        if fst_a is not None and fst_b is not None:
            return (
                lofcz_plot,
                fst_segment_comparison_figure(fst_a, fst_b, t),
                fst_gate_comparison_figure(fst_a, fst_b, t),
                fst_similarity_difference_figure(fst_a, fst_b, t),
            )
        return (
            lofcz_plot,
            empty_figure(t("empty.fst_ab")),
            empty_figure(t("empty.fst_ab")),
            empty_figure(t("empty.fst_ab")),
        )

    with gr.Blocks(
        title="AI Music Lab",
        fill_width=True,
        delete_cache=(86_400, 86_400),
    ) as app:
        current_run_id = gr.State(None)
        with gr.Row(elem_classes="lab-shell"):
            with gr.Column(
                scale=3,
                min_width=330,
                elem_classes="left-workbench",
            ):
                gr.HTML(
                    f"""
                    <header class="brand-block">
                      <span class="eyebrow">{t("app.eyebrow")}</span>
                      <h1>{t("app.title")}</h1>
                      <p>{t("app.tagline")}</p>
                    </header>
                    {_language_switcher_html(locale, t)}
                    """
                )

                gr.Markdown(t("app.step.upload"))
                audio = gr.Audio(
                    label=t("app.audio.label"),
                    sources=["upload"],
                    type="filepath",
                    editable=False,
                    waveform_options={
                        "waveform_color": "#23b7e5",
                        "waveform_progress_color": "#f4ad28",
                    },
                    elem_classes="audio-drop",
                )

                gr.Markdown(t("app.step.metadata"))
                metadata_table = gr.Dataframe(
                    headers=[
                        t("table.metadata.parameter"),
                        t("table.metadata.value"),
                        t("table.metadata.unit"),
                    ],
                    value=[],
                    interactive=False,
                    show_label=False,
                    wrap=True,
                    elem_classes="metadata-rail",
                )

                note = gr.Textbox(
                    label=t("app.note.label"),
                    placeholder=t("app.note.placeholder"),
                    lines=2,
                )

                gr.Markdown(t("app.step.detectors"))
                detectors = gr.CheckboxGroup(
                    choices=[
                        (t("app.detectors.lofcz"), "lofcz"),
                        (t("app.detectors.fst"), "FST"),
                    ],
                    value=["lofcz", "FST"],
                    label=t("app.detectors.label"),
                )

                analyze_button = gr.Button(
                    t("app.analyze"),
                    variant="primary",
                    elem_classes="analyze-button",
                )
                status = gr.Markdown(
                    t("app.status.ready"),
                    elem_classes="status-line",
                )
                gr.Markdown(
                    t("app.method_note"),
                    elem_classes="method-note",
                )

            with gr.Column(
                scale=9,
                min_width=650,
                elem_classes="analysis-canvas",
            ):
                detector_summary = gr.HTML(
                    f'<div class="empty-state">{t("app.empty.detectors")}</div>'
                )

                with gr.Tabs():
                    with gr.Tab(t("tab.spectrum")):
                        spectrogram = gr.Plot(
                            empty_figure(t("empty.start")),
                            label=t("plot.spectrogram"),
                            elem_classes="hero-plot",
                        )
                        spectrogram_3d = gr.Plot(
                            empty_figure(t("empty.surface")),
                            label=t("plot.spectrogram_3d"),
                        )
                        high_detail_3d_button = gr.Button(
                            t("app.high_detail"),
                            variant="secondary",
                            elem_classes="high-detail-3d-button",
                        )
                        with gr.Row(elem_classes="secondary-plots"):
                            waveform = gr.Plot(
                                empty_figure(t("empty.rms")),
                                label=t("app.plot.rms_envelope"),
                            )
                            spectrum = gr.Plot(
                                empty_figure(t("empty.spectrum")),
                                label=t("plot.average_spectrum"),
                            )

                    with gr.Tab(t("tab.timeline")):
                        gr.Markdown(t("doc.timeline"))
                        with gr.Row():
                            timeline_window = gr.Slider(
                                minimum=5,
                                maximum=30,
                                value=15,
                                step=1,
                                label=t("app.timeline.window"),
                            )
                            timeline_hop = gr.Slider(
                                minimum=1,
                                maximum=15,
                                value=5,
                                step=1,
                                label=t("app.timeline.hop"),
                            )
                        timeline_button = gr.Button(
                            t("app.timeline.build"),
                            variant="secondary",
                        )
                        timeline_status = gr.Markdown("")
                        timeline_plot = gr.Plot(
                            empty_figure(t("empty.timeline")),
                            label=t("tab.timeline"),
                            elem_classes="hero-plot",
                        )

                    with gr.Tab(t("tab.layers")):
                        gr.Markdown(t("doc.layers"))
                        layer_files = gr.File(
                            label=t("app.layers.files"),
                            file_count="multiple",
                            file_types=[".wav", ".flac", ".mp3"],
                        )
                        layer_button = gr.Button(
                            t("app.layers.button"),
                            variant="secondary",
                        )
                        layer_table = gr.Dataframe(
                            headers=[
                                t("table.layer.name"),
                                "lofcz",
                                t("table.layer.residue"),
                                t("table.layer.duration"),
                                t("table.layer.priority"),
                            ],
                            value=[],
                            interactive=False,
                            wrap=True,
                        )
                        layer_plot = gr.Plot(
                            empty_figure(t("empty.layers")),
                            label=t("telemetry.layers.title"),
                        )

                    with gr.Tab(t("tab.artifacts")):
                        gr.Markdown(t("doc.artifacts"))
                        reference_files = gr.File(
                            label=t("app.artifacts.references"),
                            file_count="multiple",
                            file_types=[".wav", ".flac", ".mp3"],
                        )
                        artifact_button = gr.Button(
                            t("app.artifacts.button"),
                            variant="secondary",
                        )
                        artifact_table = gr.Dataframe(
                            headers=[
                                t("table.artifact.file"),
                                t("table.artifact.attack"),
                                t("table.artifact.rolloff"),
                                t("table.artifact.cliff"),
                                t("table.artifact.noise_floor"),
                                t("table.artifact.flatness"),
                                t("table.artifact.corr_low"),
                                t("table.artifact.corr_high"),
                            ],
                            value=[],
                            interactive=False,
                            wrap=True,
                        )

                    with gr.Tab(t("tab.overview")):
                        overview = gr.HTML(
                            f"""
                            <div class="analysis-guide">
                              <h3>{t("app.overview.heading")}</h3>
                              <p>{t("app.overview.body")}</p>
                            </div>
                            """
                        )

                    with gr.Tab(t("tab.detector_data")):
                        gr.Markdown(t("doc.detector_data"))
                        gr.HTML(help_html("lofcz", "fakeprint", t))
                        lofcz_native_spectrum = gr.Plot(
                            empty_figure(t("empty.run_lofcz")),
                            label=t("telemetry.lofcz.spectrum"),
                        )
                        lofcz_native_fakeprint = gr.Plot(
                            empty_figure(t("empty.run_lofcz")),
                            label="lofcz · native fakeprint",
                        )
                        lofcz_peaks = gr.Dataframe(
                            headers=[
                                t("table.peaks.frequency"),
                                t("table.peaks.fakeprint"),
                            ],
                            value=[],
                            interactive=False,
                            label="lofcz · strongest frequency bins",
                        )
                        lofcz_telemetry_json = gr.JSON(
                            value={},
                            label="lofcz · native configuration and shapes",
                            open=False,
                        )
                        gr.HTML(help_html("FST", "stage1", t))
                        fst_native_segments = gr.Plot(
                            empty_figure(t("empty.run_fst")),
                            label="FST · Stage-1 segment classes",
                        )
                        gr.HTML(help_html("FST", "self_similarity", t))
                        fst_native_similarity = gr.Plot(
                            empty_figure(t("empty.run_fst")),
                            label="FST · self-similarity matrix",
                        )
                        gr.HTML(help_html("FST", "fusion_gate", t))
                        fst_native_gate = gr.Plot(
                            empty_figure(t("empty.run_fst")),
                            label="FST · fusion gate",
                        )
                        fst_telemetry_json = gr.JSON(
                            value={},
                            label="FST · native configuration and shapes",
                            open=False,
                        )
                        fst_telemetry_npz = gr.File(
                            value=None,
                            label=t("app.fst_npz"),
                            interactive=False,
                        )
                        run_interpretation = gr.HTML(
                            interpret_run({}, t),
                        )

                    with gr.Tab(t("tab.comparison")):
                        gr.Markdown(t("doc.comparison"))
                        with gr.Row(elem_classes="comparison-controls"):
                            version_a = gr.Dropdown(
                                choices=initial_choices,
                                value=initial_a,
                                label=t("telemetry.version_a"),
                                info=t("app.version_a.info"),
                            )
                            version_b = gr.Dropdown(
                                choices=initial_choices,
                                value=initial_b,
                                label=t("telemetry.version_b"),
                                info=t("app.version_b.info"),
                            )
                            compare_button = gr.Button(
                                t("app.compare.button"),
                                variant="secondary",
                                elem_classes="compare-button",
                            )
                        with gr.Row(elem_classes="pin-controls"):
                            pin_a_button = gr.Button(
                                t("app.compare.pin"),
                                variant="secondary",
                            )
                            clear_a_button = gr.Button(
                                t("app.compare.unpin"),
                                variant="secondary",
                            )
                        comparison_status = gr.Markdown(t("compare.initial"))
                        detector_comparison = gr.Dataframe(
                            headers=[
                                t("table.detector"),
                                t("telemetry.version_a"),
                                t("telemetry.version_b"),
                                t("table.delta"),
                            ],
                            value=[],
                            interactive=False,
                            label=t("app.compare.detector_label"),
                        )
                        comparison_spectrum = gr.Plot(
                            empty_figure(t("empty.pick_two")),
                            label=t("app.compare.spectrum_label"),
                        )
                        difference = gr.Plot(
                            empty_figure(t("empty.difference")),
                            label=t("app.compare.difference_label"),
                        )
                        comparison_table = gr.Dataframe(
                            headers=[
                                t("table.metric"),
                                t("telemetry.version_a"),
                                t("telemetry.version_b"),
                                t("table.delta"),
                                t("table.unit"),
                            ],
                            value=[],
                            interactive=False,
                            label=t("app.compare.metric_label"),
                        )
                        gr.Markdown(t("app.compare.native_heading"))
                        lofcz_comparison = gr.Plot(
                            empty_figure(t("empty.pick_lofcz")),
                            label="lofcz · native fakeprint A/B",
                        )
                        fst_segment_comparison = gr.Plot(
                            empty_figure(t("empty.pick_fst")),
                            label="FST · Stage-1 A/B",
                        )
                        fst_gate_comparison = gr.Plot(
                            empty_figure(t("empty.pick_fst")),
                            label="FST · fusion gate A/B",
                        )
                        fst_similarity_difference = gr.Plot(
                            empty_figure(t("empty.pick_fst")),
                            label="FST · self-similarity Δ B−A",
                        )

                    with gr.Tab(t("tab.technical")):
                        technical = gr.JSON(
                            value={},
                            label="SHA-256, runtime, raw detector outputs",
                            open=False,
                        )

                gr.HTML(
                    f"""
                    <div class="history-heading">
                      <div>
                        <span class="eyebrow">LOCAL EXPERIMENT LOG</span>
                        <h2>{t("app.history.title")}</h2>
                      </div>
                      <p>{t("app.history.subtitle")}</p>
                    </div>
                    """
                )
                history_table = gr.Dataframe(
                    headers=[
                        t("table.history.date"),
                        t("meta.file"),
                        t("meta.duration"),
                        "lofcz",
                        "FST",
                        t("table.history.note"),
                        t("table.history.run_id"),
                        t("telemetry.version_a"),
                    ],
                    value=initial_history,
                    interactive=False,
                    show_label=False,
                    wrap=True,
                    show_search="filter",
                    elem_classes="history-table",
                )

        def analyze_callback(
            audio_path: str | None,
            selected: list[str],
            run_note: str,
            progress=gr.Progress(),
        ):
            def report(message: str, fraction: float) -> None:
                progress(fraction, desc=message)

            try:
                outcome = analysis_service.analyze(
                    audio_path,
                    selected,
                    run_note,
                    progress=report,
                    t=t,
                )
            except Exception as error:
                raise gr.Error(str(error)) from error

            refreshed_history, choices = history_snapshot()
            value_b = outcome.run.run_id
            value_a, _ = analysis_service.default_version_pair()
            safe_filename = html.escape(outcome.features.metadata.filename)
            overview_html = f"""
            <div class="analysis-guide">
              <span class="eyebrow">CURRENT RUN</span>
              <h3>{safe_filename}</h3>
              <p>{t("app.run_overview", run_id=outcome.run.run_id)}</p>
            </div>
            """
            return (
                t("app.status.done", run_id=outcome.run.run_id),
                outcome.run.run_id,
                detector_cards(outcome.run.results, t),
                metadata_rows(outcome.features, t),
                spectrogram_figure(outcome.features, t),
                waveform_figure(outcome.features, t),
                spectrum_figure(outcome.features, t=t),
                spectrogram_3d_figure(outcome.features, detail="preview", t=t),
                *telemetry_views(outcome.telemetry, outcome.run.run_id),
                overview_html,
                technical_payload(outcome),
                refreshed_history,
                gr.update(choices=choices, value=value_a),
                gr.update(choices=choices, value=value_b),
                *_comparison_reset_payload(t),
                *_telemetry_comparison_reset_payload(t),
            )

        analyze_button.click(
            fn=analyze_callback,
            inputs=[audio, detectors, note],
            outputs=[
                status,
                current_run_id,
                detector_summary,
                metadata_table,
                spectrogram,
                waveform,
                spectrum,
                spectrogram_3d,
                lofcz_native_spectrum,
                lofcz_native_fakeprint,
                lofcz_peaks,
                lofcz_telemetry_json,
                fst_native_segments,
                fst_native_similarity,
                fst_native_gate,
                fst_telemetry_json,
                fst_telemetry_npz,
                run_interpretation,
                overview,
                technical,
                history_table,
                version_a,
                version_b,
                comparison_status,
                detector_comparison,
                comparison_spectrum,
                difference,
                comparison_table,
                lofcz_comparison,
                fst_segment_comparison,
                fst_gate_comparison,
                fst_similarity_difference,
            ],
            show_progress="full",
            scroll_to_output=True,
        )

        def high_detail_3d_callback(run_id: str | None):
            if not run_id:
                raise gr.Error(t("error.analyze_first"))
            try:
                features = analysis_service.load_features(run_id)
            except (KeyError, OSError, ValueError) as error:
                raise gr.Error(str(error)) from error
            return spectrogram_3d_figure(features, detail="high", t=t)

        high_detail_3d_button.click(
            fn=high_detail_3d_callback,
            inputs=[current_run_id],
            outputs=[spectrogram_3d],
            show_progress="full",
        )

        def timeline_callback(
            run_id: str | None,
            window_seconds: float,
            hop_seconds: float,
        ):
            if not run_id:
                raise gr.Error(t("error.analyze_first"))
            try:
                timeline = analysis_service.build_timeline(
                    run_id,
                    window_seconds=float(window_seconds),
                    hop_seconds=float(hop_seconds),
                    t=t,
                )
                fst = analysis_service.history.load_telemetry(run_id).get("FST")
            except (KeyError, OSError, RuntimeError, ValueError) as error:
                raise gr.Error(str(error)) from error
            return timeline_summary(timeline, t), timeline_figure(timeline, fst, t)

        timeline_button.click(
            fn=timeline_callback,
            inputs=[current_run_id, timeline_window, timeline_hop],
            outputs=[timeline_status, timeline_plot],
            show_progress="full",
        )

        def layer_callback(files, progress=gr.Progress()):
            paths = [
                item if isinstance(item, str) else getattr(item, "name", None)
                for item in (files or [])
            ]
            try:
                results = analysis_service.sweep_layers(
                    [path for path in paths if path],
                    lambda message, fraction: progress(fraction, desc=message),
                    t=t,
                )
            except (OSError, RuntimeError, ValueError) as error:
                raise gr.Error(str(error)) from error
            return layer_rows(results, t), layer_ranking_figure(results, t)

        layer_button.click(
            fn=layer_callback,
            inputs=[layer_files],
            outputs=[layer_table, layer_plot],
            show_progress="full",
        )

        def artifact_callback(run_id: str | None, files, progress=gr.Progress()):
            paths = [
                item if isinstance(item, str) else getattr(item, "name", None)
                for item in (files or [])
            ]
            try:
                results = analysis_service.measure_artifacts_batch(
                    run_id,
                    [path for path in paths if path],
                    lambda message, fraction: progress(fraction, desc=message),
                    t=t,
                )
            except (KeyError, OSError, RuntimeError, ValueError) as error:
                raise gr.Error(str(error)) from error
            return artifact_rows(results, t)

        artifact_button.click(
            fn=artifact_callback,
            inputs=[current_run_id, reference_files],
            outputs=[artifact_table],
            show_progress="full",
        )

        def compare_callback(run_a_id: str | None, run_b_id: str | None):
            if not run_a_id or not run_b_id:
                raise gr.Error(t("error.pick_both"))
            try:
                outcome = analysis_service.compare_runs(run_a_id, run_b_id, t=t)
            except (KeyError, OSError, ValueError) as error:
                raise gr.Error(str(error)) from error

            spectrum_plot = spectrum_figure(
                outcome.features_b,
                outcome.features_a,
                current_label=t("telemetry.version_b"),
                baseline_label=t("telemetry.version_a"),
                t=t,
            )
            if outcome.comparison is None:
                difference_plot = empty_figure(t("empty.heatmap_duration"))
                message = t(
                    "compare.duration_mismatch",
                    version_a=outcome.run_a.filename,
                    version_b=outcome.run_b.filename,
                )
            else:
                difference_plot = difference_figure(outcome.comparison, t)
                message = t(
                    "compare.result",
                    version_a=outcome.run_a.filename,
                    version_b=outcome.run_b.filename,
                )
            return (
                message,
                detector_delta_rows(outcome, t),
                spectrum_plot,
                difference_plot,
                comparison_metric_rows(outcome, t),
                *telemetry_comparison_views(outcome),
            )

        compare_button.click(
            fn=compare_callback,
            inputs=[version_a, version_b],
            outputs=[
                comparison_status,
                detector_comparison,
                comparison_spectrum,
                difference,
                comparison_table,
                lofcz_comparison,
                fst_segment_comparison,
                fst_gate_comparison,
                fst_similarity_difference,
            ],
        )

        def pin_a_callback(run_id: str | None):
            if not run_id:
                raise gr.Error(t("error.pick_a"))
            pinned = analysis_service.pin_version_a(run_id)
            refreshed_history, choices = history_snapshot()
            value_a, value_b = analysis_service.default_version_pair()
            return (
                t("compare.pinned", filename=pinned.filename),
                refreshed_history,
                gr.update(choices=choices, value=value_a),
                gr.update(choices=choices, value=value_b),
            )

        pin_a_button.click(
            fn=pin_a_callback,
            inputs=[version_a],
            outputs=[comparison_status, history_table, version_a, version_b],
        )

        def clear_a_callback():
            analysis_service.pin_version_a(None)
            refreshed_history, choices = history_snapshot()
            value_a, value_b = analysis_service.default_version_pair()
            return (
                t("compare.unpinned"),
                refreshed_history,
                gr.update(choices=choices, value=value_a),
                gr.update(choices=choices, value=value_b),
            )

        clear_a_button.click(
            fn=clear_a_callback,
            outputs=[comparison_status, history_table, version_a, version_b],
        )

    return app


def build_server(service: AnalysisService | None = None):
    """Mount one interface per locale, all sharing a single analysis service.

    Building separately per locale is what lets every string be translated,
    including Plotly axis titles and generated HTML that a live language switch
    would have to regenerate by hand.

    Mount order matters: the root mount swallows every unmatched path, so the
    locale paths have to be registered first, and a bare ``/ru`` needs its own
    redirect or it would 404 before Gradio's ``/ru/`` mount is reached.
    """
    analysis_service = service or AnalysisService()
    head = playback_sync_head() + language_memory_head()
    fastapi_app = FastAPI()

    non_default = [code for code in LOCALES if code != DEFAULT_LOCALE]
    for code in non_default:
        path = LOCALE_PATHS[code]

        def _redirect(target: str = path + "/") -> RedirectResponse:
            return RedirectResponse(target)

        fastapi_app.get(path)(_redirect)

    for code in non_default + [DEFAULT_LOCALE]:
        blocks = build_app(analysis_service, locale=code).queue(
            default_concurrency_limit=1
        )
        fastapi_app = gr.mount_gradio_app(
            fastapi_app,
            blocks,
            path=LOCALE_PATHS[code],
            theme=THEME,
            css_paths=[CSS_PATH],
            head=head,
            show_error=True,
        )
    return fastapi_app


def main() -> None:
    host = os.environ.get("AI_MUSIC_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("AI_MUSIC_UI_PORT", "7860"))
    uvicorn.run(build_server(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
