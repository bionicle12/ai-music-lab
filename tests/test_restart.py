"""Guards for the restart button.

Two things carry real consequences: rebuilding the command line wrongly leaves
you with a dead port, and the loopback check is what keeps the button from
being a way for anyone on the network to bounce someone else's server.
"""

from __future__ import annotations

import sys

import pytest

from music_lab_ui.restart import (
    LOOPBACK_HOSTS,
    is_loopback,
    restart_command,
    schedule_restart,
)


@pytest.mark.parametrize("host", sorted(LOOPBACK_HOSTS))
def test_loopback_hosts_are_recognised(host: str) -> None:
    assert is_loopback(host)


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "example.com", None])
def test_anything_reachable_from_elsewhere_is_not(host) -> None:
    assert not is_loopback(host)


def test_capitalisation_and_padding_do_not_defeat_the_check() -> None:
    assert is_loopback("  LocalHost ")


def test_a_module_launch_is_restarted_as_a_module() -> None:
    """`python -m music_lab_ui.app` cannot be restarted as
    `python /path/to/app.py`: the module uses relative imports and would not
    load. This is the case that actually happens."""
    command = restart_command(
        argv=["/repo/music_lab_ui/app.py"],
        main_spec_name="music_lab_ui.app",
    )

    assert command == [sys.executable, "-m", "music_lab_ui.app"]


def test_a_script_launch_keeps_its_arguments() -> None:
    command = restart_command(
        argv=["serve.py", "--port", "7860"], main_spec_name=None
    )

    assert command == [sys.executable, "serve.py", "--port", "7860"]


def test_the_process_is_replaced_only_after_the_response_can_leave() -> None:
    """Calling execv inline would kill the connection mid-response, so the
    caller sees a network error instead of the confirmation."""
    calls: list[tuple] = []
    started: list[dict] = []

    class FakeThread:
        def __init__(self, **kwargs):
            started.append(kwargs)

        def start(self):
            started[-1]["target"]()

    schedule_restart(
        delay=0,
        executor=lambda path, args: calls.append((path, args)),
        spawn=FakeThread,
    )

    assert started[0]["daemon"] is True
    assert len(calls) == 1
    path, args = calls[0]
    assert path == sys.executable
    assert args[0] == sys.executable


def test_the_button_is_wired_and_asks_before_it_acts() -> None:
    from music_lab_ui.app import build_app, restart_head

    config = build_app().get_config_file()
    javascript = str(config["dependencies"])

    assert "aiLabConfirmRestart" in javascript
    assert "aiLabAwaitRestart" in javascript
    # The dialog runs before Python, so a cancelled prompt restarts nothing.
    assert "confirm" in restart_head()
