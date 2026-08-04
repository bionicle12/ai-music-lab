from __future__ import annotations

import datetime as dt
import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

from . import muscriptor as muscriptor_runner
from . import provisioning
from . import readiness as readiness_module
from . import repositories
from .artifact_metrics import ArtifactMetrics, measure_artifacts
from .audio_features import extract_audio_features, extract_preview_features
from .comparison import FeatureComparison, compare_features
from .config import LabPaths, default_paths
from .contracts import AnalysisRun, AudioFeatures, DetectorResult, LayerResult
from .detectors import ProgressCallback, run_lofcz, run_lofcz_timeline, run_selected
from .history import HistoryStore
from .i18n import Translator, get_translator
from .settings import LabSettings, SettingsStore, resolve_token
from .telemetry import DetectorTelemetry, validate_telemetry

SUPPORTED_SUFFIXES = frozenset({".wav", ".flac", ".mp3"})

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
    #: The per-detector settings this run was produced with. Saved alongside
    #: the results, because a score is only comparable with another one when
    #: you can see that both were measured the same way.
    settings: dict[str, Any] = field(default_factory=dict)


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
        preview_extractor: FeatureExtractor = extract_preview_features,
        detector_runner: DetectorRunner = run_selected,
        timeline_runner: TimelineRunner = run_lofcz_timeline,
        layer_runner: LayerRunner = run_lofcz,
        artifact_measurer: ArtifactMeasurer = measure_artifacts,
        settings_store: SettingsStore | None = None,
        midi_runner: Callable[..., Iterator[Any]] = muscriptor_runner.transcribe,
        weights_runner: Callable[..., Iterator[Any]] = (
            muscriptor_runner.download_weights
        ),
        probe_runner: Callable[..., dict[str, Any]] = muscriptor_runner.probe,
        repository_reader: Callable[..., tuple] = repositories.all_statuses,
    ) -> None:
        self.paths = paths or default_paths()
        self.history = history or HistoryStore(
            self.paths.history_db,
            self.paths.runs_dir,
        )
        self.feature_extractor = feature_extractor
        self.preview_extractor = preview_extractor
        self.detector_runner = detector_runner
        self.timeline_runner = timeline_runner
        self.layer_runner = layer_runner
        self.artifact_measurer = artifact_measurer
        self.settings_store = settings_store or SettingsStore(self.paths.settings_path)
        self.midi_runner = midi_runner
        self.weights_runner = weights_runner
        self.probe_runner = probe_runner
        self.repository_reader = repository_reader

    def _audio_source(self, audio_path: str, translate: Translator) -> Path:
        source = Path(audio_path).resolve()
        if source.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(translate("error.unsupported_format"))
        if not source.is_file():
            raise ValueError(translate("error.audio_missing", path=source))
        return source

    def preview(
        self,
        audio_path: str | None,
        t: Translator | None = None,
    ) -> AudioFeatures | None:
        """Read a dropped file well enough to draw it, before anything is run.

        The sidebar's whole-track strip is the counterpart to the player above
        it, and a player with nothing beside it reads as a broken page rather
        than as one waiting for a button. This fills both from the same cheap
        pass; the analysis run recomputes properly and overwrites.
        """
        if not audio_path:
            return None
        return self.preview_extractor(self._audio_source(audio_path, t or get_translator()))

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

        source = self._audio_source(audio_path, translate)

        if progress:
            progress(translate("progress.features"), 0.02)
        features = self.feature_extractor(source)
        options = self.detector_options()
        detector_results = self.detector_runner(
            source,
            selected,
            self.paths,
            progress,
            options=options,
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
        run = self.history.save_run(source, features, results, note, settings=options)
        if telemetry:
            self.history.save_telemetry(run.run_id, telemetry)

        if progress:
            progress(translate("progress.done"), 1.0)
        return AnalysisOutcome(
            run=run,
            features=features,
            telemetry=telemetry,
            settings=options,
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
                        path=str(source),
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
                    path=str(source),
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

    # ---- settings, upstreams and MIDI transcription ----------------------

    def settings(self) -> LabSettings:
        return self.settings_store.load()

    def save_settings(self, settings: LabSettings) -> LabSettings:
        return self.settings_store.save(settings)

    def readiness(self, *, probe: bool = False) -> readiness_module.ReadinessReport:
        """Probing spawns a process, so it is opt-in and never happens on render."""
        settings = self.settings()
        token, _ = resolve_token(settings)
        runner = None
        if probe:
            runner = lambda: self.probe_runner(self.paths, token)  # noqa: E731
        return readiness_module.evaluate(self.paths, settings, probe=runner)

    def detector_options(self) -> dict[str, Any]:
        """The settings a detector run is allowed to see.

        Named explicitly rather than handing over ``LabSettings``: that object
        also holds the Hugging Face token, and nothing that runs a detector has
        any business being able to read it.
        """
        settings = self.settings()
        return {"fst_backbone_batch": settings.fst_backbone_batch}

    def conda_executable(self) -> str | None:
        """Conda is a precondition, not something this app installs."""
        return provisioning.conda_executable()

    def detector_downloads(self, detector: str) -> list[tuple[Any, Path, bool]]:
        """``(download, destination, present_and_verified)`` for one detector."""
        catalogue = provisioning.load_downloads(self.paths.root)
        rows = []
        for key in provisioning.WEIGHT_KEYS.get(detector, ()):
            item = catalogue[key]
            destination = getattr(
                self.paths, provisioning.WEIGHT_DESTINATIONS[key]
            )
            rows.append((item, destination, provisioning.verify(destination, item)))
        return rows

    def provision_detector(self, detector: str) -> Iterator[str]:
        """Do whatever is still missing, in order, narrating as it goes.

        A generator rather than a function that returns a log: `conda create`
        takes minutes, and an interface that shows nothing until it finishes is
        indistinguishable from one that has hung.

        Every step is skipped when its work is already done, so this is safe to
        press again after fixing one thing by hand — which is the whole point,
        because the step most likely to fail is the one this cannot retry
        usefully.
        """
        spec = readiness_module.DETECTOR_REQUIREMENTS_BY_KEY.get(detector)
        if spec is None:
            raise provisioning.ProvisioningError("unknown", detector)

        repo = repositories.REPOSITORIES_BY_KEY[spec.repo_key]
        report = self.detector_readiness(detector)
        state = {item.key: item.ok for item in report.items}

        if not state.get("clone"):
            provisioning.check_clone_target(repo, self.paths)
            command = provisioning.clone_command(repo, self.paths)
            yield f"$ {subprocess.list2cmdline(command)}"
            yield from provisioning.stream_command(command, cwd=self.paths.root)

        if not state.get("env"):
            conda = self.conda_executable()
            if conda is None:
                raise provisioning.ProvisioningError("no_conda", "")
            for command in provisioning.environment_commands(
                detector, self.paths, conda
            ):
                yield f"$ {subprocess.list2cmdline(command)}"
                yield from provisioning.stream_command(command, cwd=self.paths.root)

        if not state.get("weights"):
            for item, destination, present in self.detector_downloads(detector):
                if present:
                    continue
                if not item.automatable:
                    # Google Drive has no stable direct URL for a file this
                    # size. Saying so is the honest outcome; pretending to try
                    # would fail in a way nobody could act on.
                    yield f"! {item.filename}: {item.url} -> {destination}"
                    continue
                yield f"$ download {item.filename}"
                yield from provisioning.download_weight(item, self.paths)

    def detector_readiness(self, detector: str) -> readiness_module.ReadinessReport:
        """Clone, environment, weights — for one detector, without running it."""
        return readiness_module.evaluate_detector(detector, self.paths)

    def detector_upstream(self, detector: str):
        """The clone's status, or ``None`` when git cannot describe it.

        ``fetch=False`` on purpose: this is drawn every time a settings dialog
        opens, and a network round-trip per open would make the dialog feel
        broken on a machine that is offline — which is most of them, by design.
        """
        spec = readiness_module.DETECTOR_REQUIREMENTS_BY_KEY.get(detector)
        if spec is None:
            return None
        repo = repositories.REPOSITORIES_BY_KEY[spec.repo_key]
        status = repositories.read_status(repo, self.paths, fetch=False)
        return status if status.present else None

    def repository_statuses(self, *, fetch: bool = True) -> tuple:
        return self.repository_reader(self.paths, fetch=fetch)

    def pull_repository(self, key: str) -> repositories.PullOutcome:
        repo = repositories.REPOSITORIES_BY_KEY.get(key)
        if repo is None:
            raise ValueError(f"unknown repository: {key}")
        return repositories.pull(repo, self.paths)

    def midi_destination(self, source: Path, now: dt.datetime | None = None) -> Path:
        """A stable place on disk, because a transcription is worth keeping.

        Gradio's own cache is wiped daily; a file the user is going to open in a
        DAW should not evaporate overnight.
        """
        stamp = (now or dt.datetime.now()).strftime("%Y%m%dT%H%M%S")
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip("-") or "stem"
        return self.paths.midi_dir / f"{stamp}-{safe}.mid"

    def download_weights(self, size: str) -> Iterator[Any]:
        token, _ = resolve_token(self.settings())
        return self.weights_runner(self.paths, token, size)

    def transcribe_to_midi(
        self,
        audio_path: str | Path | None,
        *,
        size: str | None = None,
        instruments: str | list[str] = "",
        device: str | None = None,
        t: Translator | None = None,
    ) -> tuple[Path, Iterator[Any]]:
        """Return the destination and the event stream; the caller drains it."""
        translate = t or get_translator()
        if not audio_path:
            raise ValueError(translate("error.no_midi_source"))
        source = Path(audio_path).resolve()
        if source.suffix.lower() not in {".wav", ".flac", ".mp3"}:
            raise ValueError(translate("error.unsupported_format"))
        if not source.is_file():
            raise ValueError(translate("error.audio_missing", path=source))

        settings = self.settings()
        token, _ = resolve_token(settings)
        destination = self.midi_destination(source)
        stream = self.midi_runner(
            self.paths,
            token,
            source,
            destination,
            size=size or settings.muscriptor_model,
            device=device or settings.midi_device,
            instruments=(
                ", ".join(instruments)
                if isinstance(instruments, list)
                else instruments
            ),
        )
        return destination, stream

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
