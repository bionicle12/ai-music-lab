from music_lab_ui.detector_help import help_html
from music_lab_ui.i18n import get_translator

t = get_translator()


def test_every_native_topic_explains_measurement_reading_and_limits() -> None:
    for detector, topic in (
        ("lofcz", "fakeprint"),
        ("lofcz", "lower_hull"),
        ("FST", "stage1"),
        ("FST", "self_similarity"),
        ("FST", "fusion_gate"),
    ):
        rendered = help_html(detector, topic)
        assert t("help.measured") in rendered
        assert t("help.reading") in rendered
        assert t("help.limits") in rendered
        assert 'class="telemetry-help"' in rendered
