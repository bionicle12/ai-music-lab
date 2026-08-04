from pathlib import Path

import gradio as gr
from gradio import utils

from music_lab_ui.app import (
    THEME,
    _comparison_reset_payload,
    build_app,
    playback_sync_head,
    plot_resize_head,
    settings_modal_head,
)
from music_lab_ui.i18n import get_translator

t = get_translator()


def test_build_app_exposes_single_file_workflow() -> None:
    app = build_app()
    config = app.get_config_file()
    labels = {
        component["props"].get("label")
        for component in config["components"]
        if "props" in component
    }

    assert isinstance(app, gr.Blocks)
    assert t("app.audio.label") in labels
    assert t("app.detectors.label") in labels
    assert t("telemetry.version_a") in labels
    assert t("telemetry.version_b") in labels
    assert t("plot.spectrogram_3d") in labels
    assert "lofcz · native fakeprint" in labels
    assert "FST · self-similarity matrix" in labels
    assert "lofcz · native fakeprint A/B" in labels
    assert "FST · Stage-1 A/B" in labels
    assert "FST · fusion gate A/B" in labels
    assert "FST · self-similarity Δ B−A" in labels
    assert t("app.fst_npz") in labels
    assert "Baseline для A/B" not in labels

    button_values = {
        component["props"].get("value")
        for component in config["components"]
        if component.get("type") == "button"
    }
    assert t("app.compare.button") in button_values
    assert t("app.compare.pin") in button_values
    assert t("app.compare.unpin") in button_values
    assert t("app.high_detail") in button_values
    assert "Назначить baseline" not in button_values

    component_markers = [
        component["props"].get("label") or component["props"].get("value")
        for component in config["components"]
        if "props" in component
    ]
    assert component_markers.index(
        t("plot.spectrogram_3d")
    ) < component_markers.index(t("app.high_detail"))
    assert component_markers.index(
        t("app.high_detail")
    ) < component_markers.index(t("plot.average_spectrum"))


def test_workspace_splits_analysis_from_editing() -> None:
    """Analysis is the first group, so it is the one open on load."""
    config = build_app().get_config_file()
    tabs = [
        component["props"].get("label")
        for component in config["components"]
        if component.get("type") == "tabitem"
    ]

    assert tabs[0] == t("tab.group.analysis")
    assert t("tab.group.editing") in tabs
    # The analysis tabs kept their identity instead of being flattened away.
    assert t("tab.spectrum") in tabs
    assert t("tab.timeline") in tabs
    assert t("tab.technical") in tabs
    # Editing is a placeholder for now; both planned tabs are declared.
    assert t("tab.edit.sunofix") in tabs
    assert t("tab.edit.midi") in tabs
    assert tabs.index(t("tab.technical")) < tabs.index(t("tab.group.editing"))


def test_sunofix_still_says_it_is_not_implemented() -> None:
    """A placeholder that reads like a feature is worse than no placeholder."""
    assert "nothing here runs yet" in get_translator("en")("lead.sunofix").lower()
    assert "ничего не работает" in get_translator("ru")("lead.sunofix").lower()


def test_the_weights_licence_is_stated_once_in_full() -> None:
    """Non-commercial weights are a boundary a releasing musician can cross, so
    it is said properly once rather than half-said in five places."""
    for locale in ("en", "ru"):
        t_ = get_translator(locale)
        full = t_("disc.licence.weights.body")

        assert "CC BY-NC 4.0" in full
        # The pointer on the tab is the row's own title — short enough to scan.
        assert len(t_("disc.licence.weights.title").split()) <= 7
        # And the tab's own lead does not restate it.
        assert "CC BY-NC" not in t_("lead.midi")


def test_the_editing_group_carries_no_text_of_its_own() -> None:
    """Anything placed there sits outside both sub-tab panels, so it renders on
    both at once — which is how the same 76 words appeared twice."""
    from music_lab_ui.i18n import CATALOGUE

    assert "doc.editing" not in CATALOGUE["en"]
    assert "doc.editing" not in CATALOGUE["ru"]


def test_layers_hands_a_stem_to_the_midi_tab() -> None:
    """The whole point of the sweep is choosing what to transcribe next."""
    config = build_app().get_config_file()
    buttons = {
        component["props"].get("value")
        for component in config["components"]
        if component.get("type") == "button"
    }

    assert t("layers.send_to_midi") in buttons
    assert t("midi.run") in buttons
    assert t("settings.download") in buttons


def test_tabs_carry_the_ids_the_handoff_switches_between() -> None:
    config = build_app().get_config_file()
    ids = {
        component["props"].get("id")
        for component in config["components"]
        if component.get("type") == "tabitem"
    }

    # Both nesting levels, or a "send to MIDI" click could only move one of them.
    assert {"analysis", "editing", "sunofix", "midi"} <= ids


def test_building_the_interface_never_spawns_a_subprocess(monkeypatch) -> None:
    """The readiness probe costs a process, so it must be opt-in only."""
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError("build_app must not shell out")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    assert build_app() is not None


def test_a_corrupt_settings_file_does_not_stop_the_interface(
    tmp_path, monkeypatch
) -> None:
    """The one file a user can hand-edit must never lock them out of the app."""
    from music_lab_ui.config import LabPaths
    from music_lab_ui.history import HistoryStore
    from music_lab_ui.ui_service import AnalysisService

    root = tmp_path / "ai-music-lab"
    root.mkdir()
    paths = LabPaths.from_root(root)
    paths.settings_path.parent.mkdir(parents=True, exist_ok=True)
    paths.settings_path.write_text("{oops", encoding="utf-8")
    service = AnalysisService(
        paths=paths,
        history=HistoryStore(paths.history_db, paths.runs_dir),
    )

    assert build_app(service) is not None


def test_the_stored_token_never_reaches_the_interface(tmp_path) -> None:
    """A leak guard: the panel shows a fingerprint, never the credential."""
    from dataclasses import replace

    from music_lab_ui.config import LabPaths
    from music_lab_ui.history import HistoryStore
    from music_lab_ui.ui_service import AnalysisService

    secret = "hf_xxxxTESTTOKENxxxx"
    root = tmp_path / "ai-music-lab"
    root.mkdir()
    paths = LabPaths.from_root(root)
    service = AnalysisService(
        paths=paths,
        history=HistoryStore(paths.history_db, paths.runs_dir),
    )
    service.save_settings(replace(service.settings(), hf_token=secret))

    rendered = str(build_app(service).get_config_file())

    assert secret not in rendered
    # It is on disk, in the one file that is meant to hold it, and nowhere else.
    assert secret in paths.settings_path.read_text(encoding="utf-8")
    assert not list(paths.runs_dir.rglob("*.json"))


def test_charts_are_relaid_out_when_a_hidden_tab_is_revealed() -> None:
    """Without this the chart keeps the width it was first drawn at."""
    script = plot_resize_head()

    assert "Plotly.Plots.resize" in script
    assert "ResizeObserver" in script


def test_the_transcription_can_be_seen_and_heard() -> None:
    """A MIDI file is unverifiable by eye; the roll and the preview fix that."""
    config = build_app().get_config_file()
    labels = {
        component["props"].get("label")
        for component in config["components"]
        if "props" in component
    }

    assert t("midi.plot.label") in labels
    assert t("midi.preview.label") in labels


def test_the_settings_dialog_is_centred_without_a_transform() -> None:
    """A transformed element becomes the containing block for its own
    fixed-position descendants, so the backdrop resolved `inset: 0` against the
    dialog and dimmed nothing but itself."""
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")
    block = css.split(".settings-modal {")[1].split("}")[0]
    declarations = [
        line.split(":")[0].strip()
        for line in block.splitlines()
        if ":" in line and not line.strip().startswith(("/*", "*"))
    ]

    assert "transform" not in declarations
    assert "margin: auto" in block


def test_nothing_in_the_settings_dialog_is_allowed_to_shrink() -> None:
    """Gradio renders it as a flex column, and the default `flex-shrink: 1`
    collapsed the token field's wrapper to two pixels while the input itself
    overflowed out below the Save button."""
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")

    assert ".settings-modal > * {" in css
    assert "flex: 0 0 auto" in css


def test_the_setup_dialog_opens_from_the_tab_that_needs_it() -> None:
    """It only configures muscriptor, so it belongs to the MIDI tab rather than
    to the app title, where it read as a global preferences screen."""
    config = build_app().get_config_file()
    buttons = [
        component["props"].get("value")
        for component in config["components"]
        if component.get("type") == "button"
    ]

    assert t("settings.open") in buttons
    assert "⚙" not in buttons  # the bare gear beside the title is gone


def test_the_settings_dialog_closes_without_a_python_round_trip_of_its_own() -> None:
    """Escape and backdrop clicks go through the same button a user would press,
    so Gradio's idea of the dialog state cannot drift from the DOM's."""
    script = settings_modal_head()

    assert "Escape" in script
    assert "settings-close" in script
    # offsetParent is always null on a fixed-position element, which this is.
    assert "getClientRects" in script


def test_the_playhead_follows_whichever_player_is_actually_playing() -> None:
    """Two players exist now — the analysed track and the MIDI preview."""
    script = playback_sync_head()

    assert "allAudio" in script
    assert "paused" in script


def test_theme_can_be_compared_with_builtin_themes() -> None:
    for builtin in utils.BUILT_IN_THEMES.values():
        assert isinstance(THEME.to_dict() == builtin.to_dict(), bool)


def test_every_gradio_dependency_references_registered_components() -> None:
    config = build_app().get_config_file()
    component_ids = {component["id"] for component in config["components"]}

    for dependency in config["dependencies"]:
        assert set(dependency["inputs"]).issubset(component_ids)
        assert set(dependency["outputs"]).issubset(component_ids)


def test_new_analysis_resets_stale_comparison_views() -> None:
    status, detector_rows, spectrum, difference, metric_rows = (
        _comparison_reset_payload(t)
    )

    assert status == t("compare.reset")
    assert detector_rows == []
    assert spectrum.layout.annotations[0].text == t("empty.pick_two")
    assert difference.layout.annotations[0].text == t("empty.pick_two")
    assert metric_rows == []


def test_detector_cards_stack_before_their_content_can_clip() -> None:
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")

    assert ".detector-card:only-child" in css
    assert "@media (max-width: 1380px)" in css


def test_dataframe_columns_are_sized_by_the_token_not_the_table() -> None:
    """The regression guard for the clipped-column bug.

    Gradio 6.20 measures a dataframe's column widths from a hidden
    `<tbody class="sizing-body">` inside the header <table>, then pins those
    widths in pixels — but the visible rows are separate `.virtual-row` divs.
    A `table { font-size }` rule therefore changes the measurement and not the
    rendering, and every column comes out too narrow to hold its text. Setting
    `--input-text-size` on the wrapper reaches both sides. Do not "simplify"
    this back to a font-size on the table.
    """
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")

    assert ".metadata-rail table {" not in css
    assert ".history-table table {" not in css
    assert css.count("--input-text-size") >= 2


def test_selectors_that_match_nothing_in_this_gradio_are_gone() -> None:
    """Dead CSS is worse than none: it reads as working styling that isn't."""
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")

    # `.tab-nav` is the Gradio 4/5 name; 6.20 renders `.tab-container`.
    assert ".tab-nav" not in css
    # Dataframe selection is `.cell-selected` on a div outside any <table>.
    assert '[aria-selected="true"]' not in css


def test_charts_use_the_same_fonts_as_the_interface() -> None:
    """Charts asked for Inter, which is loaded nowhere — so they silently fell
    back to a system font while the chrome rendered in the theme font."""
    from music_lab_ui.plots import FONT_MONO, FONT_UI, spectrogram_figure
    from tests.test_comparison import feature_fixture

    figure = spectrogram_figure(feature_fixture())

    assert figure.layout.font.family == FONT_UI
    assert "Inter" not in figure.layout.font.family
    # Tick labels are measurements, so they get the tabular monospace.
    assert figure.layout.xaxis.tickfont.family == FONT_MONO


def test_inline_code_uses_readable_dark_theme_colors() -> None:
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")

    assert ".prose code" in css
    assert "pre code" in css
    # The literal used to be spelled out five times; it is a token now.
    assert "var(--lab-cyan-ink)" in css


def test_the_palette_is_owned_by_the_theme_not_the_stylesheet() -> None:
    """Gradio appends theme.css after custom CSS, so a `:root` block here would
    lose every tie — which is what the pile of !important used to paper over."""
    from music_lab_ui.app import LAB_PALETTE, THEME

    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")
    theme_css = THEME._get_theme_css()

    assert ":root {" not in css
    for name in LAB_PALETTE:
        assert f"--{name.replace('_', '-')}:" in theme_css, name


def test_every_lab_variable_used_in_css_is_actually_defined() -> None:
    """A typo in a var() name renders as nothing at all, silently."""
    import re

    from music_lab_ui.app import LAB_PALETTE

    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")
    declared = {name.replace("_", "-") for name in LAB_PALETTE}
    used = set(re.findall(r"var\(--(lab-[a-z0-9-]+)\)", css))

    assert used - declared == set()


def test_important_is_kept_to_what_nothing_else_can_win() -> None:
    """A ratchet. It was 46; each survivor needs a reason.

    Two are on `.gradio-container`, which sits outside the `.contain` wrapper
    Gradio prefixes our rules with, so it gets no specificity boost. The third
    fights an inline style Gradio writes on the column itself.
    """
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")

    assert css.count("!important") <= 3


def test_keyboard_focus_is_visible() -> None:
    """Gradio provides no focus token for buttons, and most of the prose in this
    interface now lives behind a <summary>."""
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")

    assert ":focus-visible" in css
    assert "outline: 2px solid var(--lab-cyan)" in css


def test_table_hover_and_loaded_audio_spacing() -> None:
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")

    assert ".gradio-container table ::selection" in css
    assert ".gradio-container .cell-selected" in css
    assert ".gradio-container .virtual-row:hover" in css
    assert ".gradio-container .virtual-row:hover *" in css
    assert (
        ".audio-drop .audio-container .component-wrapper .waveform-container"
        in css
    )
    assert "margin-bottom: 20px" in css
    assert "min-height: 320px" not in css


def test_a_dropped_file_is_drawn_before_it_is_analysed() -> None:
    """The player fills itself on upload; without this the whole-track strip
    beside it stayed empty until a run finished, which reads as broken."""
    config = build_app().get_config_file()
    audio_id = strip_id = None
    for component in config["components"]:
        props = component.get("props", {})
        if props.get("label") == t("app.audio.label"):
            audio_id = component["id"]
        if "track-overview" in (props.get("elem_classes") or []):
            strip_id = component["id"]

    assert audio_id is not None and strip_id is not None

    on_upload = [
        dependency
        for dependency in config["dependencies"]
        if [audio_id, "change"] in [list(target) for target in dependency["targets"]]
    ]

    assert on_upload, "nothing happens when a file is dropped"
    assert any(strip_id in dependency["outputs"] for dependency in on_upload)


def test_opening_a_detector_dialog_rereads_its_stored_parameters() -> None:
    """The controls keep whatever was last clicked. Without re-reading, picking
    a value and closing without saving leaves the dialog showing a setting that
    was never stored — visible only as one wrong run later."""
    config = build_app().get_config_file()
    gears = [
        component["id"]
        for component in config["components"]
        if "detector-gear" in (component.get("props", {}).get("elem_classes") or [])
    ]
    radios = {
        component["id"]
        for component in config["components"]
        if component.get("props", {}).get("label") == t("detector.fst.batch.label")
    }

    assert len(gears) == 2 and radios

    on_open = [
        dependency
        for dependency in config["dependencies"]
        for gear in gears
        if [gear, "click"] in [list(target) for target in dependency["targets"]]
    ]

    assert any(radios & set(dependency["outputs"]) for dependency in on_open)
