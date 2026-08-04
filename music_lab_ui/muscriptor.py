"""Drives ``adapters/muscriptor_cli.py`` in its own conda environment.

The detector runners in :mod:`music_lab_ui.detectors` use ``subprocess.run``
with a wall-clock timeout, which is right for a call that takes seconds and
prints nothing until it is done. It is wrong here: the transcription weights are
gigabytes, and a fixed deadline would kill a healthy download on a slow link
while a stalled one sits there until the same deadline anyway.

So the child is read line by line, and the deadline is *idle* time — no output
for N seconds means the connection died, which is the failure that actually
happens.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Final

from .config import LabPaths

Popener = Callable[..., "subprocess.Popen[str]"]

#: muscriptor's own instrument vocabulary, in its own order — read from
#: `muscriptor.tokenizer.mt3.MT3_FULL_PLUS_GROUP_NAMES` at 0.2.2 (e2bd0fc).
#: Duplicated here rather than imported because this module runs in the UI
#: environment, which has no muscriptor. An upstream release could add names;
#: `--mode probe` reports the live list so a mismatch is discoverable.
#: Left untranslated on purpose: these are the exact strings the adapter
#: receives and the exact track names that come back in the MIDI.
INSTRUMENTS: Final[tuple[str, ...]] = (
    "acoustic_piano",
    "electric_piano",
    "chromatic_percussion",
    "organ",
    "acoustic_guitar",
    "clean_electric_guitar",
    "distorted_electric_guitar",
    "acoustic_bass",
    "electric_bass",
    "violin",
    "viola",
    "cello",
    "contrabass",
    "orchestral_harp",
    "timpani",
    "string_ensemble",
    "synth_strings",
    "voice",
    "orchestra_hit",
    "trumpet",
    "trombone",
    "tuba",
    "french_horn",
    "brass_section",
    "soprano_and_alto_sax",
    "tenor_sax",
    "baritone_sax",
    "oboe",
    "english_horn",
    "bassoon",
    "clarinet",
    "flutes",
    "synth_lead",
    "synth_pad",
    "drums",
)


def instrument_choices() -> list[tuple[str, str]]:
    """`(label, value)` pairs — underscores are a wire format, not a label."""
    return [(name.replace("_", " "), name) for name in INSTRUMENTS]


#: No output for this long means the child is stuck, not slow.
IDLE_TIMEOUT_SECONDS: Final[float] = 300.0
#: Transcription is bounded work, so it also gets an absolute ceiling.
TRANSCRIBE_TIMEOUT_SECONDS: Final[float] = 1800.0
PROBE_TIMEOUT_SECONDS: Final[float] = 120.0


@dataclass(frozen=True)
class StreamEvent:
    kind: str  # "progress" | "result" | "error" | "log"
    message: str = ""
    fraction: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    code: str = ""


def build_env(
    paths: LabPaths,
    token: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """The child's environment — and the only channel the token travels on.

    ``HF_HOME`` moves gigabytes of weights off the system drive and next to the
    detector models. The two encoding variables are the same ones
    ``start_ui.ps1`` sets for the parent: a child that inherits a scrubbed
    environment would print mojibake on the first non-ASCII path.
    """
    source = dict(os.environ if environ is None else environ)
    child = {
        **source,
        "HF_HOME": str(paths.muscriptor_cache),
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }
    stripped = token.strip()
    if stripped:
        child["HF_TOKEN"] = stripped
    else:
        # An empty variable is not the same as an absent one: huggingface_hub
        # would try to authenticate with it and fail confusingly.
        child.pop("HF_TOKEN", None)
    return child


def _adapter_argv(paths: LabPaths, *arguments: str) -> list[str]:
    return [str(paths.muscriptor_python), str(paths.muscriptor_adapter), *arguments]


def missing_requirements(paths: LabPaths) -> list[str]:
    """Everything that has to exist before the adapter can even be started."""
    required = (paths.muscriptor_python, paths.muscriptor_adapter)
    return [str(path) for path in required if not path.is_file()]


def parse_line(line: str) -> StreamEvent:
    """NDJSON if it parses, a log line if it does not.

    A stray print from a dependency must not look like a protocol violation.
    """
    stripped = line.strip()
    if not stripped:
        return StreamEvent(kind="log")
    try:
        payload = json.loads(stripped)
    except ValueError:
        return StreamEvent(kind="log", message=stripped)
    if not isinstance(payload, dict) or "event" not in payload:
        return StreamEvent(kind="log", message=stripped)
    kind = str(payload["event"])
    fraction = payload.get("fraction")
    return StreamEvent(
        kind=kind,
        message=str(payload.get("message", "")),
        fraction=float(fraction) if isinstance(fraction, (int, float)) else None,
        payload=payload.get("payload") or payload,
        code=str(payload.get("code", "")),
    )


def stream_adapter(
    argv: list[str],
    paths: LabPaths,
    token: str,
    *,
    popener: Popener = subprocess.Popen,
    idle_timeout: float = IDLE_TIMEOUT_SECONDS,
    total_timeout: float | None = None,
    environ: Mapping[str, str] | None = None,
) -> Iterator[StreamEvent]:
    """Yield the child's events as they arrive; raise on a failed run."""
    missing = missing_requirements(paths)
    if missing:
        raise RuntimeError("missing files: " + ", ".join(missing))

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    process = popener(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(paths.root),
        env=build_env(paths, token, environ),
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creation_flags,
    )

    lines: Queue[str | None] = Queue()

    def pump() -> None:
        try:
            for line in process.stdout or ():
                lines.put(line)
        finally:
            lines.put(None)

    reader = threading.Thread(target=pump, name="muscriptor-stdout", daemon=True)
    reader.start()

    started = time.monotonic()
    failure: str | None = None
    try:
        while True:
            try:
                line = lines.get(timeout=idle_timeout)
            except Empty:
                process.kill()
                raise AdapterError(
                    "stalled",
                    f"no output from the adapter for {idle_timeout:.0f} s",
                ) from None
            if line is None:
                break
            if total_timeout is not None and time.monotonic() - started > total_timeout:
                process.kill()
                raise AdapterError(
                    "timeout",
                    f"the adapter ran past {total_timeout:.0f} s",
                )
            event = parse_line(line)
            if event.kind == "error":
                failure = event.code or "failed"
            if event.kind != "log" or event.message:
                yield event
        process.wait(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()

    if process.returncode not in (0, None):
        stderr = (process.stderr.read() if process.stderr else "") or ""
        raise AdapterError(failure or "failed", stderr.strip()[-2000:])


class AdapterError(RuntimeError):
    """A failure the adapter classified, so the interface can translate it."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


def probe(
    paths: LabPaths,
    token: str = "",
    *,
    runner: Callable[..., "subprocess.CompletedProcess[str]"] = subprocess.run,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """A quick "is the environment real" call — fast enough for plain ``run``."""
    missing = missing_requirements(paths)
    if missing:
        raise AdapterError("package_missing", "missing files: " + ", ".join(missing))
    with _temporary_json(paths) as destination:
        completed = runner(
            _adapter_argv(
                paths,
                "--mode",
                "probe",
                "--upstream",
                str(paths.muscriptor_upstream),
                "--json-output",
                str(destination),
            ),
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            check=False,
            cwd=str(paths.root),
            env=build_env(paths, token, environ),
        )
        if completed.returncode != 0:
            raise AdapterError(
                "package_missing",
                (completed.stderr or completed.stdout).strip()[-2000:],
            )
        for line in completed.stdout.splitlines():
            event = parse_line(line)
            if event.kind == "result":
                return event.payload
    raise AdapterError("failed", "the probe produced no result")


def download_weights(
    paths: LabPaths,
    token: str,
    size: str,
    **kwargs: Any,
) -> Iterator[StreamEvent]:
    return stream_adapter(
        _adapter_argv(paths, "--mode", "download", "--model", size,
                      "--json-output", str(_json_path(paths, f"download-{size}"))),
        paths,
        token,
        **kwargs,
    )


def transcribe(
    paths: LabPaths,
    token: str,
    audio: Path,
    midi_output: Path,
    *,
    size: str,
    device: str = "cuda",
    instruments: str = "",
    beam_size: int = 1,
    **kwargs: Any,
) -> Iterator[StreamEvent]:
    arguments = [
        "--mode", "transcribe",
        "--model", size,
        "--device", device,
        "--beam-size", str(beam_size),
        "--audio", str(audio),
        "--midi-output", str(midi_output),
        "--json-output", str(midi_output.with_suffix(".json")),
    ]
    if instruments.strip():
        arguments += ["--instruments", instruments.strip()]
    kwargs.setdefault("total_timeout", TRANSCRIBE_TIMEOUT_SECONDS)
    return stream_adapter(_adapter_argv(paths, *arguments), paths, token, **kwargs)


def _json_path(paths: LabPaths, name: str) -> Path:
    destination = paths.root / "artifacts" / f"muscriptor-{name}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


@contextlib.contextmanager
def _temporary_json(paths: LabPaths) -> Iterator[Path]:
    """A probe's JSON file is read from stdout anyway; nothing should persist."""
    with tempfile.TemporaryDirectory(prefix="ai-music-muscriptor-") as directory:
        yield Path(directory) / "probe.json"
