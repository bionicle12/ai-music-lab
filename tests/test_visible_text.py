"""How much text the interface puts in front of you before you click anything.

Every number here was a measurement first. The tab budgets are not aspirations —
they are slightly above what the interface currently does, so a future change
that quietly reintroduces an essay fails rather than merely feeling worse.
"""

from __future__ import annotations

import re

import pytest

from music_lab_ui.app import build_app
from music_lab_ui.i18n import LOCALES

#: Everything inside a disclosure body counts as hidden. This is the whole
#: machine-checkable definition of "behind a click".
#: Matched per string rather than over the joined text, so a body can never
#: swallow the visible text of the component that follows it.
_BODY = re.compile(r'<div class="lab-disclosure-body">.*', re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")

#: Props that a user actually reads on screen.
_TEXT_PROPS = ("value", "label", "info", "headers", "placeholder")


def _readable(value: str) -> str:
    """One component's text, minus anything a disclosure hides."""
    return _TAGS.sub(" ", _BODY.sub(" ", value))


def _strings(props: dict) -> list[str]:
    out = []
    for name in _TEXT_PROPS:
        value = props.get(name)
        if isinstance(value, str):
            out.append(_readable(value))
        elif isinstance(value, (list, tuple)):
            out.extend(
                _readable(item) for item in value if isinstance(item, str)
            )
    return out


def visible_text(blocks) -> str:
    """Text a user can read without opening anything."""
    config = blocks.get_config_file()
    chunks = []
    for component in config["components"]:
        props = component.get("props") or {}
        if props.get("visible") is False:
            continue
        chunks.extend(_strings(props))
    return "\n".join(chunks)


def _words(text: str) -> int:
    return len(text.split())


@pytest.mark.parametrize("locale", LOCALES)
def test_the_weights_licence_is_not_restated(locale: str) -> None:
    """It used to be stated five times across the interface."""
    text = visible_text(build_app(locale=locale))

    assert text.count("CC BY-NC") <= 1


@pytest.mark.parametrize("locale", LOCALES)
def test_the_stems_not_mixes_point_is_made_once(locale: str) -> None:
    """Three separate paragraphs used to say it. What survives is one row title
    on the tab where the mistake is actually made; the argument is in its body."""
    text = visible_text(build_app(locale=locale)).lower()
    marker = "stems, not mixes" if locale == "en" else "стемы, а не миксы"

    assert text.count(marker) == 1


@pytest.mark.parametrize("locale", LOCALES)
def test_most_of_the_prose_is_behind_a_click(locale: str) -> None:
    """The catalogue barely shrank — the text moved. This is the ratio that
    matters, and the one that silently degrades if nobody watches it.

    Measured after the text pass: 25% visible in English, 27% in Russian.
    """
    from music_lab_ui.i18n import CATALOGUE

    total = sum(_words(value) for value in CATALOGUE[locale].values())
    on_screen = _words(visible_text(build_app(locale=locale)))

    assert on_screen < total * 0.35, (on_screen, total)


@pytest.mark.parametrize("locale", LOCALES)
def test_the_interface_opens_with_controls_not_an_essay(locale: str) -> None:
    """A ratchet on the absolute count across every tab, label and header.

    Measured at 910 words (English) after the text pass, and at 1132 once
    SunoFix added a tab with twelve controls of its own. The ratio test above
    is what caught whether that growth was prose or controls: it stayed at 25%,
    so the new explanations went behind a click like everything else. The limit
    leaves room to add a feature, not to add an essay.
    """
    assert _words(visible_text(build_app(locale=locale))) < 1200


def test_the_disclosure_body_marker_is_what_the_measurement_relies_on() -> None:
    """If the markup changes, the numbers above become meaningless rather than
    wrong — so assert the thing they key off actually exists."""
    from music_lab_ui.disclosure import disclosure_html

    assert '<div class="lab-disclosure-body">' in disclosure_html("midi/basics")
