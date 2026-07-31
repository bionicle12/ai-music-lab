from __future__ import annotations

import html

from .i18n import Translator, get_translator


#: (detector, topic) -> catalogue prefix. The three help lines of every topic
#: share a prefix and differ only by suffix, so a new topic needs one entry here
#: and three keys in the catalogue.
TOPICS: dict[tuple[str, str], str] = {
    ("lofcz", "fakeprint"): "help.lofcz.fakeprint",
    ("lofcz", "lower_hull"): "help.lofcz.lower_hull",
    ("FST", "stage1"): "help.fst.stage1",
    ("FST", "self_similarity"): "help.fst.self_similarity",
    ("FST", "fusion_gate"): "help.fst.fusion_gate",
}


def help_html(detector: str, topic: str, t: Translator | None = None) -> str:
    translate = t or get_translator()
    prefix = TOPICS[(detector, topic)]
    measurement = translate(f"{prefix}.measured")
    reading = translate(f"{prefix}.reading")
    limits = translate(f"{prefix}.limits")
    title = html.escape(f"{detector}: {topic}")
    return f"""
    <details class="telemetry-help">
      <summary aria-label="{translate('help.aria', title=title)}">!</summary>
      <div class="telemetry-help-body">
        <h4>{title}</h4>
        <strong>{translate('help.measured')}</strong><p>{html.escape(measurement)}</p>
        <strong>{translate('help.reading')}</strong><p>{html.escape(reading)}</p>
        <strong>{translate('help.limits')}</strong><p>{html.escape(limits)}</p>
      </div>
    </details>
    """
