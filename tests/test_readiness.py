"""Readiness is a checklist, and the tests are about which row fails and when."""

from __future__ import annotations

from pathlib import Path

from music_lab_ui.config import LabPaths
from music_lab_ui.readiness import ITEM_KEYS, can_transcribe, evaluate
from music_lab_ui.settings import LabSettings

PATHS = LabPaths.from_root(Path("C:/lab"))


def report(settings: LabSettings, present: set[str] | None = None, **kwargs):
    known = present if present is not None else set()

    def exists(path: Path) -> bool:
        # as_posix so a test can name a path without caring which slash Windows
        # turns it into.
        return path.as_posix() in known or path.name in known

    return evaluate(PATHS, settings, {}, exists=exists, **kwargs)


def keyed(result) -> dict[str, bool | None]:
    return {item.key: item.ok for item in result.items}


def test_a_fresh_install_fails_at_the_first_row_not_the_last() -> None:
    result = report(LabSettings())

    assert [item.key for item in result.items] == list(ITEM_KEYS)
    assert result.first_problem().key == "clone"
    assert result.ready is False


def test_every_requirement_is_reported_separately() -> None:
    settings = LabSettings(
        hf_token="hf_abcdefghijklmnop",
        weights_license_accepted=True,
        muscriptor_model="large",
        muscriptor_weights={"large": "C:/cache/large/model.safetensors"},
    )
    present = {
        "pyproject.toml",
        "__init__.py",
        "python.exe",
        "C:/cache/large/model.safetensors",
    }

    result = report(settings, present)

    assert keyed(result) == {
        "clone": True,
        "env": True,
        "license": True,
        "token": True,
        "weights": True,
        # Not checked: no probe was passed.
        "package": None,
    }


def test_an_unprobed_report_is_never_ready() -> None:
    """Unknown is not the same as broken, but it is not ready either."""
    settings = LabSettings(
        hf_token="hf_abcdefghijklmnop",
        weights_license_accepted=True,
        muscriptor_weights={"large": "C:/w"},
    )

    result = report(settings, {"pyproject.toml", "__init__.py", "python.exe", "C:/w"})

    assert result.probed is False
    assert result.ready is False
    # …but the run button is still offered: a real run fails loudly enough.
    assert can_transcribe(result) is True


def test_a_probe_that_resolves_outside_the_clone_is_a_failure() -> None:
    """Then `git pull` on the clone changes nothing that actually runs."""
    settings = LabSettings(weights_license_accepted=True, hf_token="hf_abcdefghijkl")

    result = report(
        settings,
        {"pyproject.toml", "__init__.py", "python.exe"},
        probe=lambda: {
            "muscriptor_file": "C:/env/site-packages/muscriptor/__init__.py",
            "inside_clone": False,
        },
    )

    assert keyed(result)["package"] is False
    assert "site-packages" in dict(
        (item.key, item.detail) for item in result.items
    )["package"]


def test_a_probe_that_raises_becomes_a_row_rather_than_an_exception() -> None:
    def broken():
        raise RuntimeError("python.exe not found")

    result = report(LabSettings(), probe=broken)

    assert keyed(result)["package"] is False
    assert result.probed is True


def test_the_token_row_names_its_source_and_never_the_token() -> None:
    secret = "hf_xxxxTESTTOKENxxxx"
    details = dict(
        (item.key, item.detail)
        for item in evaluate(
            PATHS,
            LabSettings(hf_token=secret),
            {},
            exists=lambda path: False,
        ).items
    )

    assert secret not in details["token"]
    assert details["token"] == "…xxxx"


def test_an_environment_token_is_reported_as_such() -> None:
    result = evaluate(
        PATHS,
        LabSettings(),
        {"HF_TOKEN": "hf_fromenv"},
        exists=lambda path: False,
    )

    assert dict((item.key, item.detail) for item in result.items)["token"] == "HF_TOKEN"


def test_weights_are_checked_for_the_selected_size_only() -> None:
    settings = LabSettings(
        muscriptor_model="large",
        muscriptor_weights={"small": "C:/cache/small"},
    )

    result = report(settings, {"C:/cache/small"})

    assert keyed(result)["weights"] is False


def test_a_recorded_path_that_no_longer_exists_is_not_ready() -> None:
    """Someone clearing the cache must not leave a green checkbox behind."""
    settings = LabSettings(muscriptor_weights={"large": "C:/cache/gone"})

    assert keyed(report(settings))["weights"] is False
