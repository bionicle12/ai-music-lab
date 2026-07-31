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
