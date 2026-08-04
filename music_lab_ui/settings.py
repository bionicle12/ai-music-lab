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
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Final

#: Bumped when a stored file can no longer be read as-is. An unknown version
#: falls back to defaults rather than guessing at a migration.
SETTINGS_VERSION: Final[int] = 1

MODEL_SIZES: Final[tuple[str, ...]] = ("small", "medium", "large")
DEFAULT_MODEL: Final[str] = "large"
DEVICES: Final[tuple[str, ...]] = ("cuda", "cpu")


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
        return replace(
            self,
            hf_token=self.hf_token.strip(),
            muscriptor_model=model,
            midi_device=device,
            muscriptor_weights=weights,
            version=SETTINGS_VERSION,
        )


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
        if payload.get("version") != SETTINGS_VERSION:
            self._load_error = (
                f"settings version {payload.get('version')!r} is not "
                f"{SETTINGS_VERSION}; defaults are in use"
            )
            return LabSettings()
        known = {field_name for field_name in LabSettings().__dataclass_fields__}
        accepted = {key: value for key, value in payload.items() if key in known}
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
