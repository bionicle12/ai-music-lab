"""User-chosen settings, kept separate from :mod:`music_lab_ui.config`.

``LabPaths`` answers "where does the code expect things to be" and is derived
entirely from constants. This module answers "what did the user pick", which
lives in a file and changes at runtime. Merging the two would mean rebuilding
``LabPaths`` on every save and would break the ``LabPaths.from_root(tmp_path)``
idiom the test suite is built on.

The Hugging Face token is a credential. It reaches the interface only as a
fingerprint (:func:`token_fingerprint`) and reaches muscriptor only through the
``HF_TOKEN`` environment variable of the child process — never as a command-line
argument, never in the run history, never in the technical-data payload.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Final

#: Bumped when the stored shape changes. A file one or more versions behind is
#: migrated forward; only a file from the *future* falls back to defaults,
#: because guessing at a shape this build has never seen would lose data.
SETTINGS_VERSION: Final[int] = 2

MODEL_SIZES: Final[tuple[str, ...]] = ("small", "medium", "large")
DEFAULT_MODEL: Final[str] = "large"
DEVICES: Final[tuple[str, ...]] = ("cuda", "cpu")

#: Segments per FST backbone pass. ``0`` is upstream's own single pass over all
#: 48 and remains available for CUDA reproduction, but is rejected on MPS.
FST_BACKBONE_CHOICES: Final[tuple[int, ...]] = (1, 2, 4, 8, 0)
DEFAULT_FST_CUDA_BACKBONE_BATCH: Final[int] = 8
DEFAULT_FST_MPS_BACKBONE_BATCH: Final[int] = 2


def platform_default_fst_backbone_batch(
    platform_name: str | None = None,
) -> int:
    selected = sys.platform if platform_name is None else platform_name
    if selected == "darwin":
        return DEFAULT_FST_MPS_BACKBONE_BATCH
    return DEFAULT_FST_CUDA_BACKBONE_BATCH


#: Compatibility name used by existing UI and detector code.
DEFAULT_FST_BACKBONE_BATCH: Final[int] = platform_default_fst_backbone_batch()


@dataclass(frozen=True)
class LabSettings:
    """Frozen, like every other value object here; edit with ``dataclasses.replace``."""

    hf_token: str = ""
    muscriptor_model: str = DEFAULT_MODEL
    #: size -> resolved local path reported by a successful download. Recorded
    #: rather than derived: huggingface_hub owns the cache layout and is free to
    #: change it, so guessing at filenames would produce a readiness check that
    #: lies in both directions.
    muscriptor_weights: dict[str, str] = field(default_factory=dict)
    weights_license_accepted: bool = False
    midi_device: str = "cuda"
    #: How many of FST's 48 segments go through the backbone at once. Not a
    #: performance dial: it is the difference between 4.8 GB of VRAM and 16, and
    #: it can move the raw logit by one float16 ulp, so it is recorded per run.
    fst_backbone_batch: int = field(
        default_factory=platform_default_fst_backbone_batch
    )
    version: int = SETTINGS_VERSION

    def normalized(self) -> "LabSettings":
        """Clamp free-form fields so a hand-edited file cannot reach the UI."""
        model = (
            self.muscriptor_model
            if self.muscriptor_model in MODEL_SIZES
            else DEFAULT_MODEL
        )
        device = self.midi_device if self.midi_device in DEVICES else "cuda"
        weights = {
            str(size): str(path)
            for size, path in self.muscriptor_weights.items()
            if size in MODEL_SIZES
        }
        batch = (
            self.fst_backbone_batch
            if self.fst_backbone_batch in FST_BACKBONE_CHOICES
            else platform_default_fst_backbone_batch()
        )
        return replace(
            self,
            hf_token=self.hf_token.strip(),
            muscriptor_model=model,
            midi_device=device,
            muscriptor_weights=weights,
            fst_backbone_batch=batch,
            version=SETTINGS_VERSION,
        )


#: One entry per version step, keyed by the version it upgrades *from*. Each
#: takes a stored payload and returns the next version's shape.
#:
#: v1 -> v2 only added ``fst_backbone_batch``, and an absent field already
#: becomes its default, so the step has nothing to do. It exists anyway: the
#: chain is what makes the next bump safe, and an empty step is proof the
#: version was considered rather than forgotten.
_MIGRATIONS: Final[dict[int, Callable[[dict[str, Any]], dict[str, Any]]]] = {
    1: lambda payload: payload,
}


def migrate(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Bring a stored payload to the current version, or refuse to guess.

    Before this existed, a version bump sent :meth:`SettingsStore.load` straight
    to defaults — which reads as "your Hugging Face token vanished after an
    update", discovered a week later when a download fails. Old files are now
    carried forward field by field.

    ``None`` means the payload cannot be read: no version, or a version from a
    build newer than this one, whose shape is unknowable from here.
    """
    version = payload.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        return None
    if version < 1 or version > SETTINGS_VERSION:
        return None
    current = dict(payload)
    while version < SETTINGS_VERSION:
        step = _MIGRATIONS.get(version)
        if step is None:
            return None
        current = step(current)
        version += 1
    current["version"] = SETTINGS_VERSION
    return current


def token_fingerprint(token: str) -> str:
    """The only form of the token allowed to reach the interface.

    Enough to tell two tokens apart when checking which one is stored, never
    enough to use. A token short enough that four characters would give it away
    is not a real token, so it is masked completely.
    """
    stripped = token.strip()
    if not stripped:
        return ""
    if len(stripped) <= 8:
        return "…"
    return f"…{stripped[-4:]}"


def resolve_token(
    settings: LabSettings,
    environ: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Return ``(token, source)`` with ``source`` in ``env`` / ``settings`` / ``none``.

    The environment wins, mirroring how ``AI_MUSIC_*_PYTHON`` already overrides
    the path constants — and giving anyone who would rather not keep a
    credential in a plain file a way to avoid it entirely.
    """
    source = dict(os.environ if environ is None else environ)
    from_env = source.get("HF_TOKEN", "").strip()
    if from_env:
        return from_env, "env"
    stored = settings.hf_token.strip()
    if stored:
        return stored, "settings"
    return "", "none"


class SettingsStore:
    """Reads and writes one JSON file, and never lets it break the app.

    A settings file is the only piece of app state a user can hand-edit. If a
    broken one could raise out of ``load``, a stray comma would leave the
    interface unable to start with no way to fix it from inside the interface.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._load_error: str | None = None

    @property
    def load_error(self) -> str | None:
        """Set by the most recent :meth:`load`; shown in the panel, never raised."""
        return self._load_error

    def load(self) -> LabSettings:
        self._load_error = None
        if not self.path.is_file():
            return LabSettings()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            self._load_error = str(error)
            return LabSettings()
        if not isinstance(payload, dict):
            self._load_error = "settings file is not a JSON object"
            return LabSettings()
        migrated = migrate(payload)
        if migrated is None:
            self._load_error = (
                f"settings version {payload.get('version')!r} cannot be read by "
                f"this build (it writes {SETTINGS_VERSION}); defaults are in use"
            )
            return LabSettings()
        known = {field_name for field_name in LabSettings().__dataclass_fields__}
        accepted = {key: value for key, value in migrated.items() if key in known}
        try:
            return LabSettings(**accepted).normalized()
        except TypeError as error:
            self._load_error = str(error)
            return LabSettings()

    def save(self, settings: LabSettings) -> LabSettings:
        """Write atomically: a half-written settings file must never exist."""
        normalized = settings.normalized()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(
            json.dumps(asdict(normalized), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
        self._load_error = None
        return normalized
