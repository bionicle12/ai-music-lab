from pathlib import Path

import gradio as gr
from gradio import utils

from music_lab_ui.app import THEME, _comparison_reset_payload, build_app
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
    ) < component_markers.index(t("app.plot.rms_envelope"))


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


def test_inline_code_uses_readable_dark_theme_colors() -> None:
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")

    assert ".prose code" in css
    assert "pre code" in css
    assert "#7ee7ff" in css


def test_table_hover_and_loaded_audio_spacing() -> None:
    css = (
        Path(__file__).parents[1] / "music_lab_ui" / "styles.css"
    ).read_text(encoding="utf-8")

    assert ".gradio-container table ::selection" in css
    assert ".gradio-container .virtual-row:hover" in css
    assert ".gradio-container .virtual-row:hover *" in css
    assert (
        ".audio-drop .audio-container .component-wrapper .waveform-container"
        in css
    )
    assert "margin-bottom: 20px !important" in css
    assert "min-height: 320px" not in css
