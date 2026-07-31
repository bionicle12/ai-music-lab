from pathlib import Path

import numpy as np
import pytest

from music_lab_ui.history import HistoryStore
from music_lab_ui.telemetry import DetectorTelemetry, validate_telemetry


def test_validate_telemetry_rejects_non_finite_arrays() -> None:
    with pytest.raises(ValueError, match="finite"):
        validate_telemetry(
            {
                "detector": "lofcz",
                "scalars": {},
                "arrays": {"fakeprint": [0.1, float("nan")]},
                "warnings": [],
            }
        )


def test_history_roundtrips_optional_detector_telemetry(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3", tmp_path / "runs")
    run_id = "20260730T120000-telemetry"
    (store.runs_dir / run_id).mkdir()
    telemetry = DetectorTelemetry(
        detector="lofcz",
        scalars={"n_fft": 8192},
        arrays={
            "frequency_hz": np.array([1_000.0, 2_000.0], dtype=np.float32),
            "fakeprint": np.array([0.2, 0.8], dtype=np.float32),
        },
        warnings=(),
    )

    path = store.save_telemetry(run_id, {"lofcz": telemetry})
    loaded = store.load_telemetry(run_id)

    assert path.is_dir()
    assert loaded["lofcz"].scalars["n_fft"] == 8192
    assert np.array_equal(
        loaded["lofcz"].arrays["fakeprint"],
        telemetry.arrays["fakeprint"],
    )
    assert (path / "lofcz" / "telemetry.json").is_file()
    assert (path / "lofcz" / "arrays.npz").is_file()


def test_old_run_without_telemetry_loads_as_empty(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3", tmp_path / "runs")

    assert store.load_telemetry("missing-old-run") == {}
