from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from .artifact_metrics import ArtifactMetrics, measure_artifacts
from .audio_features import extract_audio_features
from .comparison import FeatureComparison, compare_features
from .config import LabPaths, default_paths
from .contracts import AnalysisRun, AudioFeatures, DetectorResult, LayerResult
from .detectors import ProgressCallback, run_lofcz, run_lofcz_timeline, run_selected
from .history import HistoryStore
from .i18n import Translator, get_translator
from .telemetry import DetectorTelemetry, validate_telemetry

FeatureExtractor = Callable[[Path], AudioFeatures]
DetectorRunner = Callable[
    [Path, list[str], LabPaths, ProgressCallback | None],
    list[DetectorResult],
]
TimelineRunner = Callable[..., dict]
LayerRunner = Callable[[Path, LabPaths], DetectorResult]
ArtifactMeasurer = Callable[[Path], ArtifactMetrics]


@dataclass(frozen=True)
class AnalysisOutcome:
    run: AnalysisRun
    features: AudioFeatures
    telemetry: dict[str, DetectorTelemetry] = field(default_factory=dict)


@dataclass(frozen=True)
class RunComparisonOutcome:
    run_a: AnalysisRun
    run_b: AnalysisRun
    features_a: AudioFeatures
    features_b: AudioFeatures
    comparison: FeatureComparison | None
    comparison_note: str | None
    telemetry_a: dict[str, DetectorTelemetry] = field(default_factory=dict)
    telemetry_b: dict[str, DetectorTelemetry] = field(default_factory=dict)


class AnalysisService:
    def __init__(
        self,
        paths: LabPaths | None = None,
        history: HistoryStore | None = None,
        feature_extractor: FeatureExtractor = extract_audio_features,
        detector_runner: DetectorRunner = run_selected,
        timeline_runner: TimelineRunner = run_lofcz_timeline,
        layer_runner: LayerRunner = run_lofcz,
        artifact_measurer: ArtifactMeasurer = measure_artifacts,
    ) -> None:
        self.paths = paths or default_paths()
        self.history = history or HistoryStore(
            self.paths.history_db,
            self.paths.runs_dir,
        )
        self.feature_extractor = feature_extractor
        self.detector_runner = detector_runner
        self.timeline_runner = timeline_runner
        self.layer_runner = layer_runner
        self.artifact_measurer = artifact_measurer

    def analyze(
        self,
        audio_path: str | None,
        selected_detectors: list[str] | None,
        note: str,
        progress: ProgressCallback | None = None,
        t: Translator | None = None,
    ) -> AnalysisOutcome:
        translate = t or get_translator()
        if not audio_path:
            raise ValueError(translate("error.no_audio"))
        selected = list(selected_detectors or [])
        if not selected:
            raise ValueError(translate("error.no_detector"))

        source = Path(audio_path).resolve()
        if source.suffix.lower() not in {".wav", ".flac", ".mp3"}:
            raise ValueError(translate("error.unsupported_format"))
        if not source.is_file():
            raise ValueError(translate("error.audio_missing", path=source))

        if progress:
            progress(translate("progress.features"), 0.02)
        features = self.feature_extractor(source)
        detector_results = self.detector_runner(
            source,
            selected,
            self.paths,
            progress,
        )
        telemetry: dict[str, DetectorTelemetry] = {}
        results: list[DetectorResult] = []
        for result in detector_results:
            raw = dict(result.raw)
            transient = raw.pop("telemetry", None)
            if transient is not None:
                try:
                    item = validate_telemetry(transient)
                    telemetry[item.detector] = item
                except (TypeError, ValueError):
                    pass
            results.append(replace(result, raw=raw))
        if progress:
            progress(translate("progress.saving"), 0.96)
        run = self.history.save_run(source, features, results, note)
        if telemetry:
            self.history.save_telemetry(run.run_id, telemetry)

        if progress:
            progress(translate("progress.done"), 1.0)
        return AnalysisOutcome(
            run=run,
            features=features,
            telemetry=telemetry,
        )

    def sweep_layers(
        self,
        audio_paths: list[str] | None,
        progress: ProgressCallback | None = None,
        t: Translator | None = None,
    ) -> list[LayerResult]:
        """Rank separate stems by how strongly each carries the fakeprint.

        Deliberately ephemeral: a sweep is a diagnostic over pre-mix layers, not
        a versioned measurement, and writing one run per stem would bury the
        history. Only lofcz is used — FST needs beats and most stems have none.
        """
        translate = t or get_translator()
        paths = [Path(item).resolve() for item in (audio_paths or []) if item]
        if not paths:
            raise ValueError(translate("error.no_layers"))

        results: list[LayerResult] = []
        total = len(paths)
        for index, source in enumerate(paths):
            if progress:
                progress(
                    translate(
                        "progress.layer",
                        index=index + 1,
                        total=total,
                        name=source.name,
                    ),
                    index / total,
                )
            if source.suffix.lower() not in {".wav", ".flac", ".mp3"}:
                results.append(
                    LayerResult(
                        name=source.name,
                        status="error",
                        probability=None,
                        mean_residue_db=None,
                        duration_seconds=None,
                        error=translate("error.unsupported_format"),
                    )
                )
                continue
            outcome = self.layer_runner(source, self.paths)
            telemetry = outcome.raw.get("telemetry") or {}
            scalars = telemetry.get("scalars", {}) if isinstance(telemetry, dict) else {}
            arrays = telemetry.get("arrays", {}) if isinstance(telemetry, dict) else {}
            residue = arrays.get("residue_db")
            results.append(
                LayerResult(
                    name=source.name,
                    status=outcome.status,
                    probability=outcome.probability,
                    mean_residue_db=(
                        float(sum(residue) / len(residue)) if residue else None
                    ),
                    duration_seconds=scalars.get("analyzed_duration_seconds"),
                    error=outcome.error,
                )
            )
        if progress:
            progress(translate("progress.layers_done"), 1.0)
        # Loudest fakeprint first: that is where production effort pays off.
        return sorted(
            results,
            key=lambda item: (item.probability is None, -(item.probability or 0.0)),
        )

    def measure_artifacts_batch(
        self,
        run_id: str | None,
        reference_paths: list[str] | None,
        progress: ProgressCallback | None = None,
        t: Translator | None = None,
    ) -> list[ArtifactMetrics]:
        """Measure the current version next to reference tracks, same method for all.

        These numbers are meaningless in isolation — the whole point is reading
        your track against references measured identically.
        """
        translate = t or get_translator()
        targets: list[Path] = []
        if run_id:
            run = self.history.get_run(run_id)
            if run.audio_path.is_file():
                targets.append(run.audio_path)
        targets.extend(
            Path(item).resolve() for item in (reference_paths or []) if item
        )
        if not targets:
            raise ValueError(translate("error.no_reference"))

        results: list[ArtifactMetrics] = []
        total = len(targets)
        for index, source in enumerate(targets):
            if progress:
                progress(
                    translate(
                        "progress.metrics",
                        index=index + 1,
                        total=total,
                        name=source.name,
                    ),
                    index / total,
                )
            results.append(self.artifact_measurer(source))
        if progress:
            progress(translate("progress.metrics_done"), 1.0)
        return results

    def build_timeline(
        self,
        run_id: str | None,
        window_seconds: float = 15.0,
        hop_seconds: float = 5.0,
        t: Translator | None = None,
    ) -> DetectorTelemetry:
        """Scan a saved run with a sliding window and store the map as telemetry."""
        translate = t or get_translator()
        if not run_id:
            raise ValueError(translate("error.no_run"))
        run = self.history.get_run(run_id)
        if not run.audio_path.is_file():
            raise ValueError(
                translate("error.run_audio_missing", path=run.audio_path)
            )

        payload = self.timeline_runner(
            run.audio_path,
            self.paths,
            window_seconds=window_seconds,
            hop_seconds=hop_seconds,
        )
        telemetry = validate_telemetry(payload["telemetry"])
        self.history.save_telemetry(run.run_id, {telemetry.detector: telemetry})
        return telemetry

    def load_timeline(self, run_id: str | None) -> DetectorTelemetry | None:
        if not run_id:
            return None
        return self.history.load_telemetry(run_id).get("lofcz-timeline")

    def version_choices(self) -> list[tuple[str, str]]:
        choices = []
        for run in self.history.list_runs():
            timestamp = run.created_at[:19].replace("T", " ")
            prefix = "★ A · " if run.is_baseline else ""
            label = f"{prefix}{timestamp} · {run.filename}"
            choices.append((label, run.run_id))
        return choices

    def load_features(self, run_id: str) -> AudioFeatures:
        return self.history.load_features(run_id)

    def pin_version_a(self, run_id: str | None) -> AnalysisRun | None:
        if run_id is None:
            self.history.clear_baseline()
            return None
        self.history.set_baseline(run_id)
        return self.history.get_run(run_id)

    def default_version_pair(self) -> tuple[str | None, str | None]:
        runs = self.history.list_runs()
        if not runs:
            return None, None
        pinned = self.history.get_baseline()
        value_b = next(
            (run.run_id for run in runs if pinned is None or run.run_id != pinned.run_id),
            runs[0].run_id,
        )
        if pinned is not None:
            return pinned.run_id, value_b
        value_a = runs[1].run_id if len(runs) > 1 else None
        return value_a, runs[0].run_id

    def compare_runs(
        self,
        run_a_id: str,
        run_b_id: str,
        t: Translator | None = None,
    ) -> RunComparisonOutcome:
        translate = t or get_translator()
        if run_a_id == run_b_id:
            raise ValueError(translate("error.same_version"))

        run_a = self.history.get_run(run_a_id)
        run_b = self.history.get_run(run_b_id)
        features_a = self.history.load_features(run_a_id)
        features_b = self.history.load_features(run_b_id)
        comparison = None
        comparison_note = None
        try:
            comparison = compare_features(features_b, features_a)
        except ValueError as error:
            comparison_note = str(error)

        return RunComparisonOutcome(
            run_a=run_a,
            run_b=run_b,
            features_a=features_a,
            features_b=features_b,
            comparison=comparison,
            comparison_note=comparison_note,
            telemetry_a=self.history.load_telemetry(run_a_id),
            telemetry_b=self.history.load_telemetry(run_b_id),
        )
