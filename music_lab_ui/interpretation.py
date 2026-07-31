from __future__ import annotations

import html

import numpy as np

from .i18n import Translator, get_translator
from .telemetry import DetectorTelemetry


def interpret_run(
    telemetry: dict[str, DetectorTelemetry],
    t: Translator | None = None,
) -> str:
    translate = t or get_translator()
    observations: list[str] = []
    lofcz = telemetry.get("lofcz")
    if lofcz is not None and "fakeprint" in lofcz.arrays:
        peaks = lofcz.scalars.get("strongest_peaks", [])
        peak_text = (
            translate(
                "interpret.lofcz_peak",
                frequency=f"{float(peaks[0]['frequency_hz']):.0f}",
            )
            if peaks
            else ""
        )
        observations.append(
            translate("interpret.lofcz_available", peak=peak_text)
        )
    fst = telemetry.get("FST")
    if fst is not None:
        probabilities = fst.arrays.get("stage1_class_probabilities")
        if probabilities is not None and probabilities.size:
            spread = float(np.ptp(probabilities[:, 1]))
            observations.append(
                translate("interpret.fst_spread", spread=f"{spread:.3f}")
            )
        gates = fst.arrays.get("fusion_content_gate")
        if gates is not None and gates.size:
            observations.append(
                translate(
                    "interpret.fst_gate", value=f"{float(np.mean(gates)):.3f}"
                )
            )
    if not observations:
        observations.append(translate("interpret.missing"))
    items = "".join(f"<li>{html.escape(item)}</li>" for item in observations)
    return (
        '<section class="run-interpretation">'
        f"<h3>{translate('interpret.heading')}</h3>"
        f"<p><strong>{translate('interpret.experimental_label')}</strong> "
        f"{translate('interpret.experimental_body')}</p>"
        f"<ul>{items}</ul></section>"
    )
