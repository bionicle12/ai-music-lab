import math
import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from music_lab_ui.audio_features import extract_audio_features


def write_stereo_sine(
    path: Path, seconds: int = 2, sample_rate: int = 16_000
) -> Path:
    frames = bytearray()
    for index in range(seconds * sample_rate):
        sample = int(0.25 * 32767 * math.sin(2 * math.pi * 440 * index / sample_rate))
        frames.extend(struct.pack("<hh", sample, sample))
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)
    return path


def write_empty_wav(path: Path, sample_rate: int = 16_000) -> Path:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"")
    return path


def test_extract_audio_features_returns_fixed_finite_grids(tmp_path: Path) -> None:
    audio = write_stereo_sine(tmp_path / "tone.wav")

    features = extract_audio_features(audio)

    assert features.metadata.channels == 2
    assert features.metadata.sample_rate == 16_000
    assert features.metadata.duration_seconds == pytest.approx(2.0)
    assert len(features.metadata.sha256) == 64
    assert features.spectrogram_db.shape == (768, 1536)
    assert features.waveform_rms_db.shape == (1536,)
    assert features.average_spectrum_db.shape == (768,)
    assert features.analysis_settings["n_fft"] == 4096
    assert features.analysis_settings["frequency_bins"] == 768
    assert features.analysis_settings["time_bins"] == 1536
    assert features.analysis_settings["stft_overlap_samples"] == 3584
    assert np.isfinite(features.spectrogram_db).all()
    assert np.isfinite(features.waveform_rms_db).all()
    assert features.metrics.stereo_correlation == pytest.approx(1.0)


def test_extract_audio_features_rejects_empty_audio(tmp_path: Path) -> None:
    empty = write_empty_wav(tmp_path / "empty.wav")

    with pytest.raises(ValueError, match="contains no audio frames"):
        extract_audio_features(empty)
