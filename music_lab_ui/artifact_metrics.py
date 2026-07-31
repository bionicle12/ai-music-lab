"""Objective artifact measures that never consult a detector.

A detector score answers "does a model think this is generated". These answer
"what is actually wrong with the sound" — smeared attacks, a lowpass cliff, an
unnaturally clean noise floor, a collapsed or exaggerated stereo image. They are
plain signal measurements, so they stay meaningful when detectors disagree or go
out of domain, and they point at fixes a producer can actually make.

Absolute values mean little on their own: read them against reference tracks
measured the same way.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from .i18n import get_translator

EPSILON = 1e-10
DB_FLOOR = -120.0

ENVELOPE_WINDOW_SECONDS = 0.010
ENVELOPE_HOP_SECONDS = 0.005
ATTACK_LOOKBACK_SECONDS = 0.020
QUIET_FRAME_PERCENTILE = 10.0
LOW_BAND_HZ = (40.0, 500.0)
HIGH_BAND_HZ = (5_000.0, 16_000.0)


@dataclass(frozen=True)
class ArtifactMetrics:
    name: str
    duration_seconds: float
    sample_rate: int
    channels: int
    attack_sharpness_db: float
    rolloff_95_hz: float
    hf_cliff_db_per_octave: float
    noise_floor_dbfs: float
    noise_floor_flatness: float
    stereo_correlation_low: float | None
    stereo_correlation_high: float | None


def _db(values: np.ndarray | float) -> np.ndarray:
    return np.maximum(20.0 * np.log10(np.maximum(values, EPSILON)), DB_FLOOR)


def rms_envelope_db(
    mono: np.ndarray,
    sample_rate: int,
    window_seconds: float = ENVELOPE_WINDOW_SECONDS,
    hop_seconds: float = ENVELOPE_HOP_SECONDS,
) -> np.ndarray:
    """Short-window loudness envelope in dB — the basis for attack measurement."""
    window = max(1, int(round(window_seconds * sample_rate)))
    hop = max(1, int(round(hop_seconds * sample_rate)))
    if mono.size < window:
        return _db(np.array([np.sqrt(np.mean(np.square(mono, dtype=np.float64)))]))
    count = 1 + (mono.size - window) // hop
    frames = np.lib.stride_tricks.as_strided(
        mono,
        shape=(count, window),
        strides=(mono.strides[0] * hop, mono.strides[0]),
    )
    return _db(np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1)))


def attack_sharpness_db(
    envelope_db: np.ndarray,
    hop_seconds: float = ENVELOPE_HOP_SECONDS,
    lookback_seconds: float = ATTACK_LOOKBACK_SECONDS,
) -> float:
    """Typical steepest loudness rise over a short lookback.

    Deliberately a high percentile of all rises rather than detected onsets:
    onset detection is fragile across genres, while "how fast does this material
    get loud at its sharpest" survives guitars, drums and orchestra alike.
    Transient smearing — a classic generative artifact — lowers it.
    """
    lag = max(1, int(round(lookback_seconds / hop_seconds)))
    if envelope_db.size <= lag:
        return 0.0
    rises = envelope_db[lag:] - envelope_db[:-lag]
    # Ignore rises out of near-silence, which are gate artifacts, not attacks.
    audible = envelope_db[lag:] > (np.max(envelope_db) - 60.0)
    rises = rises[audible]
    if rises.size == 0:
        return 0.0
    return float(np.percentile(rises, 95.0))


def spectral_rolloff_hz(
    power_spectrum: np.ndarray,
    frequencies: np.ndarray,
    fraction: float = 0.95,
) -> float:
    """Frequency below which `fraction` of the energy lives."""
    total = float(np.sum(power_spectrum))
    if total <= 0:
        return 0.0
    cumulative = np.cumsum(power_spectrum) / total
    index = int(np.searchsorted(cumulative, fraction))
    return float(frequencies[min(index, frequencies.size - 1)])


def hf_cliff_db_per_octave(
    spectrum_db: np.ndarray,
    frequencies: np.ndarray,
    from_hz: float = 4_000.0,
) -> float:
    """Steepest fall above `from_hz`, in dB per octave.

    A generative or codec chain often ends in a hard lowpass wall; natural
    material rolls off gently. Very negative values mean a wall.
    """
    mask = (frequencies >= from_hz) & (frequencies > 0)
    band = frequencies[mask]
    values = spectrum_db[mask]
    if band.size < 4:
        return 0.0
    octaves = np.log2(band / band[0])
    steepest = 0.0
    for start in range(band.size - 1):
        end = int(np.searchsorted(octaves, octaves[start] + 1.0))
        if end >= band.size:
            break
        slope = (values[end] - values[start]) / max(octaves[end] - octaves[start], EPSILON)
        steepest = min(steepest, float(slope))
    return steepest


def noise_floor(
    magnitude: np.ndarray,
    frequencies: np.ndarray,
    percentile: float = QUIET_FRAME_PERCENTILE,
) -> tuple[float, float]:
    """Level and spectral flatness of the quietest frames.

    Flatness near 1 means the floor is white-noise-like; a very low and very flat
    floor is the signature of digitally clean material with no room or preamp
    noise of its own.
    """
    energies = np.sum(np.square(magnitude, dtype=np.float64), axis=0)
    if energies.size == 0:
        return DB_FLOOR, 0.0
    threshold = np.percentile(energies, percentile)
    quiet = magnitude[:, energies <= threshold]
    if quiet.size == 0:
        quiet = magnitude
    average = np.mean(np.square(quiet, dtype=np.float64), axis=1)
    level = float(_db(np.sqrt(np.mean(average))))

    band = (frequencies >= 1_000) & (frequencies <= 16_000)
    values = average[band] if np.any(band) else average
    values = np.maximum(values, EPSILON)
    geometric = float(np.exp(np.mean(np.log(values))))
    arithmetic = float(np.mean(values))
    flatness = geometric / arithmetic if arithmetic > 0 else 0.0
    return level, float(flatness)


def band_stereo_correlation(
    audio: np.ndarray,
    sample_rate: int,
    band: tuple[float, float],
) -> float | None:
    """Left/right correlation inside one band, or None for mono material."""
    if audio.ndim < 2 or audio.shape[1] < 2:
        return None
    nyquist = sample_rate / 2.0
    low = max(band[0], 1.0) / nyquist
    high = min(band[1], nyquist * 0.99) / nyquist
    if not 0 < low < high < 1:
        return None
    sos = signal.butter(4, [low, high], btype="bandpass", output="sos")
    left = signal.sosfiltfilt(sos, audio[:, 0].astype(np.float64))
    right = signal.sosfiltfilt(sos, audio[:, 1].astype(np.float64))
    if np.std(left) < EPSILON or np.std(right) < EPSILON:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def measure_artifacts(path: Path) -> ArtifactMetrics:
    resolved = Path(path).resolve()
    audio, sample_rate = sf.read(resolved, always_2d=True, dtype="float32")
    if audio.shape[0] == 0:
        raise ValueError(
            get_translator()("error.no_audio_data", name=resolved.name)
        )

    mono = np.ascontiguousarray(audio.mean(axis=1, dtype=np.float32))
    duration = audio.shape[0] / sample_rate

    nperseg = min(4096, audio.shape[0])
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
    level, flatness = noise_floor(magnitude, frequencies)

    return ArtifactMetrics(
        name=resolved.name,
        duration_seconds=float(duration),
        sample_rate=int(sample_rate),
        channels=int(audio.shape[1]),
        attack_sharpness_db=attack_sharpness_db(rms_envelope_db(mono, int(sample_rate))),
        rolloff_95_hz=spectral_rolloff_hz(average_power, frequencies),
        hf_cliff_db_per_octave=hf_cliff_db_per_octave(
            np.asarray(_db(np.sqrt(average_power))),
            frequencies,
        ),
        noise_floor_dbfs=level,
        noise_floor_flatness=flatness,
        stereo_correlation_low=band_stereo_correlation(audio, int(sample_rate), LOW_BAND_HZ),
        stereo_correlation_high=band_stereo_correlation(audio, int(sample_rate), HIGH_BAND_HZ),
    )
