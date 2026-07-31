import numpy as np
import pytest

from adapters.lofcz_cli import (
    compute_fakeprint_telemetry,
    frames_in_window,
    plan_windows,
    strongest_peaks,
)


def test_fakeprint_telemetry_matches_hull_residue_and_normalization() -> None:
    frequencies = np.linspace(0, 8_000, 17, dtype=np.float32)
    spectrum = np.array(
        [-40, -40, -40, -40, -30, -40, -40, -20, -40, -40, -40, -40, -40, -40, -40, -40, -40],
        dtype=np.float32,
    )

    telemetry = compute_fakeprint_telemetry(
        spectrum,
        frequencies,
        freq_min=1_000,
        freq_max=8_000,
        hull_area=3,
        min_db=-45,
        max_db=5,
    )

    assert telemetry["frequency_hz"][0] == 1_000
    assert telemetry["fakeprint"].max() == np.float32(1.0)
    assert np.all(telemetry["residue_db"] >= 0)
    assert telemetry["fakeprint"].shape == telemetry["frequency_hz"].shape


def test_strongest_peaks_are_sorted_by_strength() -> None:
    peaks = strongest_peaks(
        np.array([1_000, 2_000, 3_000, 4_000], dtype=np.float32),
        np.array([0.1, 0.9, 0.3, 0.7], dtype=np.float32),
        limit=3,
    )

    assert [item["frequency_hz"] for item in peaks] == [2_000.0, 4_000.0, 3_000.0]


def test_plan_windows_slides_and_closes_the_tail() -> None:
    windows = plan_windows(32.0, window_seconds=15.0, hop_seconds=5.0)

    assert windows[0] == (0.0, 15.0)
    assert windows[1] == (5.0, 20.0)
    # Tail window is flush with the end so the last seconds are never dropped.
    assert windows[-1] == (17.0, 32.0)
    assert all(end - start == 15.0 for start, end in windows)


def test_plan_windows_returns_single_window_for_short_audio() -> None:
    assert plan_windows(8.0, window_seconds=15.0, hop_seconds=5.0) == [(0.0, 8.0)]


def test_plan_windows_without_tail_gap_does_not_duplicate() -> None:
    windows = plan_windows(20.0, window_seconds=10.0, hop_seconds=5.0)

    assert windows == [(0.0, 10.0), (5.0, 15.0), (10.0, 20.0)]


def test_plan_windows_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        plan_windows(0.0, window_seconds=10.0, hop_seconds=5.0)
    with pytest.raises(ValueError):
        plan_windows(30.0, window_seconds=0.0, hop_seconds=5.0)


def test_frames_in_window_selects_half_open_range() -> None:
    times = np.array([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float64)

    assert frames_in_window(times, 0.25, 0.75).tolist() == [1, 2]


def test_frames_in_window_falls_back_to_nearest_frame() -> None:
    times = np.array([0.0, 1.0, 2.0], dtype=np.float64)

    # A window that lands between frames still returns the closest one.
    assert frames_in_window(times, 1.1, 1.2).tolist() == [1]
