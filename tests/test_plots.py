import numpy as np
import pytest

from music_lab_ui.plots import (
    _smooth_3d_levels,
    difference_figure,
    spectrogram_3d_figure,
    spectrogram_figure,
    spectrum_figure,
    waveform_figure,
)
from tests.test_comparison import feature_fixture
from music_lab_ui.comparison import compare_features
from music_lab_ui.i18n import get_translator

t = get_translator()


def test_spectrogram_hover_contains_time_frequency_level_and_hint() -> None:
    figure = spectrogram_figure(feature_fixture())

    template = figure.data[0].hovertemplate
    assert t("plot.hover.time") in template
    assert t("plot.hover.frequency") in template
    assert t("plot.hover.level") in template
    assert t("plot.hover.zone") in template
    assert figure.layout.yaxis.type == "log"


def test_spectrum_uses_direct_current_and_baseline_labels() -> None:
    figure = spectrum_figure(feature_fixture(-40.0), feature_fixture(-46.0))

    assert [trace.name for trace in figure.data] == [
        t("plot.current"),
        t("plot.baseline"),
    ]


def test_spectrum_accepts_explicit_version_labels() -> None:
    figure = spectrum_figure(
        feature_fixture(-40.0),
        feature_fixture(-46.0),
        current_label=t("telemetry.version_b"),
        baseline_label=t("telemetry.version_a"),
    )

    assert [trace.name for trace in figure.data] == [
        t("telemetry.version_b"),
        t("telemetry.version_a"),
    ]


def test_difference_figure_uses_symmetric_color_limits() -> None:
    comparison = compare_features(feature_fixture(-40.0), feature_fixture(-46.0))

    figure = difference_figure(comparison)

    assert figure.data[0].zmin == -figure.data[0].zmax


def test_3d_spectrogram_supports_preview_and_high_detail() -> None:
    features = feature_fixture(frequency_bins=768, time_bins=1536)

    preview = spectrogram_3d_figure(features, detail="preview")
    high = spectrogram_3d_figure(features, detail="high")

    assert preview.data[0].type == "surface"
    assert np.asarray(preview.data[0].z).shape == (96, 160)
    assert np.asarray(high.data[0].z).shape == (256, 480)
    assert preview.data[0].connectgaps is True
    assert high.data[0].connectgaps is True
    assert preview.layout.scene.camera.eye.x == 1.55


def test_3d_spectrogram_rejects_unknown_detail() -> None:
    with pytest.raises(ValueError, match="unknown 3D detail preset"):
        spectrogram_3d_figure(feature_fixture(), detail="ultra")


def test_3d_smoothing_reduces_temporal_spikes_without_mutating_input() -> None:
    source = np.full((96, 160), -80.0, dtype=np.float32)
    source[::8, ::10] = -5.0
    before = source.copy()

    smoothed = _smooth_3d_levels(source)

    assert smoothed.shape == source.shape
    assert np.array_equal(source, before)
    assert np.isfinite(smoothed).all()
    assert smoothed.min() >= -100
    assert smoothed.max() <= 0
    assert np.abs(np.diff(smoothed, axis=1)).sum() < np.abs(
        np.diff(source, axis=1)
    ).sum()


def test_only_time_domain_figures_opt_into_playback_sync() -> None:
    features = feature_fixture()
    comparison = compare_features(features, features)

    time_domain = [
        spectrogram_figure(features),
        waveform_figure(features),
        difference_figure(comparison),
    ]
    frequency_domain = [spectrum_figure(features)]

    for figure in time_domain:
        assert figure.layout.meta["time_axis"] is True
    for figure in frequency_domain:
        # A playhead on a frequency axis would point at a meaningless position.
        assert figure.layout.meta["time_axis"] is False


def test_an_untitled_chart_keeps_the_top_margin_it_asked_for() -> None:
    """Gradio 6.20 forces `margin.t` to at least 100 on a labelled plot that
    carries a title, and a title of "" still counts as one. The whole-track
    strip is 118px tall, so that left two pixels to draw the track in — which
    looks exactly like a chart that never got any data."""
    figure = waveform_figure(feature_fixture())

    assert figure.layout.title.text is None
    assert figure.layout.margin.t == 20
