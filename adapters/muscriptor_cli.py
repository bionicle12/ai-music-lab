"""External CLI for muscriptor, run under the ai-music-muscriptor environment.

Deliberately unlike the detector adapters in one respect: there is no
``upstream_import_context`` here. lofcz and FST are loose script trees that have
to be put on ``sys.path``; muscriptor is a pip-installed package, so ``import
muscriptor`` simply works. ``--upstream`` survives only as an assertion — probe
mode reports where the package actually resolved, and the interface warns when
that is not the clone, because then ``git pull`` on the clone changes nothing.

Everything else follows the house pattern: heavy imports live inside functions
so the pure helpers stay importable (and testable) from the UI environment,
``build_parser`` describes the surface, and ``main`` writes a JSON result file.

Progress is written to stdout as NDJSON, one object per line. Human-readable
logging goes to stderr, so stdout stays a clean machine stream.

There is no ``--token`` argument on purpose. The Hugging Face token arrives only
through the ``HF_TOKEN`` environment variable: a command-line argument would be
visible to anything that can list processes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterator

MODEL_SIZES = ("small", "medium", "large")
WEIGHTS_FILENAME = "model.safetensors"
CONFIG_FILENAME = "config.json"

#: How often the download poller reports, in seconds. Fast enough to look live,
#: slow enough that the pipe never becomes the bottleneck.
PROGRESS_INTERVAL_SECONDS = 0.5


def repo_id(size: str) -> str:
    if size not in MODEL_SIZES:
        raise ValueError(f"unknown model size: {size}")
    return f"MuScriptor/muscriptor-{size}"


def weights_url(size: str) -> str:
    return f"hf://{repo_id(size)}/{WEIGHTS_FILENAME}"


def parse_instruments(text: str | None) -> list[str] | None:
    """``"drums, acoustic_piano"`` -> ``["drums", "acoustic_piano"]``; blank -> None."""
    if not text:
        return None
    names = [item.strip() for item in text.split(",")]
    kept = [name for name in names if name]
    return kept or None


def classify_http_error(status: int | None, message: str) -> str:
    """Map a Hugging Face failure onto a stable code the interface can translate.

    Kept pure and free of ``huggingface_hub`` imports so the UI environment can
    test it. Wording lives in the catalogue, never here: this file runs in a
    different environment and knows nothing about the translator.
    """
    lowered = message.lower()
    if status == 401:
        return "token_missing"
    if status == 403:
        if "gated" in lowered or "awaiting" in lowered or "access" in lowered:
            return "gated_repo"
        return "token_scope"
    if status == 404:
        return "repo_missing"
    if any(word in lowered for word in ("offline", "connection", "resolve host")):
        return "offline"
    return "http_error"


def classify_error(error: BaseException) -> str:
    """Classify any adapter failure, network or local."""
    message = str(error)
    lowered = message.lower()
    name = type(error).__name__
    if name in {"GatedRepoError", "ModelDownloadError"} or "gated" in lowered:
        return "gated_repo"
    if name == "RepositoryNotFoundError":
        return "repo_missing"
    if "out of memory" in lowered or name == "OutOfMemoryError":
        return "cuda_oom"
    if isinstance(error, ModuleNotFoundError):
        return "package_missing"
    if isinstance(error, FileNotFoundError):
        return "file_missing"
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status is not None or "http" in lowered:
        return classify_http_error(status, message)
    return "failed"


def emit(event: str, **fields: Any) -> None:
    """One NDJSON object per line on stdout, flushed so the parent sees it live."""
    sys.stdout.write(json.dumps({"event": event, **fields}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def directory_bytes(path: Path) -> int:
    """Total size below ``path``, partial downloads included. Missing dir -> 0."""
    total = 0
    if not path.is_dir():
        return 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            # A file being written can vanish between listing and stat; a
            # progress reading is not worth failing a download over.
            continue
    return total


def package_version() -> str:
    """muscriptor exposes no ``__version__``; the installed distribution does."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("muscriptor")
    except PackageNotFoundError:
        return "unknown"


def cache_root() -> Path:
    """Where huggingface_hub is putting things for this process."""
    from huggingface_hub import constants

    return Path(constants.HF_HUB_CACHE)


def repo_cache_dir(size: str) -> Path:
    return cache_root() / f"models--MuScriptor--muscriptor-{size}"


def expected_bytes(size: str) -> int | None:
    """Total download size, or None when the metadata call fails.

    Only used to turn byte counts into a fraction. A failure here degrades the
    progress bar to indeterminate; it must never fail the download itself.
    """
    try:
        from huggingface_hub import HfApi

        info = HfApi().model_info(repo_id(size), files_metadata=True)
    except Exception:  # noqa: BLE001 - progress is advisory, never fatal
        return None
    wanted = {WEIGHTS_FILENAME, CONFIG_FILENAME}
    sizes = [
        sibling.size
        for sibling in (info.siblings or [])
        if sibling.rfilename in wanted and sibling.size
    ]
    return sum(sizes) or None


def _watch_download(size: str, stop: threading.Event, total: int | None) -> None:
    """Report cache growth while another thread downloads.

    Polling the cache directory rather than hooking huggingface_hub's progress
    bars: the hook API has moved between versions, the directory has not.
    """
    directory = repo_cache_dir(size)
    baseline = directory_bytes(directory)
    while not stop.wait(PROGRESS_INTERVAL_SECONDS):
        current = directory_bytes(directory) - baseline
        fraction = None
        if total:
            fraction = max(0.0, min(1.0, current / total))
        emit(
            "progress",
            stage="download",
            fraction=fraction,
            bytes=current,
            total=total,
            message=f"{repo_id(size)}",
        )


def run_probe(upstream: Path | None) -> dict[str, Any]:
    import muscriptor
    import torch

    package = Path(muscriptor.__file__).resolve()
    inside_clone = False
    if upstream is not None:
        try:
            package.relative_to(upstream.resolve())
            inside_clone = True
        except ValueError:
            inside_clone = False
    return {
        "mode": "probe",
        "muscriptor_version": package_version(),
        "muscriptor_file": str(package),
        "inside_clone": inside_clone,
        "torch_version": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "device_name": (
            torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
        ),
        "python": sys.version.split()[0],
        "hf_home": os.environ.get("HF_HOME", ""),
        "hf_cache": str(cache_root()),
    }


def run_download(size: str) -> dict[str, Any]:
    """Fetch the weights, then prove the cache resolves them without a network.

    The second half matters: a checkbox that goes green because a file exists,
    while transcription still fails on a gated repo, is worse than no checkbox.
    """
    from muscriptor.utils.download import download_companion, download_if_necessary

    url = weights_url(size)
    total = expected_bytes(size)
    emit("progress", stage="download", fraction=0.0, bytes=0, total=total,
         message=repo_id(size))

    result: dict[str, Any] = {}
    error: list[BaseException] = []

    def work() -> None:
        try:
            result["weights"] = Path(download_if_necessary(url))
            result["config"] = download_companion(url, CONFIG_FILENAME)
        except BaseException as caught:  # noqa: BLE001 - re-raised on the main thread
            error.append(caught)

    stop = threading.Event()
    worker = threading.Thread(target=work, name="muscriptor-download", daemon=True)
    watcher = threading.Thread(
        target=_watch_download, args=(size, stop, total), daemon=True
    )
    worker.start()
    watcher.start()
    worker.join()
    stop.set()
    watcher.join(timeout=2.0)
    if error:
        raise error[0]

    weights = result["weights"]
    emit("progress", stage="verify", fraction=1.0, message="offline reload")
    previous = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        verified = Path(download_if_necessary(url))
    finally:
        if previous is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = previous

    return {
        "mode": "download",
        "model": size,
        "repo_id": repo_id(size),
        "weights_path": str(verified),
        "config_path": str(result["config"]) if result.get("config") else "",
        "bytes": verified.stat().st_size if verified.is_file() else 0,
        "verified_offline": True,
    }


def _with_progress(events: Iterator[Any]) -> Iterator[Any]:
    """Pass the event stream through, reporting muscriptor's own chunk anchors."""
    from muscriptor.events import ProgressEvent

    for event in events:
        if isinstance(event, ProgressEvent) and event.total:
            emit(
                "progress",
                stage="transcribe",
                fraction=min(1.0, event.completed / event.total),
                message=f"{event.completed}/{event.total}",
            )
        yield event


def run_transcribe(
    size: str,
    audio: Path,
    midi_output: Path,
    device: str,
    instruments: list[str] | None,
    beam_size: int,
) -> dict[str, Any]:
    import time as _time

    import torch
    from muscriptor import TranscriptionModel

    if not audio.is_file():
        raise FileNotFoundError(f"audio file not found: {audio}")
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"
        log("CUDA is unavailable; falling back to CPU")

    started = _time.perf_counter()
    emit("progress", stage="load", fraction=0.0, message=f"loading {size}")
    model = TranscriptionModel.load_model(size, device=device)
    emit("progress", stage="load", fraction=1.0, message=f"loaded {size}")

    # transcribe_to_midi() is the same three calls, but folding the stream by
    # hand is what lets chunk progress reach the interface.
    beat_grid = model.detect_beat_grid_for(str(audio))
    events = _with_progress(
        model.transcribe(
            str(audio),
            instruments=instruments,
            beam_size=beam_size,
            use_sampling=False,
        )
    )
    midi_bytes = model.events_to_midi_bytes(events, beat_grid=beat_grid)
    midi_output.parent.mkdir(parents=True, exist_ok=True)
    midi_output.write_bytes(midi_bytes)

    return {
        "mode": "transcribe",
        "model": size,
        "repo_id": repo_id(size),
        "audio": str(audio.resolve()),
        "midi_path": str(midi_output.resolve()),
        "midi_bytes": len(midi_bytes),
        "instruments": instruments or [],
        "beam_size": beam_size,
        "use_sampling": False,
        "device": device,
        "tempo_detected": beat_grid is not None,
        "runtime_seconds": round(_time.perf_counter() - started, 2),
        "muscriptor_version": package_version(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="External CLI for muscriptor")
    parser.add_argument("--mode", choices=("probe", "download", "transcribe"),
                        required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--upstream", type=Path)
    parser.add_argument("--model", choices=MODEL_SIZES, default="large")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--midi-output", type=Path)
    parser.add_argument("--instruments")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--beam-size", type=int, default=1)
    return parser


def validate(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.mode == "transcribe":
        if args.audio is None:
            parser.error("--audio is required in transcribe mode")
        if args.midi_output is None:
            parser.error("--midi-output is required in transcribe mode")


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.mode == "probe":
        return run_probe(args.upstream)
    if args.mode == "download":
        return run_download(args.model)
    return run_transcribe(
        args.model,
        args.audio,
        args.midi_output,
        args.device,
        parse_instruments(args.instruments),
        args.beam_size,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    validate(args, parser)
    started = time.perf_counter()
    try:
        payload = dispatch(args)
    except BaseException as error:  # noqa: BLE001 - every failure becomes a code
        code = classify_error(error)
        emit("error", code=code, detail=str(error)[:500])
        log(f"{type(error).__name__}: {error}")
        return 1
    payload["elapsed_seconds"] = round(time.perf_counter() - started, 2)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    emit("result", payload=payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
