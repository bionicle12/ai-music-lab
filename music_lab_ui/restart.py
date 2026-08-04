"""Restarting the server from inside the interface.

Editing a stylesheet, a translation or a presenter means restarting: Gradio
reads ``css_paths`` once at mount time and the catalogue is captured by the
handler closures. Doing that by hand from a terminal, several times an hour, is
the kind of friction that stops you making small improvements.

The process re-executes itself rather than asking a supervisor to do it, so the
button works however the app was started.

One Windows caveat worth knowing: `os.execv` there is emulated as spawn-and-exit
rather than a true image replacement, so the restarted server gets a new PID and
is no longer attached to the console that launched it — Ctrl+C in that terminal
will not stop it, and the port stays held until the new process is killed.

uvicorn's own `reload=True` would avoid that, and was tried: it detects the
change, announces a reload, and then hangs, because Gradio's queue leaves
threads running that never let the worker shut down. The old code keeps serving
while the log says otherwise, which is worse than restarting by hand.

Two things it deliberately will not do. It refuses when the server is bound to
anything but a loopback address — restarting somebody's server from a web page
is fine on your own machine and rude on a network. And it never touches
``data/``: a restart drops the in-memory state Gradio holds, and nothing else.
"""

from __future__ import annotations

import os
import sys
import threading
from collections.abc import Callable, Sequence
from typing import Final

#: Hosts where the only person who can press the button is the person sitting
#: at the machine. An empty bind address is NOT one of them — to a socket it
#: means every interface — and an unknown host fails closed for the same reason.
LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset(
    {"127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"}
)

#: Distinguishes "work it out from __main__" from "there is no module spec".
_UNSET: Final = object()

#: Long enough for the HTTP response to leave before the process is replaced.
RESTART_DELAY_SECONDS: Final[float] = 0.6


def is_loopback(host: str | None) -> bool:
    return (host or "").strip().lower() in LOOPBACK_HOSTS


def restart_command(
    argv: Sequence[str] | None = None,
    main_spec_name: str | None | object = _UNSET,
) -> list[str]:
    """Rebuild the command line this process was started with.

    ``python -m music_lab_ui.app`` cannot be restarted as
    ``python /path/to/app.py``: the module uses relative imports and would fail
    to load. ``__main__.__spec__`` is how Python records that ``-m`` was used,
    and its name is what has to be handed back.
    """
    arguments = list(sys.argv if argv is None else argv)
    if main_spec_name is _UNSET:
        spec = getattr(sys.modules.get("__main__"), "__spec__", None)
        main_spec_name = getattr(spec, "name", None)
    if main_spec_name:
        return [sys.executable, "-m", str(main_spec_name), *arguments[1:]]
    return [sys.executable, *arguments]


def schedule_restart(
    delay: float = RESTART_DELAY_SECONDS,
    executor: Callable[..., None] = os.execv,
    spawn: Callable[..., threading.Thread] = threading.Thread,
) -> None:
    """Replace this process, after letting the current response finish.

    ``os.execv`` from a timer thread replaces the whole process, threads
    included. Python marks sockets non-inheritable by default, so the listening
    port is released as the image is swapped and the new process can bind it.
    """
    command = restart_command()

    def run() -> None:
        import time

        time.sleep(delay)
        sys.stdout.flush()
        sys.stderr.flush()
        executor(command[0], command)

    spawn(target=run, name="ai-music-restart", daemon=True).start()
