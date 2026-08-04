from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .contracts import (
    AnalysisRun,
    AudioFeatures,
    AudioMetadata,
    AudioMetrics,
    DetectorResult,
)
from .telemetry import DetectorTelemetry, file_sha256, validate_telemetry

SCHEMA_VERSION = 1


class HistoryStore:
    def __init__(self, db_path: Path, runs_dir: Path) -> None:
        self.db_path = db_path.resolve()
        self.runs_dir = runs_dir.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_info (
                    version INTEGER NOT NULL
                )
                """
            )
            if connection.execute("SELECT COUNT(*) FROM schema_info").fetchone()[0] == 0:
                connection.execute(
                    "INSERT INTO schema_info(version) VALUES (?)", (SCHEMA_VERSION,)
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    audio_path TEXT NOT NULL,
                    features_path TEXT NOT NULL,
                    result_path TEXT NOT NULL,
                    note TEXT NOT NULL,
                    selected_detectors TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    is_baseline INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def save_run(
        self,
        source: Path,
        features: AudioFeatures,
        results: list[DetectorResult],
        note: str,
        settings: Mapping[str, Any] | None = None,
    ) -> AnalysisRun:
        created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        run_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            + "-"
            + uuid.uuid4().hex[:10]
        )
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        audio_path = run_dir / f"input{source.suffix.lower()}"
        features_path = run_dir / "features.npz"
        result_path = run_dir / "result.json"
        shutil.copy2(source, audio_path)
        np.savez_compressed(
            features_path,
            metadata_json=json.dumps(asdict(features.metadata), ensure_ascii=False),
            metrics_json=json.dumps(asdict(features.metrics), ensure_ascii=False),
            time_axis=features.time_axis,
            frequency_axis=features.frequency_axis,
            spectrogram_db=features.spectrogram_db,
            waveform_rms_db=features.waveform_rms_db,
            average_spectrum_db=features.average_spectrum_db,
            analysis_settings_json=json.dumps(
                features.analysis_settings,
                ensure_ascii=False,
            ),
        )
        result_payload = {
            "run_id": run_id,
            "created_at": created_at,
            "note": note.strip(),
            # In the run file rather than in a database column: it is never
            # queried, and a new setting would otherwise mean a schema
            # migration over somebody's saved measurements.
            "settings": dict(settings or {}),
            "results": [asdict(result) for result in results],
        }
        result_path.write_text(
            json.dumps(result_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        selected = tuple(result.detector for result in results)
        results_json = json.dumps(
            [asdict(result) for result in results], ensure_ascii=False
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs(
                    run_id, created_at, filename, audio_path, features_path,
                    result_path, note, selected_detectors, results_json, is_baseline
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    created_at,
                    source.name,
                    str(audio_path),
                    str(features_path),
                    str(result_path),
                    note.strip(),
                    json.dumps(selected),
                    results_json,
                    0,
                ),
            )
        return self.get_run(run_id)

    def _row_to_run(self, row: sqlite3.Row) -> AnalysisRun:
        return AnalysisRun(
            run_id=row["run_id"],
            created_at=row["created_at"],
            filename=row["filename"],
            audio_path=Path(row["audio_path"]),
            features_path=Path(row["features_path"]),
            result_path=Path(row["result_path"]),
            note=row["note"],
            selected_detectors=tuple(json.loads(row["selected_detectors"])),
            results=tuple(
                DetectorResult(**payload)
                for payload in json.loads(row["results_json"])
            ),
            is_baseline=bool(row["is_baseline"]),
        )

    def list_runs(self) -> list[AnalysisRun]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def get_run(self, run_id: str) -> AnalysisRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown analysis run: {run_id}")
        return self._row_to_run(row)

    def get_baseline(self) -> AnalysisRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE is_baseline = 1 LIMIT 1"
            ).fetchone()
        return self._row_to_run(row) if row is not None else None

    def set_baseline(self, run_id: str) -> None:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT EXISTS(SELECT 1 FROM runs WHERE run_id = ?)", (run_id,)
            ).fetchone()[0]
            if not exists:
                raise KeyError(f"unknown analysis run: {run_id}")
            connection.execute("UPDATE runs SET is_baseline = 0")
            connection.execute(
                "UPDATE runs SET is_baseline = 1 WHERE run_id = ?", (run_id,)
            )

    def clear_baseline(self) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE runs SET is_baseline = 0")

    def load_features(self, run_id: str) -> AudioFeatures:
        run = self.get_run(run_id)
        with np.load(run.features_path, allow_pickle=False) as payload:
            metadata = AudioMetadata(**json.loads(str(payload["metadata_json"])))
            metrics = AudioMetrics(**json.loads(str(payload["metrics_json"])))
            settings = (
                json.loads(str(payload["analysis_settings_json"]))
                if "analysis_settings_json" in payload.files
                else {
                    "n_fft": 2048,
                    "stft_window_samples": 2048,
                    "stft_overlap_samples": 1536,
                    "frequency_bins": int(payload["frequency_axis"].size),
                    "time_bins": int(payload["time_axis"].size),
                    "db_floor": -100.0,
                    "legacy": 1,
                }
            )
            return AudioFeatures(
                metadata=metadata,
                metrics=metrics,
                time_axis=payload["time_axis"].copy(),
                frequency_axis=payload["frequency_axis"].copy(),
                spectrogram_db=payload["spectrogram_db"].copy(),
                waveform_rms_db=payload["waveform_rms_db"].copy(),
                average_spectrum_db=payload["average_spectrum_db"].copy(),
                analysis_settings=settings,
            )

    def save_telemetry(
        self,
        run_id: str,
        telemetry: dict[str, DetectorTelemetry],
    ) -> Path:
        run_dir = self.runs_dir / run_id
        if not run_dir.is_dir():
            raise KeyError(f"unknown analysis run directory: {run_id}")
        telemetry_root = run_dir / "telemetry"
        telemetry_root.mkdir(exist_ok=True)
        for detector, item in telemetry.items():
            validated = validate_telemetry(
                {
                    "detector": item.detector,
                    "scalars": item.scalars,
                    "arrays": item.arrays,
                    "warnings": item.warnings,
                }
            )
            detector_dir = telemetry_root / detector
            detector_dir.mkdir(exist_ok=True)
            arrays_path = detector_dir / "arrays.npz"
            arrays_temp = detector_dir / f".arrays-{uuid.uuid4().hex}.tmp"
            with arrays_temp.open("wb") as target:
                np.savez_compressed(target, **validated.arrays)
            arrays_temp.replace(arrays_path)
            metadata = {
                "detector": validated.detector,
                "scalars": validated.scalars,
                "warnings": list(validated.warnings),
                "arrays": {
                    name: {
                        "shape": list(array.shape),
                        "dtype": str(array.dtype),
                    }
                    for name, array in validated.arrays.items()
                },
                "arrays_sha256": file_sha256(arrays_path),
            }
            metadata_path = detector_dir / "telemetry.json"
            metadata_temp = detector_dir / f".telemetry-{uuid.uuid4().hex}.tmp"
            metadata_temp.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            metadata_temp.replace(metadata_path)
        return telemetry_root

    def load_telemetry(self, run_id: str) -> dict[str, DetectorTelemetry]:
        telemetry_root = self.runs_dir / run_id / "telemetry"
        if not telemetry_root.is_dir():
            return {}
        loaded: dict[str, DetectorTelemetry] = {}
        for detector_dir in telemetry_root.iterdir():
            metadata_path = detector_dir / "telemetry.json"
            arrays_path = detector_dir / "arrays.npz"
            if not metadata_path.is_file() or not arrays_path.is_file():
                continue
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if file_sha256(arrays_path) != metadata["arrays_sha256"]:
                raise ValueError(
                    f"telemetry checksum mismatch: {detector_dir.name}"
                )
            with np.load(arrays_path, allow_pickle=False) as payload:
                arrays = {name: payload[name].copy() for name in payload.files}
            item = validate_telemetry(
                {
                    "detector": metadata["detector"],
                    "scalars": metadata.get("scalars", {}),
                    "arrays": arrays,
                    "warnings": metadata.get("warnings", []),
                }
            )
            loaded[item.detector] = item
        return loaded
