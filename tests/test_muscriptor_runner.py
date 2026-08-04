"""The runner is tested against a fake child: no environment, no weights, no net.

The security-relevant assertion is that the token reaches the child only through
its environment — a command-line argument would be readable by anything that can
list processes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from music_lab_ui.config import LabPaths
from music_lab_ui.muscriptor import (
    AdapterError,
    build_env,
    download_weights,
    missing_requirements,
    parse_line,
    stream_adapter,
    transcribe,
)

TOKEN = "hf_xxxxTESTTOKENxxxx"


def lab(tmp_path: Path, monkeypatch) -> LabPaths:
    """A repo whose adapter and environment python both exist as empty files."""
    root = tmp_path / "ai-music-lab"
    (root / "adapters").mkdir(parents=True)
    (root / "adapters" / "muscriptor_cli.py").write_text("", encoding="utf-8")
    interpreter = tmp_path / "python.exe"
    interpreter.write_text("", encoding="utf-8")
    monkeypatch.setenv("AI_MUSIC_MUSCRIPTOR_PYTHON", str(interpreter))
    return LabPaths.from_root(root)


class FakeProcess:
    def __init__(self, lines: list[str], returncode: int = 0, stderr: str = "") -> None:
        self.stdout = iter(lines)
        self.stderr = _Reader(stderr)
        self.returncode = returncode
        self.killed = False
        self.env: dict[str, str] = {}
        self.argv: list[str] = []

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True


class _Reader:
    def __init__(self, text: str) -> None:
        self.text = text

    def read(self) -> str:
        return self.text


def popener_for(process: FakeProcess):
    def popen(argv, **kwargs):
        process.argv = list(argv)
        process.env = dict(kwargs.get("env") or {})
        return process

    return popen


def test_a_token_travels_in_the_environment_and_nowhere_else(
    tmp_path: Path, monkeypatch
) -> None:
    paths = lab(tmp_path, monkeypatch)
    process = FakeProcess(['{"event":"result","payload":{"mode":"download"}}\n'])

    list(
        download_weights(
            paths, TOKEN, "small", popener=popener_for(process), environ={}
        )
    )

    assert process.env["HF_TOKEN"] == TOKEN
    assert not any(TOKEN in argument for argument in process.argv)


def test_no_token_means_the_variable_is_absent_not_empty() -> None:
    paths = LabPaths.from_root(Path("."))

    child = build_env(paths, "  ", {"HF_TOKEN": "stale"})

    # An empty HF_TOKEN would make huggingface_hub authenticate with nothing and
    # fail in a way that reads like a permissions problem.
    assert "HF_TOKEN" not in child


def test_the_child_gets_a_repo_local_weight_cache(tmp_path: Path) -> None:
    paths = LabPaths.from_root(tmp_path / "ai-music-lab")

    child = build_env(paths, "", {})

    assert child["HF_HOME"] == str(paths.muscriptor_cache)
    assert child["PYTHONUTF8"] == "1"


def test_malformed_output_becomes_a_log_line_rather_than_a_crash() -> None:
    assert parse_line("not json at all").kind == "log"
    assert parse_line("{}").kind == "log"
    assert parse_line('{"nope": 1}').kind == "log"
    assert parse_line("").kind == "log"

    event = parse_line('{"event":"progress","fraction":0.5,"message":"weights"}')
    assert (event.kind, event.fraction, event.message) == ("progress", 0.5, "weights")


def test_events_arrive_in_order(tmp_path: Path, monkeypatch) -> None:
    paths = lab(tmp_path, monkeypatch)
    process = FakeProcess(
        [
            '{"event":"progress","fraction":0.1}\n',
            "a stray print from some dependency\n",
            '{"event":"progress","fraction":0.9}\n',
            '{"event":"result","payload":{"model":"small"}}\n',
        ]
    )

    events = list(
        download_weights(paths, "", "small", popener=popener_for(process), environ={})
    )

    assert [event.kind for event in events] == [
        "progress",
        "log",
        "progress",
        "result",
    ]
    assert events[-1].payload["model"] == "small"


def test_a_failed_run_raises_with_the_code_the_adapter_reported(
    tmp_path: Path, monkeypatch
) -> None:
    paths = lab(tmp_path, monkeypatch)
    process = FakeProcess(
        ['{"event":"error","code":"gated_repo","detail":"accept the licence"}\n'],
        returncode=1,
        stderr="ModelDownloadError: gated",
    )

    with pytest.raises(AdapterError) as raised:
        list(
            download_weights(
                paths, TOKEN, "small", popener=popener_for(process), environ={}
            )
        )

    assert raised.value.code == "gated_repo"
    assert "gated" in raised.value.detail


def test_a_silent_child_is_killed_rather_than_waited_on_forever(
    tmp_path: Path, monkeypatch
) -> None:
    paths = lab(tmp_path, monkeypatch)

    class Silent(FakeProcess):
        def __init__(self) -> None:
            super().__init__([])
            self.stdout = _Blocking()

    process = Silent()
    with pytest.raises(AdapterError) as raised:
        list(
            download_weights(
                paths,
                "",
                "small",
                popener=popener_for(process),
                idle_timeout=0.05,
                environ={},
            )
        )

    assert raised.value.code == "stalled"
    assert process.killed is True


class _Blocking:
    """An stdout that never yields a line, like a stalled connection."""

    def __iter__(self):
        return self

    def __next__(self):
        import time

        time.sleep(5)
        raise StopIteration


def test_a_missing_environment_is_reported_before_anything_is_launched(
    tmp_path: Path,
) -> None:
    paths = LabPaths.from_root(tmp_path / "ai-music-lab")

    assert missing_requirements(paths)
    with pytest.raises(RuntimeError, match="missing files"):
        list(stream_adapter(["x"], paths, "", popener=lambda *a, **k: None))


def test_transcribe_passes_instruments_only_when_given(
    tmp_path: Path, monkeypatch
) -> None:
    paths = lab(tmp_path, monkeypatch)
    process = FakeProcess(['{"event":"result","payload":{}}\n'])

    list(
        transcribe(
            paths,
            "",
            tmp_path / "stem.wav",
            tmp_path / "out.mid",
            size="large",
            instruments="  ",
            popener=popener_for(process),
            environ={},
        )
    )

    assert "--instruments" not in process.argv
    assert "--beam-size" in process.argv
    # Greedy decoding by default: same input and parameters, same MIDI.
    assert process.argv[process.argv.index("--beam-size") + 1] == "1"


def test_the_instrument_list_is_the_model_s_own_vocabulary() -> None:
    """Typed names were a trap: a misspelling silently transcribed everything
    instead of the one part asked for. These are picked, not written."""
    from music_lab_ui.muscriptor import INSTRUMENTS, instrument_choices

    assert len(INSTRUMENTS) == 35
    assert "drums" in INSTRUMENTS
    assert "acoustic_piano" in INSTRUMENTS
    # Labels are readable; values stay exactly what the adapter expects.
    labels = dict(instrument_choices())
    assert labels["acoustic piano"] == "acoustic_piano"
    assert all("_" not in label for label in labels)


def test_a_picked_list_reaches_the_adapter_as_its_comma_format(
    tmp_path: Path, monkeypatch
) -> None:
    """The picker hands back a list; the CLI takes a comma-separated string."""
    from music_lab_ui.config import LabPaths
    from music_lab_ui.history import HistoryStore
    from music_lab_ui.ui_service import AnalysisService

    import soundfile as sf
    import numpy as np

    root = tmp_path / "ai-music-lab"
    root.mkdir()
    audio = tmp_path / "stem.wav"
    sf.write(audio, np.zeros(1000, dtype=np.float32), 16_000)
    paths = LabPaths.from_root(root)
    seen: dict[str, object] = {}

    def fake_midi_runner(*args, **kwargs):
        seen.update(kwargs)
        return iter(())

    service = AnalysisService(
        paths=paths,
        history=HistoryStore(paths.history_db, paths.runs_dir),
        midi_runner=fake_midi_runner,
    )
    service.transcribe_to_midi(audio, instruments=["drums", "electric_bass"])

    assert seen["instruments"] == "drums, electric_bass"


def test_probe_reports_a_missing_environment_as_a_classified_error(
    tmp_path: Path,
) -> None:
    from music_lab_ui.muscriptor import probe

    paths = LabPaths.from_root(tmp_path / "ai-music-lab")

    with pytest.raises(AdapterError) as raised:
        probe(paths)

    assert raised.value.code == "package_missing"


def test_probe_returns_the_result_payload(tmp_path: Path, monkeypatch) -> None:
    from music_lab_ui.muscriptor import probe

    paths = lab(tmp_path, monkeypatch)

    def runner(argv, **kwargs):
        assert kwargs["env"]["HF_TOKEN"] == TOKEN
        return subprocess.CompletedProcess(
            argv, 0, '{"event":"result","payload":{"muscriptor_version":"0.2.2"}}\n', ""
        )

    assert probe(paths, TOKEN, runner=runner, environ={}) == {
        "muscriptor_version": "0.2.2"
    }
