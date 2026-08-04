from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from .contracts import AudioFeatures, AudioMetadata, AudioMetrics

DB_FLOOR = -100.0
FREQUENCY_BINS = 768
TIME_BINS = 1536
FFT_SIZE = 4096
EPSILON = 1e-10


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _db(amplitude: np.ndarray | float) -> np.ndarray | float:
    result = 20.0 * np.log10(np.maximum(amplitude, EPSILON))
    return np.maximum(result, DB_FLOOR)


def _interpolate_axis(
    values: np.ndarray, source_axis: np.ndarray, target_axis: np.ndarray
) -> np.ndarray:
    return np.vstack(
        [np.interp(target_axis, source_axis, row) for row in values]
    ).astype(np.float32)


def _waveform_envelope(mono: np.ndarray, duration: float) -> tuple[np.ndarray, np.ndarray]:
    edges = np.linspace(0, mono.size, TIME_BINS + 1, dtype=int)
    rms = np.empty(TIME_BINS, dtype=np.float32)
    for index in range(TIME_BINS):
        segment = mono[edges[index] : edges[index + 1]]
        if segment.size == 0:
            sample_index = min(edges[index], mono.size - 1)
            segment = mono[sample_index : sample_index + 1]
        rms[index] = float(np.sqrt(np.mean(np.square(segment), dtype=np.float64)))
    return (
        np.linspace(0.0, duration, TIME_BINS, dtype=np.float32),
        np.asarray(_db(rms), dtype=np.float32),
    )


def _read(path: Path) -> tuple[np.ndarray, int, np.ndarray, float]:
    audio, sample_rate = sf.read(path, always_2d=True, dtype="float32")
    if audio.shape[0] == 0:
        raise ValueError(f"{path.name} contains no audio frames")
    duration = audio.shape[0] / sample_rate
    return audio, int(sample_rate), audio.mean(axis=1, dtype=np.float32), duration


def _describe(
    path: Path, audio: np.ndarray, sample_rate: int, duration: float
) -> tuple[AudioMetadata, AudioMetrics]:
    frames, channels = audio.shape

    peak_dbfs = float(_db(float(np.max(np.abs(audio)))))
    rms_dbfs = float(
        _db(float(np.sqrt(np.mean(np.square(audio), dtype=np.float64))))
    )

    stereo_correlation: float | None = None
    mid_side_ratio_db: float | None = None
    if channels >= 2:
        left = audio[:, 0].astype(np.float64)
        right = audio[:, 1].astype(np.float64)
        if np.std(left) > EPSILON and np.std(right) > EPSILON:
            stereo_correlation = float(np.corrcoef(left, right)[0, 1])
        mid = (left + right) * 0.5
        side = (left - right) * 0.5
        mid_rms = np.sqrt(np.mean(np.square(mid)))
        side_rms = np.sqrt(np.mean(np.square(side)))
        mid_side_ratio_db = float(
            20.0 * np.log10(max(mid_rms, EPSILON) / max(side_rms, EPSILON))
        )

    metadata = AudioMetadata(
        filename=path.name,
        suffix=path.suffix.lower(),
        size_bytes=path.stat().st_size,
        sample_rate=int(sample_rate),
        channels=int(channels),
        frames=int(frames),
        duration_seconds=float(duration),
        sha256=_sha256(path),
    )
    metrics = AudioMetrics(
        peak_dbfs=peak_dbfs,
        rms_dbfs=rms_dbfs,
        crest_factor_db=float(peak_dbfs - rms_dbfs),
        stereo_correlation=stereo_correlation,
        mid_side_ratio_db=mid_side_ratio_db,
    )
    return metadata, metrics


def extract_preview_features(path: Path) -> AudioFeatures:
    """What the sidebar can show the moment a file is dropped on the page.

    The full extraction below resamples some twenty thousand spectrogram
    columns one at a time — the right price for an analysis run and the wrong
    one for a preview. The whole-track strip and the file card need the
    envelope, the identity and the three levels, none of which involve the
    transform, so this computes exactly those.

    The spectral fields come back empty rather than wrong. ``analysis_settings``
    stays empty too, which is how a caller can tell a preview from the real
    thing.
    """
    resolved = path.resolve()
    audio, sample_rate, mono, duration = _read(resolved)
    metadata, metrics = _describe(resolved, audio, sample_rate, duration)
    time_axis, waveform_rms_db = _waveform_envelope(mono, duration)
    empty = np.zeros(0, dtype=np.float32)
    return AudioFeatures(
        metadata=metadata,
        metrics=metrics,
        time_axis=time_axis,
        frequency_axis=empty,
        spectrogram_db=np.zeros((0, 0), dtype=np.float32),
        waveform_rms_db=waveform_rms_db,
        average_spectrum_db=empty,
    )


def extract_audio_features(path: Path) -> AudioFeatures:
    resolved = path.resolve()
    audio, sample_rate, mono, duration = _read(resolved)
    metadata, metrics = _describe(resolved, audio, sample_rate, duration)
    frames = audio.shape[0]

    nperseg = min(FFT_SIZE, frames)
    noverlap = min(int(nperseg * 0.875), nperseg - 1)
    frequencies, source_times, spectrum = signal.stft(
        mono,
        fs=sample_rate,
        nperseg=nperseg,
        noverlap=noverlap,
        boundary=None,
        padded=True,
        scaling="spectrum",
    )
    magnitude = np.abs(spectrum).astype(np.float32)
    magnitude_db = np.asarray(_db(magnitude), dtype=np.float32)

    max_frequency = min(sample_rate / 2.0, 20_000.0)
    min_frequency = min(20.0, max_frequency)
    target_frequencies = np.geomspace(
        max(min_frequency, EPSILON),
        max(max_frequency, min_frequency + EPSILON),
        FREQUENCY_BINS,
    ).astype(np.float32)
    frequency_resampled = np.vstack(
        [
            np.interp(target_frequencies, frequencies, magnitude_db[:, index])
            for index in range(magnitude_db.shape[1])
        ]
    ).T.astype(np.float32)
    target_times = np.linspace(0.0, duration, TIME_BINS, dtype=np.float32)
    spectrogram_db = _interpolate_axis(
        frequency_resampled, source_times, target_times
    )

    average_magnitude = np.sqrt(
        np.mean(np.square(magnitude, dtype=np.float64), axis=1)
    )
    average_spectrum_db = np.interp(
        target_frequencies,
        frequencies,
        np.asarray(_db(average_magnitude), dtype=np.float32),
    ).astype(np.float32)
    time_axis, waveform_rms_db = _waveform_envelope(mono, duration)

    return AudioFeatures(
        metadata=metadata,
        metrics=metrics,
        time_axis=time_axis,
        frequency_axis=target_frequencies,
        spectrogram_db=spectrogram_db,
        waveform_rms_db=waveform_rms_db,
        average_spectrum_db=average_spectrum_db,
        analysis_settings={
            "n_fft": FFT_SIZE,
            "stft_window_samples": nperseg,
            "stft_overlap_samples": noverlap,
            "frequency_bins": FREQUENCY_BINS,
            "time_bins": TIME_BINS,
            "db_floor": DB_FLOOR,
        },
    )
