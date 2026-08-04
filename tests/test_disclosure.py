"""Guards for the disclosure registry and renderer.

The most valuable test here is `test_every_declared_disclosure_is_rendered`.
Before the registry existed, a help topic sat in the map for months wired to
nothing while the chart it described carried a different explanation — a bug no
amount of reading the diff would have caught, because nothing was wrong with the
code, only with what was hooked to what.
"""

from __future__ import annotations

import re

import pytest

from music_lab_ui.app import build_app
from music_lab_ui.disclosure import DISCLOSURES, disclosure_html
from music_lab_ui.i18n import LOCALES, get_translator

TRUSTED = sorted(key for key, spec in DISCLOSURES.items() if spec.trusted_html)


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("disclosure_id", sorted(DISCLOSURES))
def test_every_disclosure_resolves_all_of_its_keys(
    disclosure_id: str, locale: str
) -> None:
    t = get_translator(locale)
    spec = DISCLOSURES[disclosure_id]

    assert t(f"{spec.prefix}.title")
    for section in spec.sections:
        assert t(f"{spec.prefix}.{section}")


BUILT = sorted(key for key, spec in DISCLOSURES.items() if not spec.runtime)


@pytest.mark.parametrize("disclosure_id", BUILT)
def test_every_declared_disclosure_is_rendered(disclosure_id: str) -> None:
    """A registry entry that reaches no screen is worse than no entry: it looks
    like the explanation exists."""
    config = str(build_app().get_config_file())

    assert f'data-disclosure="{disclosure_id}"' in config


def test_the_runtime_disclosures_are_emitted_by_their_presenters() -> None:
    """These appear only after a callback fills them, so the sweep above cannot
    see them — they are covered here instead of being exempted quietly."""
    from music_lab_ui.contracts import DetectorResult
    from music_lab_ui.ui_presenters import detector_cards

    rendered = detector_cards(
        (
            DetectorResult(
                detector="lofcz",
                status="ok",
                probability=0.9,
                label="AI-Generated",
                confidence=0.8,
                runtime_seconds=1.0,
            ),
        )
    )

    assert 'data-disclosure="detector/caveat"' in rendered
    # High score, so the badge warns rather than merely informs.
    assert "tone-warn" in rendered
    # And the caveat itself is no longer sitting in the open.
    caveat = get_translator()("caveat.lofcz")
    assert caveat in rendered.split('class="lab-disclosure-body"')[1]


@pytest.mark.parametrize("disclosure_id", sorted(DISCLOSURES))
def test_the_id_and_the_tone_reach_the_markup(disclosure_id: str) -> None:
    spec = DISCLOSURES[disclosure_id]
    rendered = disclosure_html(disclosure_id)

    assert f'data-disclosure="{disclosure_id}"' in rendered
    assert f"tone-{spec.tone}" in rendered
    assert f"layout-{spec.layout}" in rendered
    assert '<span class="lab-disclosure-badge">' in rendered
    # SVG, not a text glyph: neither vendored family carries `!` in a circle or
    # a warning triangle, so a character would fall back to a symbol font.
    assert "<svg" in rendered


def test_a_row_shows_its_title_before_you_open_it() -> None:
    rendered = disclosure_html("midi/basics")
    summary = rendered.split("<summary")[1].split("</summary>")[0]

    assert get_translator()("guide.midi.basics.title") in summary


def test_a_badge_keeps_its_title_inside_the_popover() -> None:
    """Beside a chart there is no room for a label; the title heads the body."""
    rendered = disclosure_html("fst/stage1")
    summary = rendered.split("<summary")[1].split("</summary>")[0]

    assert "lab-disclosure-title" not in summary
    assert get_translator()("help.fst.stage1.title") in rendered


def test_a_runtime_body_overrides_the_catalogue() -> None:
    """Detector caveats and readiness checklists have no fixed key but belong
    behind the same affordance."""
    rendered = disclosure_html("fst/stage1", body="<p>measured just now</p>")

    assert "measured just now" in rendered
    assert get_translator()("help.fst.stage1.measured") not in rendered


def test_catalogue_text_is_escaped_unless_the_spec_opts_in() -> None:
    """Only `trusted_html` specs may carry markup; the rest are plain text and
    get wrapped and escaped, so a stray `<` in a translation cannot break out."""
    spec = DISCLOSURES["fst/stage1"]
    assert spec.trusted_html is False

    rendered = disclosure_html("fst/stage1")
    measured = get_translator()("help.fst.stage1.measured")

    assert f"<p>{measured}</p>" in rendered


@pytest.mark.parametrize("disclosure_id", TRUSTED)
@pytest.mark.parametrize("locale", LOCALES)
def test_authored_bodies_carry_no_scripts_or_event_handlers(
    disclosure_id: str, locale: str
) -> None:
    """These are the only catalogue entries inserted without escaping."""
    spec = DISCLOSURES[disclosure_id]
    for section in spec.sections:
        body = get_translator(locale)(f"{spec.prefix}.{section}")

        assert "<script" not in body.lower()
        assert not re.search(r"\son\w+\s*=", body, flags=re.IGNORECASE)
        assert "javascript:" not in body.lower()


@pytest.mark.parametrize("disclosure_id", TRUSTED)
@pytest.mark.parametrize("locale", LOCALES)
def test_authored_links_open_safely(disclosure_id: str, locale: str) -> None:
    spec = DISCLOSURES[disclosure_id]
    for section in spec.sections:
        body = get_translator(locale)(f"{spec.prefix}.{section}")
        for link in re.findall(r"<a\s[^>]*>", body):
            assert 'target="_blank"' in link
            # Without noopener the opened page gets a handle on this one.
            assert 'rel="noopener"' in link
            assert 'href="https://' in link


def test_the_telemetry_badges_explain_the_chart_they_sit_above() -> None:
    """These two were one apart: the fakeprint explanation headed the spectrum
    chart, and the fakeprint chart had no badge at all."""
    from music_lab_ui.app import build_app

    config = str(build_app().get_config_file())
    hull = config.index('data-disclosure="lofcz/lower_hull"')
    spectrum = config.index("telemetry.lofcz.spectrum") if (
        "telemetry.lofcz.spectrum" in config
    ) else config.index("spectrum and lower hull")
    fakeprint = config.index('data-disclosure="lofcz/fakeprint"')

    assert hull < spectrum < fakeprint
