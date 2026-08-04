import math
import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from music_lab_ui.audio_features import (
    extract_audio_features,
    extract_preview_features,
)


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


def test_preview_matches_the_full_extraction_where_they_overlap(
    tmp_path: Path,
) -> None:
    """The strip drawn on upload and the one drawn after the run are the same
    picture, so the chart must not visibly change under the user when the
    analysis finishes."""
    audio = write_stereo_sine(tmp_path / "tone.wav")

    preview = extract_preview_features(audio)
    full = extract_audio_features(audio)

    assert preview.metadata == full.metadata
    assert preview.metrics == full.metrics
    np.testing.assert_array_equal(preview.time_axis, full.time_axis)
    np.testing.assert_array_equal(preview.waveform_rms_db, full.waveform_rms_db)


def test_preview_leaves_the_spectral_fields_empty_rather_than_wrong(
    tmp_path: Path,
) -> None:
    """Empty is what makes a preview detectable; a zero-filled spectrogram of
    the right shape would be drawn as if it meant something."""
    preview = extract_preview_features(write_stereo_sine(tmp_path / "tone.wav"))

    assert preview.spectrogram_db.size == 0
    assert preview.average_spectrum_db.size == 0
    assert preview.frequency_axis.size == 0
    assert preview.analysis_settings == {}


def test_preview_rejects_empty_audio_too(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="contains no audio frames"):
        extract_preview_features(write_empty_wav(tmp_path / "empty.wav"))
