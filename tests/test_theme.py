"""Guards for the theme and the vendored fonts.

The load-bearing one is the offline promise: this app tells the user that
nothing leaves the machine, and a font stylesheet fetched from Google on every
launch would quietly make that false.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from music_lab_ui.app import (
    ASSET_MOUNT,
    FONTS_CSS_PATH,
    MONO_FONT,
    THEME,
    UI_FONT,
    font_face_head,
)

FONT_DIR = Path(__file__).parents[1] / "music_lab_ui" / "static" / "fonts"


def test_the_theme_never_fetches_a_stylesheet() -> None:
    """`gr.themes.GoogleFont` would emit a fonts.googleapis.com link; plain
    strings cannot. This is the whole reason the font names are strings."""
    assert THEME._stylesheets == []
    assert "googleapis" not in THEME._get_theme_css()


def test_the_theme_asks_for_the_vendored_families_first() -> None:
    assert THEME.font.startswith("'Manrope'")
    assert THEME.font_mono.startswith("'JetBrains Mono'")
    # Fallbacks survive, so a missing woff2 degrades rather than breaking — and
    # the generic must stay unquoted or it stops being a generic.
    assert THEME.font.endswith("sans-serif")
    assert THEME.font_mono.endswith("monospace")
    assert UI_FONT[-1].name == "sans-serif"
    assert MONO_FONT[-1].name == "monospace"


def test_every_vendored_font_is_a_real_woff2_with_its_licence() -> None:
    files = sorted(FONT_DIR.glob("*.woff2"))

    assert len(files) == 8  # two families × four unicode subsets
    for path in files:
        assert path.read_bytes()[:4] == b"wOF2", path.name
    for family in ("manrope", "jetbrains-mono"):
        # SIL OFL permits redistribution only if the licence travels along.
        assert (FONT_DIR / f"{family}-OFL.txt").is_file()
    assert sum(path.stat().st_size for path in files) < 250_000


def test_font_urls_are_absolute_and_point_at_files_that_exist() -> None:
    """Relative urls resolve against the document, and the interface is mounted
    at both `/` and `/ru/` — so the Russian build would look one level down."""
    head = font_face_head()
    urls = re.findall(r"url\('([^']+)'\)", head)

    assert urls
    for url in urls:
        assert url.startswith(f"{ASSET_MOUNT}/fonts/"), url
        assert (FONT_DIR / Path(url).name).is_file(), url


def test_both_scripts_are_covered() -> None:
    """The Russian build is not an afterthought: Cyrillic has its own slices."""
    css = FONTS_CSS_PATH.read_text(encoding="utf-8")

    for family in ("Manrope", "JetBrains Mono"):
        block = [line for line in css.splitlines() if family in line]
        assert block, family
    assert css.count("U+0400-045F") == 2  # the Cyrillic range, once per family


def test_static_assets_are_mounted_before_gradio_swallows_the_path() -> None:
    """The root Gradio mount matches everything unmatched, so ours must come
    first — and it must not be `/static`, which Gradio reserves."""
    from music_lab_ui.app import build_server

    paths = [getattr(route, "path", None) for route in build_server().routes]

    assert ASSET_MOUNT in paths
    # Starlette normalises the root mount's path to the empty string.
    assert paths.index(ASSET_MOUNT) < paths.index("")
    assert ASSET_MOUNT not in ("/static", "/assets")


@pytest.mark.parametrize("token", ["--font", "--font-mono"])
def test_the_theme_publishes_the_font_tokens(token: str) -> None:
    assert f"{token}:" in THEME._get_theme_css()
