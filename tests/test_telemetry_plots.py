import numpy as np

from music_lab_ui.telemetry import DetectorTelemetry
from music_lab_ui.i18n import get_translator
from music_lab_ui.telemetry_plots import (
    fst_gate_comparison_figure,
    fst_gate_figure,
    fst_segment_comparison_figure,
    fst_segment_figure,
    fst_similarity_difference_figure,
    fst_similarity_figure,
    lofcz_fakeprint_comparison_figure,
    lofcz_fakeprint_figure,
    lofcz_spectrum_figure,
)

t = get_translator()


def lofcz_fixture() -> DetectorTelemetry:
    return DetectorTelemetry(
        detector="lofcz",
        scalars={},
        arrays={
            "frequency_hz": np.array([1000, 2000, 3000], dtype=np.float32),
            "mean_spectrum_db": np.array([-30, -20, -25], dtype=np.float32),
            "lower_hull_db": np.array([-35, -35, -35], dtype=np.float32),
            "residue_db": np.array([5, 15, 10], dtype=np.float32),
            "fakeprint": np.array([0.2, 1.0, 0.6], dtype=np.float32),
        },
    )


def fst_fixture() -> DetectorTelemetry:
    return DetectorTelemetry(
        detector="FST",
        scalars={},
        arrays={
            "segment_start_seconds": np.array([0, 10], dtype=np.float32),
            "stage1_class_probabilities": np.array(
                [[0.8, 0.2], [0.1, 0.9]], dtype=np.float32
            ),
            "self_similarity": np.array([[1, 0.4], [0.4, 1]], dtype=np.float32),
            "fusion_content_gate": np.array([0.25, 0.75], dtype=np.float32),
        },
    )


def test_lofcz_plots_preserve_native_trace_names() -> None:
    spectrum = lofcz_spectrum_figure(lofcz_fixture())
    fakeprint = lofcz_fakeprint_figure(lofcz_fixture())

    assert [trace.name for trace in spectrum.data] == [
        "Mean spectrum",
        "Lower hull",
    ]
    assert [trace.name for trace in fakeprint.data] == ["Native fakeprint"]
    assert "AI detected" not in str(fakeprint.to_dict())


def test_fst_plots_keep_stage1_gate_and_similarity_separate() -> None:
    segments = fst_segment_figure(fst_fixture())
    similarity = fst_similarity_figure(fst_fixture())
    gate = fst_gate_figure(fst_fixture())

    assert [trace.name for trace in segments.data] == ["Stage-1 class 0", "Stage-1 class 1"]
    assert similarity.data[0].type == "heatmap"
    assert gate.data[0].name == "Content gate"
    assert "probability" not in gate.layout.title.text.lower()


def test_native_comparison_plots_label_a_b_without_ai_claims() -> None:
    lofcz = lofcz_fakeprint_comparison_figure(lofcz_fixture(), lofcz_fixture())
    segments = fst_segment_comparison_figure(fst_fixture(), fst_fixture())
    gate = fst_gate_comparison_figure(fst_fixture(), fst_fixture())
    similarity = fst_similarity_difference_figure(fst_fixture(), fst_fixture())

    assert [trace.name for trace in lofcz.data] == [
        t("telemetry.version_a"),
        t("telemetry.version_b"),
    ]
    assert [trace.name for trace in segments.data] == [
        "A · class 0",
        "B · class 0",
        "A · class 1",
        "B · class 1",
    ]
    assert [trace.name for trace in gate.data] == [
        t("telemetry.version_a"),
        t("telemetry.version_b"),
    ]
    assert similarity.data[0].type == "heatmap"
    assert "AI detected" not in str(
        [lofcz.to_dict(), segments.to_dict(), gate.to_dict(), similarity.to_dict()]
    )


def test_similarity_difference_rejects_unaligned_segment_grids() -> None:
    baseline = fst_fixture()
    changed = fst_fixture()
    changed.arrays["segment_start_seconds"] = np.array([1, 11], dtype=np.float32)

    figure = fst_similarity_difference_figure(baseline, changed)

    assert not figure.data
    assert figure.layout.annotations[0].text == t("telemetry.similarity.mismatch")
