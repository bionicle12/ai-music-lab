"""Guards for the translation catalogue itself.

A half-translated interface is worse than a single-language one, so parity
between locales is asserted rather than trusted.
"""
from __future__ import annotations

import re
import string

import pytest

from music_lab_ui.app import build_app, language_memory_head
from music_lab_ui.i18n import (
    CATALOGUE,
    DEFAULT_LOCALE,
    LOCALE_NAMES,
    LOCALE_PATHS,
    LOCALES,
    Translator,
    get_translator,
)

CYRILLIC = re.compile(r"[А-яЁё]")


def test_english_is_the_default_locale() -> None:
    assert DEFAULT_LOCALE == "en"
    assert LOCALES[0] == "en"
    assert LOCALE_PATHS[DEFAULT_LOCALE] == "/"


def test_every_locale_is_declared_completely() -> None:
    for code in LOCALES:
        assert code in CATALOGUE
        assert code in LOCALE_PATHS
        assert code in LOCALE_NAMES


def test_locales_translate_exactly_the_same_keys() -> None:
    reference = set(CATALOGUE[DEFAULT_LOCALE])
    for code in LOCALES:
        missing = reference - set(CATALOGUE[code])
        extra = set(CATALOGUE[code]) - reference
        assert not missing, f"{code} is missing: {sorted(missing)}"
        assert not extra, f"{code} has keys no other locale has: {sorted(extra)}"


def test_no_translation_is_empty() -> None:
    for code, strings in CATALOGUE.items():
        blank = [key for key, value in strings.items() if not value.strip()]
        assert not blank, f"{code} has blank values: {blank}"


def test_placeholders_match_across_locales() -> None:
    """A key that formats {run_id} in one locale must format it in all of them."""

    def placeholders(template: str) -> set[str]:
        return {
            name
            for _, name, _, _ in string.Formatter().parse(template)
            if name
        }

    for key, reference in CATALOGUE[DEFAULT_LOCALE].items():
        expected = placeholders(reference)
        for code in LOCALES:
            assert placeholders(CATALOGUE[code][key]) == expected, (
                f"{code}:{key} does not use the same placeholders as "
                f"{DEFAULT_LOCALE}"
            )


def test_english_catalogue_has_no_leftover_russian() -> None:
    leftovers = [
        key for key, value in CATALOGUE["en"].items() if CYRILLIC.search(value)
    ]
    assert not leftovers, f"untranslated English entries: {leftovers}"


def test_unknown_key_raises_instead_of_rendering_a_placeholder() -> None:
    with pytest.raises(KeyError):
        get_translator()("no.such.key")


def test_unknown_locale_falls_back_to_the_default() -> None:
    translator = Translator("klingon")
    assert translator.locale == DEFAULT_LOCALE
    assert translator("app.analyze") == CATALOGUE[DEFAULT_LOCALE]["app.analyze"]


def test_translator_formats_parameters() -> None:
    rendered = get_translator()("app.status.done", run_id="2026-07-31T18-04-12")
    assert "2026-07-31T18-04-12" in rendered


@pytest.mark.parametrize("locale", LOCALES)
def test_every_locale_builds_a_complete_interface(locale: str) -> None:
    config = build_app(locale=locale).get_config_file()
    t = get_translator(locale)
    labels = {
        component["props"].get("label")
        for component in config["components"]
        if "props" in component
    }
    assert t("app.audio.label") in labels
    assert t("app.detectors.label") in labels


def test_russian_interface_contains_no_english_defaults() -> None:
    """The Russian build must not silently fall back to English labels."""
    config = build_app(locale="ru").get_config_file()
    labels = {
        component["props"].get("label")
        for component in config["components"]
        if "props" in component
    }
    english = get_translator("en")
    russian = get_translator("ru")
    for key in ("app.audio.label", "app.analyze", "app.high_detail"):
        assert russian(key) != english(key), f"{key} is identical in both locales"
        assert english(key) not in labels


def test_language_memory_only_redirects_from_the_default_path() -> None:
    """A locale path must never bounce, or the switcher could not leave it."""
    script = language_memory_head()
    assert "localStorage" in script
    assert 'if (here !== "/") return;' in script
    for code in LOCALES:
        assert f'"{code}": "{LOCALE_PATHS[code]}"' in script
