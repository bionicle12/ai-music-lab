from __future__ import annotations

import html
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import gradio as gr
import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .plots import (
    difference_figure,
    empty_figure,
    spectrogram_3d_figure,
    spectrogram_figure,
    spectrum_figure,
    waveform_figure,
)
from .disclosure import MIDI_GUIDES, disclosure_html
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
from .midi_preview import (
    piano_roll_figure,
    preview_audio,
    preview_summary,
    read_midi,
)
from .muscriptor import AdapterError, instrument_choices
from .readiness import can_transcribe
from .restart import is_loopback, schedule_restart
from .settings import MODEL_SIZES, resolve_token, token_fingerprint
from .ui_presenters import (
    artifact_rows,
    comparison_metric_rows,
    detector_cards,
    detector_delta_rows,
    history_rows,
    layer_rows,
    file_card_html,
    metadata_rows,
    pull_message,
    readiness_disclosure,
    readiness_html,
    repo_status_rows,
    technical_payload,
    timeline_summary,
)
from .ui_service import AnalysisService

ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "music_lab_ui" / "styles.css"
STATIC_DIR = ROOT / "music_lab_ui" / "static"
PLAYBACK_SYNC_PATH = STATIC_DIR / "playback_sync.js"
PLOT_RESIZE_PATH = STATIC_DIR / "plot_resize.js"
SETTINGS_MODAL_PATH = STATIC_DIR / "settings_modal.js"
RESTART_PATH = STATIC_DIR / "restart.js"
FONTS_CSS_PATH = STATIC_DIR / "fonts" / "fonts.css"

#: Where `static/` is served from. Deliberately not `/static` or `/assets` —
#: Gradio reserves both and serves its own bundled fonts from `/static/fonts/`.
ASSET_MOUNT = "/lab-assets"


#: Key used in localStorage. Bumping it resets everyone's stored choice.
LANGUAGE_STORAGE_KEY = "ai-music-lab.locale"

#: The button carries no text: `gr.Button` escapes its value, so markup would
#: appear as source on the page, and neither vendored family has a reload arrow
#: to fall back on. The icon is a CSS mask instead, which keeps `currentColor`
#: driving its colour. See `button.restart-button` in styles.css.
RESTART_LABEL = ""


def _inline_script(path: Path) -> str:
    """Inline a browser script; Gradio serves no static dir by default."""
    if not path.is_file():
        return ""
    return f"<script>\n{path.read_text(encoding='utf-8')}\n</script>"


def playback_sync_head() -> str:
    return _inline_script(PLAYBACK_SYNC_PATH)


def plot_resize_head() -> str:
    """Relayout charts that were first drawn on a hidden tab (static/plot_resize.js)."""
    return _inline_script(PLOT_RESIZE_PATH)


def settings_modal_head() -> str:
    """Escape and backdrop-click for the settings dialog (static/settings_modal.js)."""
    return _inline_script(SETTINGS_MODAL_PATH)


def restart_head() -> str:
    """Confirm dialog and wait-for-the-port logic (static/restart.js)."""
    return _inline_script(RESTART_PATH)


def font_face_head() -> str:
    """Inline the vendored @font-face rules (static/fonts/SOURCE.md).

    In `head=` rather than `styles.css` for two reasons. Gradio parses custom
    CSS rule by rule and rebuilds it, so an `@font-face` survives only as the
    browser happens to re-serialise it — a needless risk for the one thing that
    must not fail. And `head=` is injected last and verbatim.
    """
    if not FONTS_CSS_PATH.is_file():
        return ""
    return f"<style>\n{FONTS_CSS_PATH.read_text(encoding='utf-8')}\n</style>"


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

#: `gr.themes.Font`, never `gr.themes.GoogleFont`. GoogleFont emits a stylesheet
#: link to fonts.googleapis.com for any family Gradio does not already bundle,
#: and this app is not allowed to talk to the network; plain `Font` has an empty
#: stylesheet, so the offline promise is structural rather than a matter of
#: remembering — `tests/test_theme.py` asserts it. Font objects rather than bare
#: strings because Gradio compares theme fonts pairwise and its `Font.__eq__`
#: raises on a string. The faces themselves are vendored; see
#: static/fonts/SOURCE.md.
UI_FONT = [gr.themes.Font(name) for name in ("Manrope", "Segoe UI", "sans-serif")]
MONO_FONT = [
    gr.themes.Font(name) for name in ("JetBrains Mono", "Consolas", "monospace")
]

#: The palette. It lives on the theme, not in a `:root` block in styles.css,
#: because Gradio appends theme.css AFTER custom CSS — a `:root` there would
#: lose every tie. Any attribute without a leading underscore becomes a CSS
#: custom property, so these are `--lab-*` on the page and a `"*lab_cyan"`
#: reference below compiles to `var(--lab-cyan)`.
#:
#: Read as an instrument panel: five surface steps that are actually
#: distinguishable, hairlines that recede, and an accent split by role so cyan
#: only appears where it means "signal". It used to be smeared across the page
#: background and every border, which is how an accent stops meaning anything.
LAB_PALETTE: dict[str, str] = {
    "lab_sunken": "#04090f",  # chart paper, input wells
    "lab_bg": "#070f18",
    "lab_surface": "#0b1521",  # cards, panels
    "lab_surface_2": "#111d2b",  # raised: modal, open disclosure
    "lab_surface_3": "#16232f",  # hover, selected row
    "lab_line": "#1a2836",
    "lab_line_strong": "#2a3f52",
    "lab_text": "#e8f0f7",
    "lab_text_2": "#b7c6d3",  # body prose
    "lab_muted": "#8698a8",
    # Signal: score values, active tab, focus ring, info badge, links.
    "lab_cyan": "#23b7e5",
    "lab_cyan_ink": "#7ee7ff",  # cyan text on dark
    "lab_cyan_dim": "#17789a",  # large fills, where full cyan would shout
    "lab_cyan_wash": "rgba(35, 183, 229, 0.07)",
    "lab_amber": "#f4ad28",
    "lab_amber_ink": "#ffd27a",
    "lab_amber_wash": "rgba(244, 173, 40, 0.10)",
    "lab_red": "#ef5b5b",
    "lab_red_ink": "#ff9a9a",
    "lab_green": "#4bd19b",
    "lab_green_ink": "#8ee9c3",
    # Semantic aliases, so components stop naming colours.
    "lab_info": "*lab_cyan",
    "lab_warn": "*lab_amber",
    "lab_ok": "*lab_green",
    "lab_danger": "*lab_red",
    # Masked, so the stroke colour inside is irrelevant.
    "restart_icon": 'url("data:image/svg+xml;utf8,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 16 16\'%3E%3Cpath d=\'M13.4 8a5.4 5.4 0 1 1-1.6-3.8\' fill=\'none\' stroke=\'%23000\' stroke-width=\'1.7\' stroke-linecap=\'round\'/%3E%3Cpath d=\'M12.4 1.7v3h-3\' fill=\'none\' stroke=\'%23000\' stroke-width=\'1.7\' stroke-linecap=\'round\' stroke-linejoin=\'round\'/%3E%3C/svg%3E")',
}


def _lab_theme() -> gr.themes.Base:
    theme = gr.themes.Base(
        primary_hue="cyan",
        secondary_hue="amber",
        neutral_hue="slate",
        radius_size="lg",
        font=UI_FONT,
        font_mono=MONO_FONT,
    )
    for name, value in LAB_PALETTE.items():
        setattr(theme, name, value)
    return theme.set(
        body_background_fill="*lab_bg",
        body_background_fill_dark="*lab_bg",
        body_text_color="*lab_text",
        body_text_color_dark="*lab_text",
        body_text_color_subdued="*lab_muted",
        body_text_color_subdued_dark="*lab_muted",
        background_fill_primary="*lab_surface",
        background_fill_primary_dark="*lab_surface",
        background_fill_secondary="*lab_surface_2",
        background_fill_secondary_dark="*lab_surface_2",
        block_background_fill="*lab_surface",
        block_background_fill_dark="*lab_surface",
        block_border_color="*lab_line",
        block_border_color_dark="*lab_line",
        block_label_background_fill="*lab_surface",
        block_label_background_fill_dark="*lab_surface",
        block_label_text_color="*lab_muted",
        block_label_text_color_dark="*lab_muted",
        code_background_fill="#102435",
        code_background_fill_dark="#102435",
        input_background_fill="*lab_sunken",
        input_background_fill_dark="*lab_sunken",
        input_border_color="*lab_line_strong",
        input_border_color_dark="*lab_line_strong",
        input_border_color_focus="*lab_cyan",
        input_border_color_focus_dark="*lab_cyan",
        input_border_width="1px",
        input_border_width_dark="1px",
        input_placeholder_color="*lab_muted",
        input_placeholder_color_dark="*lab_muted",
        checkbox_background_color="*lab_sunken",
        checkbox_background_color_dark="*lab_sunken",
        checkbox_background_color_selected="*lab_cyan_dim",
        checkbox_background_color_selected_dark="*lab_cyan_dim",
        checkbox_label_background_fill="*lab_surface_2",
        checkbox_label_background_fill_dark="*lab_surface_2",
        checkbox_label_background_fill_selected="#103447",
        checkbox_label_background_fill_selected_dark="#103447",
        checkbox_label_text_color="*lab_text_2",
        checkbox_label_text_color_dark="*lab_text_2",
        button_primary_background_fill="*lab_cyan_dim",
        button_primary_background_fill_dark="*lab_cyan_dim",
        button_primary_background_fill_hover="*lab_cyan",
        button_primary_background_fill_hover_dark="*lab_cyan",
        button_primary_text_color="#04121a",
        button_primary_text_color_dark="#04121a",
        button_primary_shadow="none",
        button_primary_shadow_dark="none",
        button_secondary_background_fill="*lab_surface_2",
        button_secondary_background_fill_dark="*lab_surface_2",
        button_secondary_background_fill_hover="*lab_surface_3",
        button_secondary_background_fill_hover_dark="*lab_surface_3",
        button_secondary_border_color="*lab_line_strong",
        button_secondary_border_color_dark="*lab_line_strong",
        button_secondary_text_color="*lab_text",
        button_secondary_text_color_dark="*lab_text",
        button_large_text_weight="700",
        table_even_background_fill="*lab_surface",
        table_even_background_fill_dark="*lab_surface",
        table_odd_background_fill="*lab_surface_2",
        table_odd_background_fill_dark="*lab_surface_2",
        table_border_color="*lab_line",
        table_border_color_dark="*lab_line",
        table_row_focus="*lab_surface_3",
        table_row_focus_dark="*lab_surface_3",
        # Tab labels.
        section_header_text_size="*text_lg",
        section_header_text_weight="600",
    )


THEME = _lab_theme()


def _settings_panel(
    service: AnalysisService,
    t: Translator,
) -> tuple[Any, dict[str, Any]]:
    """Build the settings panel. Wiring happens later, once every tab exists.

    Components only: the readiness checklist is also shown in the MIDI tab, and
    a callback here has to update both, which is impossible before that tab has
    been created.
    """
    settings = service.settings()
    report = service.readiness()
    controls: dict[str, Any] = {}
    # Rendered as a centred overlay by CSS. Gradio 6.20 has no modal layout, and
    # the panel outgrew the sidebar it started in — it is meant to hold more
    # than muscriptor eventually.
    with gr.Column(visible=False, elem_classes="settings-modal") as panel:
        with gr.Row(elem_classes="settings-modal-head"):
            gr.Markdown(t("settings.title"))
            controls["close"] = gr.Button(
                "✕",
                elem_classes="settings-close",
                scale=0,
                min_width=44,
            )
        controls["readiness"] = gr.HTML(readiness_html(report, t))
        controls["check"] = gr.Button(t("settings.check"), variant="secondary")

        gr.Markdown(t("settings.token.heading"))
        gr.Markdown(t("settings.token.intro"))
        gr.HTML(disclosure_html("token/handling", t))
        gr.HTML(t("settings.links"))
        controls["token"] = gr.Textbox(
            label=t("settings.token.label"),
            placeholder=t("settings.token.placeholder"),
            type="password",
            value="",
        )
        with gr.Row():
            controls["save_token"] = gr.Button(
                t("settings.token.save"), variant="primary"
            )
            controls["clear_token"] = gr.Button(t("settings.token.clear"))
        controls["token_status"] = gr.Markdown(_token_status(service, t))

        # The checkbox is where the statement is load-bearing — the run is gated
        # on it — so it stays visible and the long form sits behind the badge.
        controls["license"] = gr.Checkbox(
            label=t("settings.license.accept"),
            value=settings.weights_license_accepted,
        )
        gr.HTML(disclosure_html("licence/weights", t))

        gr.Markdown(t("settings.model.heading"))
        controls["model"] = gr.Radio(
            choices=[
                (t(f"settings.model.{size}"), size) for size in MODEL_SIZES
            ],
            value=settings.muscriptor_model,
            label=t("settings.model.label"),
        )
        gr.Markdown(t("settings.model.note"))
        controls["download"] = gr.Button(t("settings.download"), variant="primary")
        controls["download_status"] = gr.Markdown("")

        gr.Markdown(t("settings.repos.heading"))
        gr.Markdown(t("settings.repos.note"))
        controls["repos"] = gr.Dataframe(
            headers=[
                t("table.repo.name"),
                t("table.repo.head"),
                t("table.repo.branch"),
                t("table.repo.state"),
                t("table.repo.pinned"),
            ],
            value=[],
            interactive=False,
            wrap=True,
        )
        with gr.Row():
            controls["refresh_repos"] = gr.Button(t("settings.repos.refresh"))
            controls["pull"] = gr.Button(t("settings.repos.pull"))
        controls["repo_log"] = gr.Markdown("")
        controls["close_bottom"] = gr.Button(t("settings.close"))
    return panel, controls


def _token_status(service: AnalysisService, t: Translator) -> str:
    token, source = resolve_token(service.settings())
    if source == "env":
        return t("settings.token.status.env")
    if source == "settings":
        return t(
            "settings.token.status.stored",
            fingerprint=token_fingerprint(token),
        )
    return t("settings.token.status.none")


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
    initial_settings = analysis_service.settings()
    # No probe here on purpose: build_app must never spawn a subprocess, and the
    # test suite builds this interface several times per run.
    initial_readiness = analysis_service.readiness()

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
        settings_open = gr.State(False)
        # A list, not a name->path map: two stems called bass.wav in different
        # folders would collide in a map, and sweep_layers re-sorts its results
        # so a row index only means something against the list it produced.
        layer_paths = gr.State([])
        selected_stem = gr.State(None)
        # A hidden Textbox, not a State: `gr.State` lives only on the server,
        # so a value returned from a `js=` handler never reaches it and the
        # confirmation silently read as "cancelled".
        restart_ack = gr.Textbox(value="", visible=False)

        # Declared at the top of the Blocks, not inside a column. A dialog has to
        # escape every stacking context on the page, and `position: fixed` alone
        # does not do that: the sticky sidebar it used to live in trapped it
        # behind the analysis canvas no matter how high its z-index went.
        settings_panel, settings_controls = _settings_panel(analysis_service, t)

        with gr.Row(elem_classes="lab-shell"):
            with gr.Column(
                scale=3,
                min_width=330,
                elem_classes="left-workbench",
            ):
                with gr.Row(elem_classes="brand-row"):
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
                    restart_button = gr.Button(
                        RESTART_LABEL,
                        elem_classes="restart-button",
                        scale=0,
                        min_width=44,
                    )
                restart_status = gr.Markdown("", elem_classes="restart-status")

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
                # The player above is a segment view whether we like it or not:
                # Gradio hardcodes wavesurfer at 20 px per second, so a 3:48
                # track would need 4560 px and this column is 330. This chart is
                # the whole track — and because it carries `time_axis`, clicking
                # it seeks the same player and the playhead follows across both.
                waveform = gr.Plot(
                    empty_figure(t("empty.rms"), height=118),
                    label=t("app.plot.fulltrack"),
                    elem_classes="track-overview",
                )

                file_card = gr.HTML(file_card_html(None, t))

                note = gr.Textbox(
                    label=t("app.note.label"),
                    placeholder=t("app.note.placeholder"),
                    lines=2,
                )

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

                # Named, with ids, so "send to MIDI" in Layers can move the user
                # across both nesting levels in one callback.
                with gr.Tabs(elem_classes="workspace-tabs") as workspace_tabs:
                    with gr.Tab(t("tab.group.analysis"), id="analysis"):
                        with gr.Tabs():
                            with gr.Tab(t("tab.spectrum")):
                                gr.HTML(disclosure_html("spectrum/reading", t))
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
                                spectrum = gr.Plot(
                                    empty_figure(t("empty.spectrum")),
                                    label=t("plot.average_spectrum"),
                                )

                            with gr.Tab(t("tab.timeline")):
                                gr.Markdown(t("lead.timeline"))
                                gr.HTML(disclosure_html("timeline/method", t))
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
                                gr.Markdown(t("lead.layers"))
                                with gr.Column(elem_classes="guide-stack"):
                                    gr.HTML(
                                        disclosure_html("layers/what_to_load", t)
                                    )
                                    gr.HTML(
                                        disclosure_html("layers/separation", t)
                                    )
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
                                with gr.Row(elem_classes="layer-handoff"):
                                    layer_pick_status = gr.Markdown(
                                        t("midi.source.none")
                                    )
                                    send_to_midi_button = gr.Button(
                                        t("layers.send_to_midi"),
                                        variant="secondary",
                                    )
                                layer_plot = gr.Plot(
                                    empty_figure(t("empty.layers")),
                                    label=t("telemetry.layers.title"),
                                )

                            with gr.Tab(t("tab.artifacts")):
                                gr.Markdown(t("lead.artifacts"))
                                with gr.Column(elem_classes="guide-stack"):
                                    gr.HTML(
                                        disclosure_html("artifacts/compare", t)
                                    )
                                    gr.HTML(
                                        disclosure_html("artifacts/metrics", t)
                                    )
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

                            with gr.Tab(t("tab.detector_data")):
                                gr.Markdown(t("lead.detector_data"))
                                # Each badge explains the chart directly beneath
                                # it. These two used to be one apart: the
                                # fakeprint explanation sat above the spectrum
                                # chart, and the fakeprint chart had none.
                                gr.HTML(disclosure_html("lofcz/lower_hull", t))
                                lofcz_native_spectrum = gr.Plot(
                                    empty_figure(t("empty.run_lofcz")),
                                    label=t("telemetry.lofcz.spectrum"),
                                )
                                gr.HTML(disclosure_html("lofcz/fakeprint", t))
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
                                gr.HTML(disclosure_html("fst/stage1", t))
                                fst_native_segments = gr.Plot(
                                    empty_figure(t("empty.run_fst")),
                                    label="FST · Stage-1 segment classes",
                                )
                                gr.HTML(disclosure_html("fst/self_similarity", t))
                                fst_native_similarity = gr.Plot(
                                    empty_figure(t("empty.run_fst")),
                                    label="FST · self-similarity matrix",
                                )
                                gr.HTML(disclosure_html("fst/fusion_gate", t))
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
                                gr.Markdown(t("lead.comparison"))
                                gr.HTML(disclosure_html("comparison/method", t))
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
                                # The sidebar shows a file card now. The full
                                # eleven-row table moves here, where a tab that
                                # held one collapsed JSON had room to spare —
                                # every value stays reachable.
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
                                technical = gr.JSON(
                                    value={},
                                    label="SHA-256, runtime, raw detector outputs",
                                    open=False,
                                )

                    # No group-level text: it would sit outside both sub-tab
                    # panels and therefore render on both of them at once.
                    with gr.Tab(t("tab.group.editing"), id="editing"):
                        with gr.Tabs() as editing_tabs:
                            with gr.Tab(t("tab.edit.sunofix"), id="sunofix"):
                                gr.Markdown(t("lead.sunofix"))
                            with gr.Tab(t("tab.edit.midi"), id="midi"):
                                gr.Markdown(t("lead.midi"))
                                with gr.Column(elem_classes="guide-stack"):
                                    gr.HTML(disclosure_html("midi/stems", t))
                                    gr.HTML(
                                        disclosure_html("licence/weights", t)
                                    )
                                    # The same checklist the settings dialog
                                    # shows, collapsed to a line: someone who
                                    # lands here first still has to be able to
                                    # see why the button is dead. It opens
                                    # itself when the setup is incomplete.
                                    midi_readiness = gr.HTML(
                                        readiness_disclosure(initial_readiness, t)
                                    )
                                # The dialog only configures muscriptor, so it
                                # opens from the tab that needs it rather than
                                # from the app title, where it read as global.
                                settings_button = gr.Button(
                                    t("settings.open"),
                                    variant="secondary",
                                    elem_classes="settings-open",
                                )

                                midi_source = gr.Radio(
                                    choices=[
                                        (t("midi.source.stem"), "stem"),
                                        (t("midi.source.run"), "run"),
                                        (t("midi.source.upload"), "upload"),
                                    ],
                                    value="upload",
                                    label=t("midi.source.label"),
                                )
                                midi_upload = gr.File(
                                    label=t("midi.upload.label"),
                                    file_count="single",
                                    file_types=[".wav", ".flac", ".mp3"],
                                )
                                midi_source_label = gr.Markdown(
                                    t("midi.source.none")
                                )
                                midi_model = gr.Radio(
                                    choices=[
                                        (t(f"settings.model.{size}"), size)
                                        for size in MODEL_SIZES
                                    ],
                                    value=initial_settings.muscriptor_model,
                                    label=t("midi.model.label"),
                                )
                                # Pick from the model's own vocabulary rather
                                # than typing names it may not know: a typo in
                                # a free-text field silently transcribed
                                # everything instead of the one part asked for.
                                midi_instruments = gr.CheckboxGroup(
                                    choices=instrument_choices(),
                                    value=[],
                                    label=t("midi.instruments.label"),
                                    info=t("midi.instruments.info"),
                                    elem_classes="instrument-picker",
                                )
                                midi_button = gr.Button(
                                    t("midi.run"),
                                    variant="primary",
                                )
                                midi_status = gr.Markdown(t("midi.status.idle"))
                                midi_roll = gr.Plot(
                                    empty_figure(t("midi.empty.notes")),
                                    label=t("midi.plot.label"),
                                    elem_classes="hero-plot",
                                )
                                midi_preview_audio = gr.Audio(
                                    value=None,
                                    label=t("midi.preview.label"),
                                    interactive=False,
                                    elem_classes="midi-preview",
                                    waveform_options={
                                        "waveform_color": "#9d7bf5",
                                        "waveform_progress_color": "#f4ad28",
                                    },
                                )
                                midi_preview_summary = gr.Markdown("")
                                gr.Markdown(t("midi.preview.note"))
                                gr.HTML(disclosure_html("midi/reproducibility", t))
                                midi_file = gr.File(
                                    value=None,
                                    label=t("midi.file.label"),
                                    interactive=False,
                                )
                                midi_payload = gr.JSON(
                                    value={},
                                    label=t("midi.payload.label"),
                                    open=False,
                                )
                                # One per row, full width: a how-to squeezed
                                # into a quarter-column is not readable.
                                with gr.Column(elem_classes="guide-stack"):
                                    for key in MIDI_GUIDES:
                                        gr.HTML(disclosure_html(key, t))

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

        def preview_callback(audio_path: str | None):
            """Draw the dropped file before anything is analysed.

            The player and the strip below it are one instrument — a segment
            view and a whole-track view of the same audio — so a filled player
            above an empty strip reads as broken rather than as waiting. The
            run recomputes both from the full extraction and overwrites this.
            """
            if not audio_path:
                return empty_figure(t("empty.rms"), height=118), file_card_html(None, t)
            try:
                features = analysis_service.preview(audio_path, t=t)
            except Exception as error:
                # A file that cannot be read should say so where its waveform
                # would have been, not as a toast over an empty sidebar.
                return empty_figure(str(error), height=118), file_card_html(None, t)
            return waveform_figure(features, t), file_card_html(features, t)

        audio.change(
            fn=preview_callback,
            inputs=audio,
            outputs=[waveform, file_card],
            show_progress="minimal",
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
            return (
                t("app.status.done", run_id=outcome.run.run_id),
                outcome.run.run_id,
                detector_cards(outcome.run.results, t),
                file_card_html(outcome.features, t),
                metadata_rows(outcome.features, t),
                spectrogram_figure(outcome.features, t),
                waveform_figure(outcome.features, t),
                spectrum_figure(outcome.features, t=t),
                spectrogram_3d_figure(outcome.features, detail="preview", t=t),
                *telemetry_views(outcome.telemetry, outcome.run.run_id),
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
                file_card,
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
            # The path list is built from the same sorted results as the rows,
            # so index N of one always refers to index N of the other.
            return (
                layer_rows(results, t),
                layer_ranking_figure(results, t),
                [item.path for item in results],
                None,
                t("midi.source.none"),
            )

        layer_button.click(
            fn=layer_callback,
            inputs=[layer_files],
            outputs=[
                layer_table,
                layer_plot,
                layer_paths,
                selected_stem,
                layer_pick_status,
            ],
            show_progress="full",
        )

        def pick_stem_callback(paths: list[str | None], event: gr.SelectData):
            index = event.index
            row = index[0] if isinstance(index, (list, tuple)) else index
            if row is None or row >= len(paths) or not paths[row]:
                return None, t("layers.pick.none")
            chosen = paths[row]
            return chosen, t("layers.pick.selected", name=Path(chosen).name)

        layer_table.select(
            fn=pick_stem_callback,
            inputs=[layer_paths],
            outputs=[selected_stem, layer_pick_status],
        )

        def send_to_midi_callback(stem: str | None):
            if not stem:
                raise gr.Error(t("error.pick_stem"))
            return (
                gr.Tabs(selected="editing"),
                gr.Tabs(selected="midi"),
                "stem",
                t("midi.source.selected", name=Path(stem).name),
            )

        send_to_midi_button.click(
            fn=send_to_midi_callback,
            inputs=[selected_stem],
            outputs=[
                workspace_tabs,
                editing_tabs,
                midi_source,
                midi_source_label,
            ],
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

        # ---- restart -------------------------------------------------------

        def restart_callback(confirmed: str):
            """Only the confirmed path restarts anything.

            The dialog runs in `js` before this, so a cancelled prompt arrives
            here as False rather than being asked about after the fact.
            """
            if confirmed != "yes":
                return gr.update()
            host = os.environ.get("AI_MUSIC_UI_HOST", "127.0.0.1")
            if not is_loopback(host):
                # Bouncing a server from a web page is fine on your own machine
                # and rude on a network.
                raise gr.Error(t("error.restart_remote", host=host))
            schedule_restart()
            return t("app.restart.running")

        restart_button.click(
            fn=restart_callback,
            inputs=[restart_ack],
            outputs=[restart_status],
            js=f"""
            () => {{
              return [window.aiLabConfirmRestart({json.dumps(t("app.restart.confirm"))}) ? "yes" : ""];
            }}
            """,
        ).then(
            fn=None,
            js="() => { window.aiLabAwaitRestart(); }",
        )

        # ---- settings panel ----------------------------------------------

        def toggle_settings(is_open: bool):
            return (not is_open), gr.update(visible=not is_open)

        settings_button.click(
            fn=toggle_settings,
            inputs=[settings_open],
            outputs=[settings_open, settings_panel],
        )
        for key in ("close", "close_bottom"):
            settings_controls[key].click(
                fn=lambda: (False, gr.update(visible=False)),
                outputs=[settings_open, settings_panel],
            )

        def refreshed_readiness(*, probe: bool = False):
            report = analysis_service.readiness(probe=probe)
            rendered = readiness_html(report, t)
            return rendered, rendered

        def save_token_callback(token: str):
            if not token.strip():
                return (
                    t("settings.token.empty"),
                    *refreshed_readiness(),
                    gr.update(),
                )
            analysis_service.save_settings(
                replace(analysis_service.settings(), hf_token=token.strip())
            )
            return (
                _token_status(analysis_service, t),
                *refreshed_readiness(),
                # Never echo the token back into the field.
                gr.update(value=""),
            )

        settings_controls["save_token"].click(
            fn=save_token_callback,
            inputs=[settings_controls["token"]],
            outputs=[
                settings_controls["token_status"],
                settings_controls["readiness"],
                midi_readiness,
                settings_controls["token"],
            ],
        )

        def clear_token_callback():
            analysis_service.save_settings(
                replace(analysis_service.settings(), hf_token="")
            )
            return (
                t("settings.token.cleared"),
                *refreshed_readiness(),
                gr.update(value=""),
            )

        settings_controls["clear_token"].click(
            fn=clear_token_callback,
            outputs=[
                settings_controls["token_status"],
                settings_controls["readiness"],
                midi_readiness,
                settings_controls["token"],
            ],
        )

        def license_callback(accepted: bool):
            analysis_service.save_settings(
                replace(
                    analysis_service.settings(),
                    weights_license_accepted=bool(accepted),
                )
            )
            return refreshed_readiness()

        settings_controls["license"].change(
            fn=license_callback,
            inputs=[settings_controls["license"]],
            outputs=[settings_controls["readiness"], midi_readiness],
        )

        def model_callback(size: str):
            analysis_service.save_settings(
                replace(analysis_service.settings(), muscriptor_model=size)
            )
            return (*refreshed_readiness(), gr.update(value=size))

        settings_controls["model"].change(
            fn=model_callback,
            inputs=[settings_controls["model"]],
            outputs=[
                settings_controls["readiness"],
                midi_readiness,
                midi_model,
            ],
        )

        def check_callback():
            return refreshed_readiness(probe=True)

        settings_controls["check"].click(
            fn=check_callback,
            outputs=[settings_controls["readiness"], midi_readiness],
            show_progress="full",
        )

        def download_callback(size: str, progress=gr.Progress()):
            """A generator: a multi-gigabyte download needs to show its work."""
            message = ""
            try:
                for event in analysis_service.download_weights(size):
                    if event.kind == "progress":
                        progress(event.fraction or 0.0, desc=event.message)
                        message = event.message
                    elif event.kind == "result":
                        payload = event.payload
                        current = analysis_service.settings()
                        analysis_service.save_settings(
                            replace(
                                current,
                                muscriptor_weights={
                                    **current.muscriptor_weights,
                                    size: payload.get("weights_path", ""),
                                },
                            )
                        )
                        message = t("settings.download.done", model=size)
                    yield message, *refreshed_readiness()
            except AdapterError as error:
                raise gr.Error(
                    _adapter_message(error, t)
                ) from error
            except (OSError, RuntimeError) as error:
                raise gr.Error(str(error)) from error

        settings_controls["download"].click(
            fn=download_callback,
            inputs=[settings_controls["model"]],
            outputs=[
                settings_controls["download_status"],
                settings_controls["readiness"],
                midi_readiness,
            ],
            show_progress="full",
        )

        def repos_callback():
            return repo_status_rows(analysis_service.repository_statuses(), t)

        settings_controls["refresh_repos"].click(
            fn=repos_callback,
            outputs=[settings_controls["repos"]],
            show_progress="full",
        )

        def pull_callback():
            outcome = analysis_service.pull_repository("muscriptor")
            return pull_message(outcome, t), repos_callback()

        settings_controls["pull"].click(
            fn=pull_callback,
            outputs=[settings_controls["repo_log"], settings_controls["repos"]],
            show_progress="full",
        )

        # ---- MIDI transcription -------------------------------------------

        def midi_callback(
            source_kind: str,
            uploaded,
            stem: str | None,
            run_id: str | None,
            size: str,
            instruments: str,
            progress=gr.Progress(),
        ):
            if not can_transcribe(analysis_service.readiness()):
                raise gr.Error(t("error.midi_not_ready"))
            # The tab lets you pick a checkpoint other than the one Settings
            # tracks, and readiness only knows about the latter. Without this,
            # choosing an undownloaded size would start a multi-gigabyte
            # download inside what looked like a transcription click.
            if not analysis_service.settings().muscriptor_weights.get(size):
                raise gr.Error(t("readiness.fix.weights"))
            if source_kind == "stem":
                audio_path = stem
            elif source_kind == "run":
                if not run_id:
                    raise gr.Error(t("error.analyze_first"))
                audio_path = str(analysis_service.history.get_run(run_id).audio_path)
            else:
                audio_path = (
                    uploaded
                    if isinstance(uploaded, str)
                    else getattr(uploaded, "name", None)
                )

            try:
                destination, stream = analysis_service.transcribe_to_midi(
                    audio_path,
                    size=size,
                    instruments=instruments,
                    t=t,
                )
                payload: dict[str, Any] = {}
                for event in stream:
                    if event.kind == "progress":
                        progress(event.fraction or 0.0, desc=event.message)
                    elif event.kind == "result":
                        payload = event.payload
            except AdapterError as error:
                raise gr.Error(_adapter_message(error, t)) from error
            except (KeyError, OSError, RuntimeError, ValueError) as error:
                raise gr.Error(str(error)) from error

            # Reading the file back is also the last sanity check: if it did not
            # parse, the run did not really succeed whatever the payload says.
            roll = empty_figure(t("midi.empty.notes"))
            preview_sound = None
            summary = ""
            if destination.is_file():
                try:
                    parsed = read_midi(destination)
                    roll = piano_roll_figure(parsed, t)
                    preview_sound = preview_audio(parsed)
                    summary = preview_summary(parsed, t)
                except (OSError, ValueError, EOFError, IndexError) as error:
                    summary = str(error)

            return (
                t(
                    "midi.status.done",
                    path=destination,
                    seconds=payload.get("runtime_seconds", "?"),
                ),
                roll,
                preview_sound,
                summary,
                str(destination) if destination.is_file() else None,
                payload,
            )

        midi_button.click(
            fn=midi_callback,
            inputs=[
                midi_source,
                midi_upload,
                selected_stem,
                current_run_id,
                midi_model,
                midi_instruments,
            ],
            outputs=[
                midi_status,
                midi_roll,
                midi_preview_audio,
                midi_preview_summary,
                midi_file,
                midi_payload,
            ],
            show_progress="full",
        )

    return app


def _adapter_message(error: AdapterError, t: Translator) -> str:
    """Translate the adapter's code; fall back to its own text if it is new."""
    try:
        return t(f"muscriptor.error.{error.code}")
    except KeyError:
        return error.detail or error.code


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
    head = (
        font_face_head()
        + playback_sync_head()
        + plot_resize_head()
        + settings_modal_head()
        + restart_head()
        + language_memory_head()
    )
    fastapi_app = FastAPI()

    # Registered first: Starlette matches routes in declaration order, and the
    # root Gradio mount added last swallows everything unmatched. Registering
    # before the /ru mount matters too, or /ru/lab-assets/... would be handed to
    # the Russian interface.
    fastapi_app.mount(
        ASSET_MOUNT,
        StaticFiles(directory=STATIC_DIR),
        name="lab-assets",
    )

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
    # No `reload=True` here, and it is not an oversight. uvicorn's reloader
    # detects the change and then hangs: Gradio's queue leaves threads running
    # that never let the worker shut down, so the old code keeps serving while
    # the log claims it reloaded. A restart that lies about having happened is
    # worse than none, so the restart button in the interface is the answer
    # instead — see music_lab_ui/restart.py.
    uvicorn.run(build_server(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
