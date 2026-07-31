import numpy as np

from music_lab_ui.interpretation import interpret_run
from music_lab_ui.telemetry import DetectorTelemetry
from music_lab_ui.i18n import get_translator

t = get_translator()


def test_interpretation_is_labelled_and_references_native_fields() -> None:
    telemetry = {
        "lofcz": DetectorTelemetry(
            detector="lofcz",
            scalars={"strongest_peaks": [{"frequency_hz": 4000, "fakeprint": 1.0}]},
            arrays={"fakeprint": np.array([0.1, 1.0], dtype=np.float32)},
        ),
        "FST": DetectorTelemetry(
            detector="FST",
            scalars={"valid_segment_count": 2},
            arrays={
                "stage1_class_probabilities": np.array(
                    [[0.8, 0.2], [0.1, 0.9]], dtype=np.float32
                ),
                "fusion_content_gate": np.array([0.2, 0.8], dtype=np.float32),
            },
        ),
    }

    rendered = interpret_run(telemetry)

    assert t("interpret.experimental_label") in rendered
    assert "fakeprint" in rendered
    assert "Stage-1" in rendered
    assert "fusion gate" in rendered
    assert "advice" not in rendered.lower()
