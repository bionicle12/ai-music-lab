"""The settings file is user-editable, so every way it can be wrong is a test."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from music_lab_ui.settings import (
    DEFAULT_MODEL,
    SETTINGS_VERSION,
    LabSettings,
    SettingsStore,
    resolve_token,
    token_fingerprint,
)


def test_missing_file_yields_defaults_without_an_error(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")

    assert store.load() == LabSettings()
    assert store.load_error is None


def test_settings_round_trip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "data" / "settings.json")
    saved = store.save(
        LabSettings(
            hf_token="hf_secretvalue1234",
            muscriptor_model="small",
            muscriptor_weights={"small": "C:/cache/small"},
            weights_license_accepted=True,
        )
    )

    assert store.load() == saved
    assert store.load_error is None


def test_save_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    SettingsStore(path).save(LabSettings(hf_token="hf_token"))

    assert [item.name for item in tmp_path.iterdir()] == ["settings.json"]


def test_a_corrupt_file_falls_back_to_defaults_instead_of_raising(
    tmp_path: Path,
) -> None:
    """A stray comma must not leave the interface unable to start."""
    path = tmp_path / "settings.json"
    path.write_text("{ not json", encoding="utf-8")
    store = SettingsStore(path)

    assert store.load() == LabSettings()
    assert store.load_error


def test_an_unknown_version_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 99, "hf_token": "x"}), encoding="utf-8")
    store = SettingsStore(path)

    assert store.load() == LabSettings()
    assert "99" in (store.load_error or "")


def test_unknown_keys_are_dropped_rather_than_crashing(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"version": SETTINGS_VERSION, "hf_token": "hf_x", "nonsense": 1}),
        encoding="utf-8",
    )

    assert SettingsStore(path).load().hf_token == "hf_x"


def test_hand_edited_values_outside_the_allowed_set_are_clamped() -> None:
    settings = LabSettings(
        muscriptor_model="enormous",
        midi_device="quantum",
        muscriptor_weights={"large": "C:/ok", "enormous": "C:/no"},
    ).normalized()

    assert settings.muscriptor_model == DEFAULT_MODEL
    assert settings.midi_device == "cuda"
    assert settings.muscriptor_weights == {"large": "C:/ok"}


def test_fingerprint_never_reveals_more_than_four_characters() -> None:
    assert token_fingerprint("hf_abcdefghijklmnop") == "…mnop"
    assert token_fingerprint("") == ""
    # Too short to mask meaningfully, so it is not shown at all.
    assert token_fingerprint("hf_short") == "…"


def test_environment_token_wins_over_the_stored_one() -> None:
    stored = LabSettings(hf_token="hf_fromfile")

    assert resolve_token(stored, {"HF_TOKEN": "hf_fromenv"}) == ("hf_fromenv", "env")
    assert resolve_token(stored, {}) == ("hf_fromfile", "settings")
    assert resolve_token(LabSettings(), {}) == ("", "none")
    # A variable set to whitespace is the same as not setting it.
    assert resolve_token(LabSettings(), {"HF_TOKEN": "  "}) == ("", "none")


def test_clearing_the_token_removes_it_from_disk(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    stored = store.save(LabSettings(hf_token="hf_secretvalue1234"))
    store.save(replace(stored, hf_token=""))

    assert "hf_secretvalue1234" not in path.read_text(encoding="utf-8")
