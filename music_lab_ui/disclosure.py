"""Progressive disclosure: one component for every "click to read more".

This started as three near-identical `<details>` builders — a badge next to a
chart, a labelled row for a how-to — and a third was about to be added for legal
warnings. They are one thing with three settings, so they are one function.

The registry matters as much as the renderer. Every disclosure declares itself
in :data:`DISCLOSURES`, which gives it a stable id, puts that id in the markup
as ``data-disclosure``, and lets a test assert that everything declared is
actually rendered somewhere. That test is not hypothetical: a help topic sat
in the old map for months, wired to nothing, while the chart it described
carried the wrong explanation.

Layouts:

``badge``
    A small round glyph beside a chart, opening a popover. Nothing moves when
    it opens — the previous version pushed the chart down the page.
``row``
    A full-width labelled strip. For prose you might read start to finish, where
    displacing what follows is the correct behaviour and the title is the whole
    reason you would click.

Tones: ``info`` is cyan and neutral; ``warn`` is an amber triangle and means the
text under it changes what you are allowed to do, or what the numbers mean.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Final, Literal

from .i18n import Translator, get_translator

Tone = Literal["info", "warn"]
Layout = Literal["badge", "row"]

#: Inline SVG rather than `!`/`⚠`: neither Manrope nor JetBrains Mono carries
#: those glyphs, so a text badge silently falls back to whatever symbol font the
#: system supplies and stops matching the rest of the interface. `currentColor`
#: also lets the tone drive the colour without a second rule.
_GLYPHS: Final[dict[str, str]] = {
    "info": (
        '<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" '
        'focusable="false"><circle cx="8" cy="8" r="7" fill="none" '
        'stroke="currentColor" stroke-width="1.4"/>'
        '<path d="M8 7v4.4M8 4.4v.9" stroke="currentColor" stroke-width="1.6" '
        'stroke-linecap="round"/></svg>'
    ),
    "warn": (
        '<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" '
        'focusable="false"><path d="M8 2.2 14.6 13.4H1.4Z" fill="none" '
        'stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>'
        '<path d="M8 6.4v3.1M8 11.2v.1" stroke="currentColor" '
        'stroke-width="1.6" stroke-linecap="round"/></svg>'
    ),
}


@dataclass(frozen=True)
class Disclosure:
    #: Catalogue key prefix. ``<prefix>.title`` is always required, plus one key
    #: per entry in :attr:`sections`.
    prefix: str
    tone: Tone = "info"
    layout: Layout = "row"
    #: Key suffixes rendered in order. Multi-section disclosures also render a
    #: shared label above each one (``help.measured`` and friends).
    sections: tuple[str, ...] = ("body",)
    #: Bodies inserted without escaping, for catalogue entries that are authored
    #: markup. Never true for anything derived from user input.
    trusted_html: bool = False
    #: Rendered from a callback rather than at build time, so it is absent from
    #: a freshly built interface. Covered by a presenter test instead of the
    #: "is it on screen" sweep.
    runtime: bool = False


#: Shared labels for the three-part telemetry explanations.
SECTION_LABELS: Final[dict[str, str]] = {
    "measured": "help.measured",
    "reading": "help.reading",
    "limits": "help.limits",
}

TELEMETRY_SECTIONS: Final[tuple[str, ...]] = ("measured", "reading", "limits")


DISCLOSURES: Final[dict[str, Disclosure]] = {
    # ---- detector telemetry, beside the chart each one explains -----------
    "lofcz/lower_hull": Disclosure(
        prefix="help.lofcz.lower_hull",
        layout="badge",
        sections=TELEMETRY_SECTIONS,
    ),
    "lofcz/fakeprint": Disclosure(
        prefix="help.lofcz.fakeprint",
        layout="badge",
        sections=TELEMETRY_SECTIONS,
    ),
    "fst/stage1": Disclosure(
        prefix="help.fst.stage1",
        layout="badge",
        sections=TELEMETRY_SECTIONS,
    ),
    "fst/self_similarity": Disclosure(
        prefix="help.fst.self_similarity",
        layout="badge",
        sections=TELEMETRY_SECTIONS,
    ),
    "fst/fusion_gate": Disclosure(
        prefix="help.fst.fusion_gate",
        layout="badge",
        sections=TELEMETRY_SECTIONS,
    ),
    # ---- method notes, moved out of the top of each tab --------------------
    "spectrum/reading": Disclosure(
        prefix="disc.spectrum.reading",
        layout="badge",
        sections=TELEMETRY_SECTIONS,
    ),
    "timeline/method": Disclosure(prefix="disc.timeline.method"),
    "layers/what_to_load": Disclosure(prefix="disc.layers.what_to_load"),
    "layers/separation": Disclosure(prefix="disc.layers.separation", tone="warn"),
    "artifacts/metrics": Disclosure(
        prefix="disc.artifacts.metrics", trusted_html=True
    ),
    "artifacts/compare": Disclosure(prefix="disc.artifacts.compare", tone="warn"),
    "comparison/method": Disclosure(prefix="disc.comparison.method"),
    # ---- MIDI --------------------------------------------------------------
    "midi/stems": Disclosure(prefix="disc.midi.stems", tone="warn"),
    "midi/reproducibility": Disclosure(prefix="disc.midi.reproducibility"),
    "midi/basics": Disclosure(prefix="guide.midi.basics", trusted_html=True),
    "midi/drums": Disclosure(prefix="guide.midi.drums", trusted_html=True),
    "midi/acoustic": Disclosure(prefix="guide.midi.acoustic", trusted_html=True),
    "midi/bass": Disclosure(prefix="guide.midi.bass", trusted_html=True),
    # ---- the one long-form licence statement in the app --------------------
    "licence/weights": Disclosure(prefix="disc.licence.weights", tone="warn"),
    "token/handling": Disclosure(prefix="disc.token.handling"),
    "file/stereo": Disclosure(
        prefix="disc.file.stereo", layout="badge", sections=(), runtime=True
    ),
    # Body supplied at render time (the readiness checklist), so it declares no
    # catalogue sections — only a title.
    "midi/setup": Disclosure(prefix="disc.midi.setup", tone="warn", sections=()),
    "detector/caveat": Disclosure(
        prefix="detector.caveat", layout="badge", sections=(), runtime=True
    ),
    "fst/batch": Disclosure(prefix="detector.fst.batch", sections=("note",)),
    "provision/manual": Disclosure(prefix="disc.provision.manual", tone="warn"),
}

#: Rendered as a stack of rows under the MIDI transcription controls.
MIDI_GUIDES: Final[tuple[str, ...]] = (
    "midi/basics",
    "midi/drums",
    "midi/acoustic",
    "midi/bass",
)


_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_CODE = re.compile(r"`([^`]+)`")


def _inline(text: str) -> str:
    """Escape, then honour the two bits of Markdown the catalogue actually uses.

    Bodies reach the page through `gr.HTML`, not `gr.Markdown`, so `**bold**`
    would otherwise render as literal asterisks. Escaping first means the
    conversion can never introduce markup the translation did not ask for.
    """
    escaped = html.escape(text)
    escaped = _BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = _CODE.sub(r"<code>\1</code>", escaped)
    return "".join(
        f"<p>{paragraph}</p>" for paragraph in escaped.split("\n\n") if paragraph
    )


def _summary(disclosure: Disclosure, title: str, show_title: bool) -> str:
    glyph = _GLYPHS[disclosure.tone]
    label = f'<span class="lab-disclosure-title">{title}</span>' if show_title else ""
    return f'<span class="lab-disclosure-badge">{glyph}</span>{label}'


def disclosure_html(
    disclosure_id: str,
    t: Translator | None = None,
    *,
    body: str | None = None,
    open: bool = False,
) -> str:
    """Render one disclosure.

    ``body`` overrides the catalogue for run-specific text — a detector's
    caveat, a readiness checklist — which has no fixed key but belongs behind
    the same affordance as everything else.
    """
    translate = t or get_translator()
    spec = DISCLOSURES[disclosure_id]
    title = translate(f"{spec.prefix}.title")
    aria = translate(
        "help.aria.warn" if spec.tone == "warn" else "help.aria",
        title=html.escape(title),
    )

    if body is not None:
        content = body
    else:
        parts = []
        for section in spec.sections:
            text = translate(f"{spec.prefix}.{section}")
            label = SECTION_LABELS.get(section)
            if label:
                parts.append(f"<strong>{html.escape(translate(label))}</strong>")
            parts.append(text if spec.trusted_html else _inline(text))
        content = "\n".join(parts)

    classes = f"lab-disclosure tone-{spec.tone} layout-{spec.layout}"
    return f"""
    <details class="{classes}" data-disclosure="{html.escape(disclosure_id)}"{
        " open" if open else ""}>
      <summary aria-label="{html.escape(aria)}">
        {_summary(spec, html.escape(title), spec.layout == "row")}
      </summary>
      <div class="lab-disclosure-body">
        {'' if spec.layout == "row" else f'<h4>{html.escape(title)}</h4>'}
        {content}
      </div>
    </details>
    """
