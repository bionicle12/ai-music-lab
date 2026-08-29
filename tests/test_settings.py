"""The settings file is user-editable, so every way it can be wrong is a test."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from music_lab_ui.settings import (
    DEFAULT_FST_BACKBONE_BATCH,
    DEFAULT_FST_CUDA_BACKBONE_BATCH,
    DEFAULT_FST_MPS_BACKBONE_BATCH,
    DEFAULT_MODEL,
    FST_BACKBONE_CHOICES,
    SETTINGS_VERSION,
    LabSettings,
    SettingsStore,
    _MIGRATIONS,
    migrate,
    platform_default_fst_backbone_batch,
    resolve_token,
    token_fingerprint,
)


def test_new_macos_settings_default_to_two() -> None:
    assert platform_default_fst_backbone_batch("darwin") == 2
    assert DEFAULT_FST_MPS_BACKBONE_BATCH == 2


def test_new_windows_settings_keep_cuda_default() -> None:
    assert platform_default_fst_backbone_batch("win32") == 8
    assert DEFAULT_FST_CUDA_BACKBONE_BATCH == 8


def test_fst_batch_choices_include_mps_safe_values() -> None:
    assert FST_BACKBONE_CHOICES == (1, 2, 4, 8, 0)


def test_invalid_fst_batch_uses_the_selected_platform_default() -> None:
    assert LabSettings(fst_backbone_batch=3).normalized().fst_backbone_batch == 2


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


def test_a_version_from_the_future_falls_back_to_defaults(tmp_path: Path) -> None:
    """A shape this build has never seen cannot be read by guessing at it."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 99, "hf_token": "x"}), encoding="utf-8")
    store = SettingsStore(path)

    assert store.load() == LabSettings()
    assert "99" in (store.load_error or "")


def test_an_older_file_is_migrated_rather_than_discarded(tmp_path: Path) -> None:
    """The failure this prevents is silent: bumping the version used to send
    `load` straight to defaults, which reads as the Hugging Face token having
    vanished after an update — noticed a week later, when a download fails."""
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "hf_token": "hf_secretvalue1234",
                "muscriptor_model": "medium",
                "muscriptor_weights": {"medium": "C:/cache/medium"},
                "weights_license_accepted": True,
            }
        ),
        encoding="utf-8",
    )
    store = SettingsStore(path)

    loaded = store.load()

    assert store.load_error is None
    assert loaded.hf_token == "hf_secretvalue1234"
    assert loaded.muscriptor_model == "medium"
    assert loaded.muscriptor_weights == {"medium": "C:/cache/medium"}
    assert loaded.weights_license_accepted is True
    # Fields the old file never had arrive at their defaults, not at zero.
    assert loaded.fst_backbone_batch == DEFAULT_FST_BACKBONE_BATCH
    assert loaded.version == SETTINGS_VERSION


def test_every_version_in_between_has_a_migration_step() -> None:
    """A gap in the chain is a version that silently discards a settings file."""
    assert set(_MIGRATIONS) == set(range(1, SETTINGS_VERSION))


def test_a_version_that_is_not_a_number_is_refused() -> None:
    """`True` is an int in Python, and version 1 must not be spelled `true`."""
    assert migrate({"version": True}) is None
    assert migrate({"version": "1"}) is None
    assert migrate({"version": 0}) is None
    assert migrate({}) is None


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
