"""Repairing generation artifacts, aimed by measurement rather than by ear.

The chain is deliberately two layers, and they are not allowed to mix:

* **Repair** — de-artifact, restore air, transients, noise floor, stereo. Each
  one exists because a specific number on the Artifacts tab says the defect is
  there, and each one is switched on by that number, not by a preset. A repair
  module carries the evidence that turned it on, so the interface can say *why*
  a box is ticked instead of asserting that it knows best.
* **Taste** — warmth and high-frequency cleanup. This is where presets live.
  A preset may never reach into the repair layer: if the choice of a musical
  pass could silently change which defects get fixed, the measurement stops
  being the thing that drives the repair.

Two rules hold the whole module together:

* **The level does not change.** No normalisation, no limiter. The output keeps
  the level of the source, and gain is only ever pulled back when true peak
  would otherwise leave the ceiling. An A/B where B is louder always sounds
  better, which makes it worthless as evidence.
* **Every run is reproducible.** Same input, same settings, same output. The
  settings that produced a file travel with the result.

Chain order is argued rather than inherited: de-artifact goes before anything
that adds harmonics, so the notches aim at the spectrum that was measured;
`restore_air` goes *after* cleanup, because a cleanup stage placed downstream
would eat the top end that was just synthesised.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np
import soundfile as sf
from scipy import signal

from .artifact_metrics import (
    DB_FLOOR,
    HIGH_BAND_HZ,
    LOW_BAND_HZ,
    ArtifactMetrics,
    attack_sharpness_db,
    band_stereo_correlation,
    hf_cliff_db_per_octave,
    hf_cutoff_hz,
    measure_artifacts,
    noise_floor,
    rms_envelope_db,
    spectral_rolloff_hz,
    tonal_peaks,
)

EPSILON: Final[float] = 1e-12

#: Ceiling for the true-peak check. Anything below it is left completely alone.
TRUE_PEAK_CEILING_DBTP: Final[float] = -1.0
TRUE_PEAK_OVERSAMPLING: Final[int] = 4

WARMTH_CHARACTERS: Final[tuple[str, ...]] = ("tape", "tube", "console", "warm")
CLEANUP_STRENGTHS: Final[tuple[str, ...]] = (
    "soft",
    "medium",
    "strong",
    "tails_only",
    "air_clean",
)

#: Repair modules, in the order the chain applies them.
REPAIR_MODULES: Final[tuple[str, ...]] = (
    "de_artifact",
    "fix_transients",
    "restore_air",
    "restore_floor",
    "fix_stereo",
)

#: Repairs that can lower a detector score without the audio getting better,
#: by removing a signal the detector reads rather than a defect a listener
#: hears. Both synthesise material that was not there; both are proven on their
#: own, against a blind listen, before they are trusted.
MASKING_RISK_MODULES: Final[frozenset[str]] = frozenset(
    {"restore_air", "restore_floor"}
)


# --------------------------------------------------------------------------
# settings
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WarmthSettings:
    """Parallel saturation.

    `drive` is how hard the signal hits the nonlinearity, `mix` how much of the
    result is blended back. They are two controls for one idea and move
    together unless deliberately unlinked — every preset measured from a
    working implementation kept `mix` at roughly 1.4x `drive`.
    """

    enabled: bool = False
    character: str = "warm"
    drive: float = 0.10
    mix: float = 0.14
    #: Post-saturation tilt. Negative is darker, and it usually is: this stage
    #: mostly exists to pay back the brightness that restored air and added
    #: harmonics put in.
    tone: float = -0.05


@dataclass(frozen=True)
class CleanupSettings:
    """Downward expansion of quiet high-frequency debris."""

    enabled: bool = False
    strength: str = "soft"


@dataclass(frozen=True)
class RepairSettings:
    de_artifact: bool = False
    restore_air: bool = False
    fix_transients: bool = False
    restore_floor: bool = False
    fix_stereo: bool = False

    def enabled(self, module: str) -> bool:
        return bool(getattr(self, module))


@dataclass(frozen=True)
class SunoFixSettings:
    preset: str = "repair_only"
    repair: RepairSettings = field(default_factory=RepairSettings)
    warmth: WarmthSettings = field(default_factory=WarmthSettings)
    cleanup: CleanupSettings = field(default_factory=CleanupSettings)


#: Taste layer only. A preset never touches `RepairSettings` — see the module
#: docstring. Starting values are the ones measured off a working
#: implementation rather than invented, and are a hypothesis until an A/B of
#: our own says otherwise.
PRESETS: Final[dict[str, tuple[WarmthSettings, CleanupSettings]]] = {
    # Repair and nothing else: the honest default.
    "repair_only": (
        WarmthSettings(enabled=False, drive=0.12, mix=0.18, tone=-0.05),
        CleanupSettings(enabled=True, strength="soft"),
    ),
    # For a track that is already close and only wants holding together.
    "soft_glue": (
        WarmthSettings(enabled=True, drive=0.08, mix=0.12, tone=-0.05),
        CleanupSettings(enabled=False, strength="soft"),
    ),
    # The one pass whose job is the top end, and so the only one with a flat
    # tone control.
    "open_top": (
        WarmthSettings(enabled=True, drive=0.08, mix=0.12, tone=0.00),
        CleanupSettings(enabled=False, strength="soft"),
    ),
    # Harshness first: cleanup on, saturation kept modest.
    "de_harsh": (
        WarmthSettings(enabled=True, drive=0.10, mix=0.14, tone=-0.05),
        CleanupSettings(enabled=True, strength="soft"),
    ),
    # Body and density. The darkest tone, because the most saturation.
    "add_body": (
        WarmthSettings(enabled=True, drive=0.22, mix=0.30, tone=-0.10),
        CleanupSettings(enabled=False, strength="soft"),
    ),
}

#: strength -> (band start Hz, threshold dBFS, ratio, deepest cut dB, tails only)
CLEANUP_PROFILES: Final[dict[str, tuple[float, float, float, float, bool]]] = {
    "soft": (8_000.0, -55.0, 1.5, 6.0, False),
    "medium": (6_000.0, -50.0, 2.0, 10.0, False),
    "strong": (5_000.0, -45.0, 3.0, 16.0, False),
    "tails_only": (7_000.0, -50.0, 2.5, 10.0, True),
    "air_clean": (12_000.0, -50.0, 2.5, 12.0, False),
}


def preset_settings(name: str) -> SunoFixSettings:
    """A preset resolved to settings, with the repair layer left untouched."""
    warmth, cleanup = PRESETS.get(name, PRESETS["repair_only"])
    resolved = name if name in PRESETS else "repair_only"
    return SunoFixSettings(preset=resolved, warmth=warmth, cleanup=cleanup)


# --------------------------------------------------------------------------
# recommendations — the repair layer's only legitimate source
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Recommendation:
    """One repair module, and the measurement that argues for it."""

    module: str
    recommended: bool
    evidence: dict[str, float | tuple[float, ...]] = field(default_factory=dict)
    #: Marks a repair that can lower a detector score without the audio
    #: getting better — the failure mode the project refuses to ship blindly.
    masking_risk: bool = False


#: A wall this steep is a lowpass, not a musical rolloff.
CLIFF_SLOPE_DB_PER_OCTAVE: Final[float] = -25.0
CLIFF_BELOW_HZ: Final[float] = 17_500.0
#: Below this the material never gets sharp; every reference in the corpus of
#: real recordings sits well above it. Still a threshold, not a law of nature —
#: read it against references measured the same way.
SMEARED_ATTACK_DB: Final[float] = 6.0
STERILE_FLATNESS: Final[float] = 0.55
STERILE_FLOOR_DBFS: Final[float] = -70.0
COLLAPSED_CORRELATION: Final[float] = 0.97
PHASEY_CORRELATION: Final[float] = 0.0


def recommend(metrics: ArtifactMetrics) -> tuple[Recommendation, ...]:
    """Read the measurements and say which repairs the file argues for.

    Everything here is a threshold on a number that was measured from the
    signal. Nothing consults a detector, and nothing consults a preset.
    """
    peaks = metrics.tonal_peaks
    strongest = max((peak.prominence_db for peak in peaks), default=0.0)
    cutoff = metrics.hf_cutoff_hz
    high = metrics.stereo_correlation_high

    return (
        Recommendation(
            module="de_artifact",
            recommended=bool(peaks),
            evidence={
                "prominence_db": strongest,
                "frequencies_hz": tuple(peak.frequency_hz for peak in peaks[:3]),
            },
        ),
        Recommendation(
            module="fix_transients",
            recommended=metrics.attack_sharpness_db < SMEARED_ATTACK_DB,
            evidence={"attack_db": metrics.attack_sharpness_db},
        ),
        Recommendation(
            module="restore_air",
            recommended=(
                0.0 < cutoff < CLIFF_BELOW_HZ
                and metrics.hf_cliff_db_per_octave < CLIFF_SLOPE_DB_PER_OCTAVE
            ),
            evidence={
                "cutoff_hz": cutoff,
                "slope_db_per_octave": metrics.hf_cliff_db_per_octave,
            },
            masking_risk="restore_air" in MASKING_RISK_MODULES,
        ),
        Recommendation(
            module="restore_floor",
            recommended=(
                metrics.noise_floor_flatness > STERILE_FLATNESS
                and metrics.noise_floor_dbfs < STERILE_FLOOR_DBFS
            ),
            evidence={
                "flatness": metrics.noise_floor_flatness,
                "floor_dbfs": metrics.noise_floor_dbfs,
            },
            masking_risk="restore_floor" in MASKING_RISK_MODULES,
        ),
        Recommendation(
            module="fix_stereo",
            recommended=high is not None
            and (high > COLLAPSED_CORRELATION or high < PHASEY_CORRELATION),
            evidence={"correlation_high": high if high is not None else 0.0},
        ),
    )


def recommended_repair(metrics: ArtifactMetrics) -> RepairSettings:
    """The repair layer as the measurements would set it."""
    ticked = {item.module: item.recommended for item in recommend(metrics)}
    return RepairSettings(**ticked)


# --------------------------------------------------------------------------
# filter helpers
# --------------------------------------------------------------------------


def _biquad(b0: float, b1: float, b2: float, a0: float, a1: float, a2: float) -> np.ndarray:
    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]])


def peaking_sos(sample_rate: int, frequency: float, q: float, gain_db: float) -> np.ndarray:
    """RBJ peaking EQ — the surgical cut `de_artifact` is built from."""
    amplitude = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * frequency / sample_rate
    alpha = np.sin(w0) / (2.0 * q)
    cos_w0 = np.cos(w0)
    return _biquad(
        1.0 + alpha * amplitude,
        -2.0 * cos_w0,
        1.0 - alpha * amplitude,
        1.0 + alpha / amplitude,
        -2.0 * cos_w0,
        1.0 - alpha / amplitude,
    )


def shelf_sos(
    sample_rate: int, frequency: float, gain_db: float, *, high: bool
) -> np.ndarray:
    """RBJ shelving filter with S=1 — one half of the tone tilt."""
    amplitude = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * frequency / sample_rate
    alpha = np.sin(w0) / 2.0 * np.sqrt(2.0)
    cos_w0 = np.cos(w0)
    root = 2.0 * np.sqrt(amplitude) * alpha
    plus, minus = amplitude + 1.0, amplitude - 1.0
    if high:
        return _biquad(
            amplitude * (plus + minus * cos_w0 + root),
            -2.0 * amplitude * (minus + plus * cos_w0),
            amplitude * (plus + minus * cos_w0 - root),
            plus - minus * cos_w0 + root,
            2.0 * (minus - plus * cos_w0),
            plus - minus * cos_w0 - root,
        )
    return _biquad(
        amplitude * (plus - minus * cos_w0 + root),
        2.0 * amplitude * (minus - plus * cos_w0),
        amplitude * (plus - minus * cos_w0 - root),
        plus + minus * cos_w0 + root,
        -2.0 * (minus + plus * cos_w0),
        plus + minus * cos_w0 - root,
    )


def _apply(sos: np.ndarray, audio: np.ndarray, *, zero_phase: bool = True) -> np.ndarray:
    """Filter every channel.

    Zero phase by default: these are corrective filters, and a corrective
    filter that also smears phase trades one artifact for another.
    """
    # sosfiltfilt pads by 3*(2*sections+1); a buffer shorter than that raises
    # rather than filtering, and a clip too short to filter is not an error.
    if audio.shape[0] <= 6 * sos.shape[0] + 12:
        return audio
    runner = signal.sosfiltfilt if zero_phase else signal.sosfilt
    return np.stack(
        [runner(sos, audio[:, channel]) for channel in range(audio.shape[1])],
        axis=1,
    )


def _zero_phase_gain_db(gain_db: float) -> float:
    """Half the gain, because `_apply` runs the filter forward and backward.

    Zero-phase filtering passes the signal through the same response twice, so
    a biquad designed for -6 dB delivers -12. Every filter here whose depth is
    a calibrated number rather than a colour has to be designed for half of it.
    """
    return gain_db / 2.0


def _one_pole(values: np.ndarray, seconds: float, sample_rate: int) -> np.ndarray:
    """Smoothing that stays vectorised.

    A real compressor uses different attack and release constants, which needs
    a per-sample loop and would make a five-minute track take minutes to
    process in Python. Smoothing the *gain* symmetrically instead costs some
    transient precision and buys a chain that runs in seconds; the modules here
    are corrective and gentle enough that the trade holds.
    """
    coefficient = float(np.exp(-1.0 / max(seconds * sample_rate, 1.0)))
    return signal.lfilter([1.0 - coefficient], [1.0, -coefficient], values, axis=0)


def _envelope_db(audio: np.ndarray, seconds: float, sample_rate: int) -> np.ndarray:
    mono = np.mean(np.square(audio), axis=1)
    smoothed = _one_pole(mono, seconds, sample_rate)
    return 10.0 * np.log10(np.maximum(smoothed, EPSILON))


def _band_split(audio: np.ndarray, sample_rate: int, crossover_hz: float):
    """Split into low and high at `crossover_hz`, summing back to the input."""
    nyquist = sample_rate / 2.0
    normalised = min(max(crossover_hz / nyquist, 1e-4), 0.99)
    sos = signal.butter(4, normalised, btype="lowpass", output="sos")
    low = _apply(sos, audio)
    return low, audio - low


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values)) + EPSILON))


# --------------------------------------------------------------------------
# repair modules
# --------------------------------------------------------------------------

#: A notch is pulled down until the ridge stands only this far above its
#: neighbourhood. Flattening it completely would leave an audible hole where a
#: real partial used to be.
RESIDUAL_PROMINENCE_DB: Final[float] = 3.0
DEEPEST_NOTCH_DB: Final[float] = -12.0
NOTCH_Q: Final[float] = 26.0


def de_artifact(
    audio: np.ndarray, sample_rate: int, peaks, amount: float = 1.0
) -> tuple[np.ndarray, dict[str, float | tuple[float, ...]]]:
    """Narrow cuts at the measured tonal ridges.

    The whistles a generator leaves sit at a fixed frequency for the whole
    track, which is what makes a static notch the right tool and what
    distinguishes them from a real instrument's partials.
    """
    applied: list[float] = []
    out = audio
    for peak in peaks:
        gain_db = max(
            DEEPEST_NOTCH_DB,
            -amount * (peak.prominence_db - RESIDUAL_PROMINENCE_DB),
        )
        if gain_db >= -0.5 or peak.frequency_hz >= sample_rate / 2.0 * 0.98:
            continue
        out = _apply(
            peaking_sos(
                sample_rate,
                peak.frequency_hz,
                NOTCH_Q,
                _zero_phase_gain_db(gain_db),
            ),
            out,
        )
        applied.append(peak.frequency_hz)
    return out, {
        "notches": float(len(applied)),
        "frequencies_hz": tuple(applied),
    }


def fix_transients(
    audio: np.ndarray, sample_rate: int, amount: float = 0.5
) -> tuple[np.ndarray, dict[str, float]]:
    """Give attacks back the rise that smearing took off them.

    The gain follows how far a fast envelope runs ahead of a slow one, which is
    high exactly during an attack and near zero everywhere else. Only upward:
    pulling sustain down would be a different edit with a different argument.
    """
    fast = _envelope_db(audio, 0.005, sample_rate)
    slow = _envelope_db(audio, 0.080, sample_rate)
    boost_db = np.clip((fast - slow) * amount, 0.0, 6.0)
    gain = _one_pole(10.0 ** (boost_db / 20.0), 0.003, sample_rate)
    out = audio * gain[:, None]
    return out, {"peak_boost_db": float(np.max(boost_db)), "amount": amount}


def restore_air(
    audio: np.ndarray,
    sample_rate: int,
    cutoff_hz: float,
    amount: float = 0.6,
    below_source_db: float = 9.0,
) -> tuple[np.ndarray, dict[str, float]]:
    """Rebuild the band above the wall from the octave below it.

    Rectifying a bandpassed copy generates harmonics that land an octave up and
    keep the material's own rhythm and timbre, which a noise generator cannot.
    The new band is deliberately set *below* the level of the source band, so
    the result continues a rolloff instead of announcing a new one.
    """
    nyquist = sample_rate / 2.0
    top = min(cutoff_hz * 2.0, nyquist * 0.94)
    if cutoff_hz <= 0.0 or top <= cutoff_hz * 1.05:
        return audio, {"cutoff_hz": cutoff_hz, "added_db": 0.0}

    source_band = signal.butter(
        4,
        [max(cutoff_hz * 0.5, 1.0) / nyquist, min(cutoff_hz * 0.98, nyquist * 0.99) / nyquist],
        btype="bandpass",
        output="sos",
    )
    source = _apply(source_band, audio)
    generated = np.abs(source) - np.mean(np.abs(source), axis=0, keepdims=True)

    new_band = signal.butter(
        4,
        [min(cutoff_hz, nyquist * 0.9) / nyquist, top / nyquist],
        btype="bandpass",
        output="sos",
    )
    generated = _apply(new_band, generated)
    if _rms(generated) <= EPSILON:
        return audio, {"cutoff_hz": cutoff_hz, "added_db": 0.0}

    target = _rms(source) * (10.0 ** (-below_source_db / 20.0)) * amount
    generated *= target / _rms(generated)
    return audio + generated, {
        "cutoff_hz": cutoff_hz,
        "added_db": float(20.0 * np.log10(max(_rms(generated), EPSILON))),
    }


def restore_floor(
    audio: np.ndarray, sample_rate: int, floor_dbfs: float, lift_db: float = 4.0
) -> tuple[np.ndarray, dict[str, float]]:
    """Put a plausible noise floor under material that has none.

    Pink rather than white, because a room, a preamp and a microphone never
    produce a flat floor — and flatness is precisely what the measurement
    flagged.
    """
    target_db = min(floor_dbfs + lift_db, -60.0)
    rng = np.random.default_rng(0xA17)  # fixed: a run has to repeat exactly
    noise = rng.normal(0.0, 1.0, audio.shape)
    pink = _apply(
        signal.butter(1, min(500.0 / (sample_rate / 2.0), 0.99), btype="lowpass", output="sos"),
        noise,
        zero_phase=False,
    )
    pink = pink * 0.7 + noise * 0.3
    pink *= (10.0 ** (target_db / 20.0)) / max(_rms(pink), EPSILON)
    return audio + pink, {"target_dbfs": target_db}


def stereo_side_gain_db(correlation_high: float) -> float:
    """How much side level to add or remove, judged from the correlation alone.

    Anything inside the acceptable window is left completely alone — most music
    lives there, and a module that pulled every track toward one "correct"
    width would be a taste control wearing a repair badge. The correction also
    fades to zero at each edge of the window, so material sitting right on a
    threshold cannot flip between untouched and heavily narrowed.
    """
    if correlation_high > COLLAPSED_CORRELATION:
        over = (correlation_high - COLLAPSED_CORRELATION) / (1.0 - COLLAPSED_CORRELATION)
        return float(min(over, 1.0) * 3.0)
    if correlation_high < PHASEY_CORRELATION:
        return float(max(correlation_high, -1.0) * 6.0)
    return 0.0


def fix_stereo(
    audio: np.ndarray,
    sample_rate: int,
    correlation_high: float | None,
    crossover_hz: float = 5_000.0,
) -> tuple[np.ndarray, dict[str, float]]:
    """Widen a collapsed top end, narrow a phasey one, touch nothing else.

    The low band is never corrected: width down there is a mono-compatibility
    decision for the mix, not a generation artifact.
    """
    if audio.shape[1] < 2 or correlation_high is None:
        return audio, {"side_gain_db": 0.0}

    side_gain_db = stereo_side_gain_db(correlation_high)
    if side_gain_db == 0.0:
        return audio, {"side_gain_db": 0.0}

    low, high = _band_split(audio, sample_rate, crossover_hz)
    mid = np.mean(high, axis=1, keepdims=True)
    side = (high - mid) * (10.0 ** (side_gain_db / 20.0))
    return low + mid + side, {"side_gain_db": side_gain_db}


# --------------------------------------------------------------------------
# taste modules
# --------------------------------------------------------------------------


def hf_cleanup(
    audio: np.ndarray, sample_rate: int, strength: str
) -> tuple[np.ndarray, dict[str, float]]:
    """Downward expansion of quiet high-frequency debris.

    Loud material passes untouched; only what sits below the threshold is
    pulled down, which is where the chirps and swirl of a generated top end
    live. `tails_only` narrows that further to the parts where the track is
    decaying, so sustained cymbals and air keep their level.
    """
    band_hz, threshold_db, ratio, deepest_db, tails_only = CLEANUP_PROFILES.get(
        strength, CLEANUP_PROFILES["soft"]
    )
    low, high = _band_split(audio, sample_rate, band_hz)

    level_db = _envelope_db(high, 0.020, sample_rate)
    below = np.maximum(threshold_db - level_db, 0.0)
    reduction_db = np.minimum(below * (1.0 - 1.0 / ratio), deepest_db)

    if tails_only:
        broadband = _envelope_db(audio, 0.050, sample_rate)
        falling = np.clip(-np.gradient(broadband) * 40.0, 0.0, 1.0)
        reduction_db = reduction_db * _one_pole(falling, 0.030, sample_rate)

    gain = _one_pole(10.0 ** (-reduction_db / 20.0), 0.015, sample_rate)
    return low + high * gain[:, None], {
        "band_hz": band_hz,
        "deepest_cut_db": float(np.max(reduction_db)),
    }


def _saturate(values: np.ndarray, character: str, drive: float, sample_rate: int) -> np.ndarray:
    """Four characters, each defined by which harmonics it makes.

    `warm` is the plain one and the default; `tube` is asymmetric and therefore
    even-order; `console` is odd-order and subtle; `tape` soft-clips and loses
    top end, which is what makes it read as tape rather than as distortion.
    """
    gain = 10.0 ** (drive * 20.0 / 20.0)
    driven = values * gain
    if character == "tube":
        bias = 0.25
        return np.tanh(driven + bias) - np.tanh(bias)
    if character == "console":
        clipped = np.clip(driven, -1.5, 1.5)
        return clipped - (clipped**3) / 6.75
    if character == "tape":
        soft = driven / (1.0 + np.abs(driven))
        return _apply(
            signal.butter(
                1, min(12_000.0 / (sample_rate / 2.0), 0.99), btype="lowpass", output="sos"
            ),
            soft,
        )
    return np.tanh(driven)


def warmth(
    audio: np.ndarray, sample_rate: int, settings: WarmthSettings
) -> tuple[np.ndarray, dict[str, float]]:
    """Parallel saturation with the wet path level-matched to the dry.

    Matching the levels before the blend is what makes `mix` a colour control
    rather than a volume control — otherwise every increase would "improve" the
    track by making it louder.
    """
    wet = _saturate(audio, settings.character, settings.drive, sample_rate)
    dry_rms, wet_rms = _rms(audio), _rms(wet)
    if wet_rms > EPSILON:
        wet *= dry_rms / wet_rms
    mixed = audio * (1.0 - settings.mix) + wet * settings.mix
    return mixed, {"drive": settings.drive, "mix": settings.mix}


#: Full-scale tilt at |tone| = 0.2, in dB at each end of the spectrum.
TONE_RANGE_DB: Final[float] = 6.0
TONE_PIVOT_HZ: Final[float] = 1_000.0


def tone_tilt(
    audio: np.ndarray, sample_rate: int, tone: float
) -> tuple[np.ndarray, dict[str, float]]:
    """A see-saw around 1 kHz: the top goes down as the bottom comes up."""
    tilt_db = float(np.clip(tone, -0.2, 0.2) / 0.2 * TONE_RANGE_DB)
    if abs(tilt_db) < 0.05:
        return audio, {"tilt_db": 0.0}
    half = _zero_phase_gain_db(tilt_db / 2.0)
    out = _apply(shelf_sos(sample_rate, TONE_PIVOT_HZ, -half, high=False), audio)
    out = _apply(shelf_sos(sample_rate, TONE_PIVOT_HZ, half, high=True), out)
    return out, {"tilt_db": tilt_db}


# --------------------------------------------------------------------------
# level policy
# --------------------------------------------------------------------------


def true_peak_dbtp(audio: np.ndarray, oversampling: int = TRUE_PEAK_OVERSAMPLING) -> float:
    """Peak of the reconstructed waveform, not of the samples.

    Inter-sample peaks are invisible to a sample-peak reading and audible after
    a converter or a lossy encoder rebuilds them.
    """
    if audio.shape[0] < 16:
        return float(20.0 * np.log10(max(np.max(np.abs(audio)), EPSILON)))
    upsampled = signal.resample_poly(audio, oversampling, 1, axis=0)
    return float(20.0 * np.log10(max(np.max(np.abs(upsampled)), EPSILON)))


def apply_level_policy(
    audio: np.ndarray, ceiling_dbtp: float = TRUE_PEAK_CEILING_DBTP
) -> tuple[np.ndarray, float]:
    """Leave the level alone unless true peak has left the ceiling.

    This is the whole loudness policy. There is no normalisation and no
    limiter: the output is a mastering-ready WAV, not a finished master, and an
    A/B is only readable when both sides sit at the same level.
    """
    measured = true_peak_dbtp(audio)
    if measured <= ceiling_dbtp:
        return audio, 0.0
    gain_db = ceiling_dbtp - measured
    return audio * (10.0 ** (gain_db / 20.0)), gain_db


# --------------------------------------------------------------------------
# the chain
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StepReport:
    module: str
    applied: bool
    values: dict[str, float | tuple[float, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class SunoFixResult:
    output_path: Path
    settings: SunoFixSettings
    before: ArtifactMetrics
    after: ArtifactMetrics
    steps: tuple[StepReport, ...]
    output_gain_db: float


def process_audio(
    audio: np.ndarray,
    sample_rate: int,
    settings: SunoFixSettings,
    metrics: ArtifactMetrics,
) -> tuple[np.ndarray, tuple[StepReport, ...], float]:
    """Run the chain in its argued order and report every step.

    Repair first and in measurement order, taste last. `restore_air` sits after
    `hf_cleanup` on purpose: a cleanup stage downstream of it would expand away
    the band that was just built.
    """
    out = np.asarray(audio, dtype=np.float64)
    if out.ndim == 1:
        out = out[:, None]
    steps: list[StepReport] = []

    def record(module: str, applied: bool, values: dict | None = None) -> None:
        steps.append(StepReport(module=module, applied=applied, values=values or {}))

    if settings.repair.de_artifact and metrics.tonal_peaks:
        out, values = de_artifact(out, sample_rate, metrics.tonal_peaks)
        record("de_artifact", True, values)
    else:
        record("de_artifact", False)

    if settings.repair.fix_transients:
        out, values = fix_transients(out, sample_rate)
        record("fix_transients", True, values)
    else:
        record("fix_transients", False)

    if settings.cleanup.enabled:
        out, values = hf_cleanup(out, sample_rate, settings.cleanup.strength)
        record("hf_cleanup", True, values)
    else:
        record("hf_cleanup", False)

    if settings.repair.restore_air:
        out, values = restore_air(out, sample_rate, metrics.hf_cutoff_hz)
        record("restore_air", True, values)
    else:
        record("restore_air", False)

    if settings.repair.restore_floor:
        out, values = restore_floor(out, sample_rate, metrics.noise_floor_dbfs)
        record("restore_floor", True, values)
    else:
        record("restore_floor", False)

    if settings.repair.fix_stereo:
        out, values = fix_stereo(out, sample_rate, metrics.stereo_correlation_high)
        record("fix_stereo", True, values)
    else:
        record("fix_stereo", False)

    # Tone belongs to the warmth stage and dies with it: it exists to pay back
    # that stage's brightness, so applying it alone would be a tone control
    # smuggled in behind a switch that is off.
    if settings.warmth.enabled:
        out, values = warmth(out, sample_rate, settings.warmth)
        record("warmth", True, values)
        out, values = tone_tilt(out, sample_rate, settings.warmth.tone)
        record("tone_tilt", values["tilt_db"] != 0.0, values)
    else:
        record("warmth", False)
        record("tone_tilt", False, {"tilt_db": 0.0})

    out, gain_db = apply_level_policy(out)
    record("level_policy", gain_db != 0.0, {"gain_db": gain_db})
    return out, tuple(steps), gain_db


def measure_array(audio: np.ndarray, sample_rate: int, name: str) -> ArtifactMetrics:
    """The same measurements as the Artifacts tab, taken on an in-memory buffer.

    Reading the output back through `measure_artifacts` would go through a file
    and a format conversion, which is exactly the "compare like with like"
    mistake the metrics documentation warns about.
    """
    stereo = audio if audio.ndim == 2 else audio[:, None]
    mono = np.ascontiguousarray(stereo.mean(axis=1, dtype=np.float64).astype(np.float32))
    nperseg = min(4096, stereo.shape[0])
    frequencies, _, spectrum = signal.stft(
        mono,
        fs=sample_rate,
        nperseg=nperseg,
        noverlap=min(nperseg // 2, nperseg - 1),
        boundary=None,
        padded=True,
        scaling="spectrum",
    )
    magnitude = np.abs(spectrum)
    average_power = np.mean(np.square(magnitude, dtype=np.float64), axis=1)
    average_db = np.maximum(
        20.0 * np.log10(np.maximum(np.sqrt(average_power), 1e-10)), DB_FLOOR
    )
    level, flatness = noise_floor(magnitude, frequencies)

    return ArtifactMetrics(
        name=name,
        duration_seconds=float(stereo.shape[0] / sample_rate),
        sample_rate=int(sample_rate),
        channels=int(stereo.shape[1]),
        attack_sharpness_db=attack_sharpness_db(rms_envelope_db(mono, int(sample_rate))),
        rolloff_95_hz=spectral_rolloff_hz(average_power, frequencies),
        hf_cliff_db_per_octave=hf_cliff_db_per_octave(average_db, frequencies),
        noise_floor_dbfs=level,
        noise_floor_flatness=flatness,
        stereo_correlation_low=band_stereo_correlation(stereo, int(sample_rate), LOW_BAND_HZ),
        stereo_correlation_high=band_stereo_correlation(stereo, int(sample_rate), HIGH_BAND_HZ),
        tonal_peaks=tonal_peaks(average_db, frequencies),
        hf_cutoff_hz=hf_cutoff_hz(average_db, frequencies),
    )


def run(
    source: Path,
    destination: Path,
    settings: SunoFixSettings,
    metrics: ArtifactMetrics | None = None,
) -> SunoFixResult:
    """Process one file into a new one, measured on both sides.

    The source is never touched: an edit produces a new file, and the numbers
    that come back are the A/B, not a claim that it got better.
    """
    source = Path(source).resolve()
    audio, sample_rate = sf.read(source, always_2d=True, dtype="float64")
    before = metrics if metrics is not None else measure_artifacts(source)

    processed, steps, gain_db = process_audio(audio, int(sample_rate), settings, before)

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # 24-bit: the output is a mastering intermediate, and 16 bits would put a
    # dither decision in the middle of a chain that has not finished yet.
    sf.write(destination, processed, int(sample_rate), subtype="PCM_24")

    return SunoFixResult(
        output_path=destination,
        settings=settings,
        before=before,
        after=measure_array(processed, int(sample_rate), destination.name),
        steps=steps,
        output_gain_db=gain_db,
    )
