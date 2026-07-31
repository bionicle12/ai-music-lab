import numpy as np
import pytest

from music_lab_ui.comparison import compare_features
from music_lab_ui.contracts import AudioFeatures, AudioMetadata, AudioMetrics


def feature_fixture(
    value: float = -40.0,
    duration: float = 120.0,
    frequency_bins: int = 256,
    time_bins: int = 512,
) -> AudioFeatures:
    return AudioFeatures(
        metadata=AudioMetadata(
            filename="fixture.wav",
            suffix=".wav",
            size_bytes=100,
            sample_rate=48_000,
            channels=2,
            frames=int(duration * 48_000),
            duration_seconds=duration,
            sha256="a" * 64,
        ),
        metrics=AudioMetrics(
            peak_dbfs=-1.0,
            rms_dbfs=-14.0,
            crest_factor_db=13.0,
            stereo_correlation=0.5,
            mid_side_ratio_db=6.0,
        ),
        time_axis=np.linspace(0, duration, time_bins, dtype=np.float32),
        frequency_axis=np.geomspace(20, 20_000, frequency_bins).astype(np.float32),
        spectrogram_db=np.full(
            (frequency_bins, time_bins), value, dtype=np.float32
        ),
        waveform_rms_db=np.full(time_bins, value, dtype=np.float32),
        average_spectrum_db=np.full(frequency_bins, value, dtype=np.float32),
    )


def test_compare_features_subtracts_current_minus_baseline() -> None:
    current = feature_fixture(-40.0)
    baseline = feature_fixture(-46.0)

    comparison = compare_features(current, baseline)

    assert comparison.spectrogram_delta_db[0, 0] == pytest.approx(6.0)
    assert comparison.waveform_delta_db[0] == pytest.approx(6.0)
    assert comparison.metric_rows[1]["delta"] == pytest.approx(0.0)


def test_compare_features_rejects_duration_mismatch_over_five_percent() -> None:
    current = feature_fixture(duration=120.0)
    baseline = feature_fixture(duration=100.0)

    with pytest.raises(ValueError, match="duration differs by more than 5%"):
        compare_features(current, baseline)


def test_compare_features_aligns_legacy_and_high_resolution_grids() -> None:
    baseline = feature_fixture(-46.0, frequency_bins=256, time_bins=512)
    current = feature_fixture(-40.0, frequency_bins=768, time_bins=1536)

    comparison = compare_features(current, baseline)

    assert comparison.spectrogram_delta_db.shape == (768, 1536)
    assert comparison.waveform_delta_db.shape == (1536,)
    assert comparison.spectrum_delta_db.shape == (768,)
    assert np.allclose(comparison.spectrogram_delta_db, 6.0)
