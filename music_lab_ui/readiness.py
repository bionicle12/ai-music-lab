"""Is MIDI transcription actually set up, and if not, what is missing.

A single boolean would be useless here: six separate things have to line up, and
the only helpful answer to "the button is greyed out" is which one is not. So
this is always a checklist, and the first failing item carries the sentence that
says what to do about it.

Order matters. Cheap local stats come first, so a missing clone is reported as a
missing clone rather than as whatever confusing failure a subprocess produces
when it cannot start.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .config import LabPaths
from .repositories import REPOSITORIES_BY_KEY
from .settings import LabSettings, resolve_token, token_fingerprint

Probe = Callable[[], dict[str, Any]]
Exists = Callable[[Path], bool]

ITEM_KEYS: Final[tuple[str, ...]] = (
    "clone",
    "env",
    "license",
    "token",
    "weights",
    "package",
)


@dataclass(frozen=True)
class ReadinessItem:
    key: str
    #: ``None`` means "not checked yet", which is neither pass nor fail.
    ok: bool | None
    #: Already safe to display: this never contains the token itself.
    detail: str = ""


@dataclass(frozen=True)
class ReadinessReport:
    items: tuple[ReadinessItem, ...]
    ready: bool
    probed: bool

    def first_problem(self) -> ReadinessItem | None:
        return next((item for item in self.items if item.ok is not True), None)


def evaluate(
    paths: LabPaths,
    settings: LabSettings,
    environ: Mapping[str, str] | None = None,
    *,
    exists: Exists = Path.is_file,
    probe: Probe | None = None,
) -> ReadinessReport:
    """Build the checklist.

    ``probe`` is optional on purpose. It spawns a process, and this function is
    called on every render — including while ``build_app`` is still assembling
    the interface, where a subprocess would be both slow and surprising. Pass it
    only from an explicit "check" action.
    """
    repo = REPOSITORIES_BY_KEY["muscriptor"]
    missing_files = [
        name
        for name in repo.required_files
        if not exists(paths.muscriptor_upstream / name)
    ]
    clone_ok = not missing_files
    env_ok = exists(paths.muscriptor_python)

    token, source = resolve_token(settings, environ)
    token_detail = ""
    if source == "env":
        token_detail = "HF_TOKEN"
    elif source == "settings":
        token_detail = token_fingerprint(token)

    size = settings.muscriptor_model
    recorded = settings.muscriptor_weights.get(size, "")
    weights_ok = bool(recorded) and exists(Path(recorded))

    probe_ok: bool | None = None
    probe_detail = ""
    if probe is not None:
        try:
            payload = probe()
        except Exception as error:  # noqa: BLE001 - a failed probe is a checklist row
            probe_ok = False
            probe_detail = str(error)[:300]
        else:
            probe_ok = True
            probe_detail = payload.get("muscriptor_version", "")
            if payload.get("inside_clone") is False:
                # The package resolved outside the clone, so `git pull` on the
                # clone would change nothing that actually runs.
                probe_ok = False
                probe_detail = payload.get("muscriptor_file", "")

    items = (
        ReadinessItem("clone", clone_ok, ", ".join(missing_files)),
        ReadinessItem("env", env_ok, str(paths.muscriptor_python)),
        ReadinessItem("license", settings.weights_license_accepted),
        ReadinessItem("token", source != "none", token_detail),
        ReadinessItem("weights", weights_ok, size),
        ReadinessItem("package", probe_ok, probe_detail),
    )
    return ReadinessReport(
        items=items,
        ready=all(item.ok is True for item in items),
        probed=probe is not None,
    )


def can_transcribe(report: ReadinessReport) -> bool:
    """Enough to let the user press the button.

    The package probe is deliberately excluded: it costs a subprocess, and a
    broken environment fails loudly on the first real run anyway. Refusing to
    let someone try until they have clicked "check" would be worse.
    """
    required = {"clone", "env", "license", "token", "weights"}
    return all(item.ok is True for item in report.items if item.key in required)
