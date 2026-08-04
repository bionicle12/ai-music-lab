import numpy as np
import pytest

from music_lab_ui.telemetry import DetectorTelemetry
from music_lab_ui.telemetry_plots import timeline_figure
from music_lab_ui.ui_presenters import timeline_summary
from music_lab_ui.i18n import get_translator

t = get_translator()


def timeline_fixture() -> DetectorTelemetry:
    return DetectorTelemetry(
        detector="lofcz-timeline",
        scalars={"window_seconds": 15.0, "hop_seconds": 5.0},
        arrays={
            "window_start_seconds": np.array([0.0, 5.0, 10.0], dtype=np.float32),
            "window_end_seconds": np.array([15.0, 20.0, 25.0], dtype=np.float32),
            "window_center_seconds": np.array([7.5, 12.5, 17.5], dtype=np.float32),
            "probability": np.array([0.02, 0.97, 0.4], dtype=np.float32),
            "mean_residue_db": np.array([1.1, 1.5, 1.2], dtype=np.float32),
        },
        warnings=("relative map",),
    )


def fst_fixture() -> DetectorTelemetry:
    return DetectorTelemetry(
        detector="FST",
        scalars={},
        arrays={
            "segment_start_seconds": np.array([0.0, 10.0], dtype=np.float32),
            "fusion_content_gate": np.array([0.3, 0.8], dtype=np.float32),
        },
    )


def fst_with_stage1_fixture() -> DetectorTelemetry:
    return DetectorTelemetry(
        detector="FST",
        scalars={},
        arrays={
            "segment_start_seconds": np.array([0.0, 10.0], dtype=np.float32),
            "fusion_content_gate": np.array([0.62, 0.60], dtype=np.float32),
            "stage1_class_probabilities": np.array(
                [[0.999, 0.001], [0.002, 0.998]],
                dtype=np.float32,
            ),
        },
    )


def test_timeline_figure_opts_into_playback_sync_and_scales_to_percent() -> None:
    figure = timeline_figure(timeline_fixture())

    assert figure.layout.meta["time_axis"] is True
    assert list(figure.data[0].y) == pytest.approx([2.0, 97.0, 40.0])
    assert tuple(figure.layout.yaxis.range) == (0, 100)


def test_timeline_figure_adds_fst_gate_on_its_own_axis() -> None:
    figure = timeline_figure(timeline_fixture(), fst_fixture())

    assert len(figure.data) == 2
    gate = figure.data[1]
    assert gate.yaxis == "y2"
    # The gate is a raw model signal and must not be relabelled as an AI score.
    assert "fusion gate" in gate.name


def test_fst_axis_keeps_its_own_scale() -> None:
    """`update_yaxes` without a selector used to rewrite y2 as well.

    That squashed FST's 0–1 signals onto a 0–100 scale, where they flatlined
    along the bottom and the chart read as "FST found nothing".
    """
    figure = timeline_figure(timeline_fixture(), fst_fixture())

    assert tuple(figure.layout.yaxis.range) == (0, 100)
    assert tuple(figure.layout.yaxis2.range) == (0, 1)
    assert figure.layout.yaxis.title.text != figure.layout.yaxis2.title.text


def test_timeline_figure_carries_fst_stage1_classes() -> None:
    """The per-segment signal that actually moves, not just the fusion gate."""
    figure = timeline_figure(timeline_fixture(), fst_with_stage1_fixture())

    on_second_axis = [trace for trace in figure.data if trace.yaxis == "y2"]
    assert len(on_second_axis) == 3
    classes = [trace for trace in on_second_axis if "Stage-1" in trace.name]
    assert len(classes) == 2
    assert list(classes[0].y) == pytest.approx([0.999, 0.002], abs=1e-6)
    # Upstream publishes no Real/Fake mapping, so neither class may be renamed.
    assert not any("AI" in trace.name for trace in classes)


def test_timeline_figure_skips_fst_when_segment_counts_disagree() -> None:
    broken = DetectorTelemetry(
        detector="FST",
        scalars={},
        arrays={
            "segment_start_seconds": np.array([0.0, 10.0], dtype=np.float32),
            "fusion_content_gate": np.array([0.3], dtype=np.float32),
        },
    )

    assert len(timeline_figure(timeline_fixture(), broken).data) == 1


def test_timeline_summary_reports_spread_and_hottest_windows() -> None:
    text = timeline_summary(timeline_fixture())

    assert text == t(
        "timeline.summary",
        count=3,
        window=15.0,
        hop=5.0,
        above=1,
        minimum="2.0",
        maximum="97.0",
        hottest=", ".join(
            [
                t("timeline.window", start="5", end="20", probability="97"),
                t("timeline.window", start="10", end="25", probability="40"),
                t("timeline.window", start="0", end="15", probability="2"),
            ]
        ),
    )
