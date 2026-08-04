"""Reading a transcription back is what makes it checkable rather than trusted."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from music_lab_ui.i18n import get_translator
from music_lab_ui.midi_preview import (
    DRUM_CHANNEL,
    piano_roll_figure,
    preview_audio,
    preview_summary,
    read_midi,
)

t = get_translator()


def write_midi(path: Path, *, tempo: int = 500_000, drums: bool = False) -> Path:
    """Two named tracks, the second optionally on the percussion channel."""
    import mido

    midi = mido.MidiFile(ticks_per_beat=480)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    midi.tracks.append(meta)

    lead = mido.MidiTrack()
    lead.append(mido.MetaMessage("track_name", name="acoustic piano", time=0))
    lead.append(mido.Message("note_on", note=60, velocity=100, time=0))
    lead.append(mido.Message("note_off", note=60, velocity=0, time=480))
    lead.append(mido.Message("note_on", note=64, velocity=100, time=480))
    lead.append(mido.Message("note_off", note=64, velocity=0, time=480))
    midi.tracks.append(lead)

    channel = DRUM_CHANNEL if drums else 1
    second = mido.MidiTrack()
    second.append(mido.MetaMessage("track_name", name="drums", time=0))
    second.append(
        mido.Message("note_on", note=36, velocity=100, channel=channel, time=0)
    )
    second.append(
        mido.Message("note_off", note=36, velocity=0, channel=channel, time=240)
    )
    midi.tracks.append(second)

    midi.save(str(path))
    return path


def test_notes_are_read_with_absolute_times(tmp_path: Path) -> None:
    preview = read_midi(write_midi(tmp_path / "a.mid"))

    assert preview.note_count == 3
    assert [track.name for track in preview.tracks] == ["acoustic piano", "drums"]
    assert preview.tempo_bpm == pytest.approx(120.0)

    lead = preview.tracks[0]
    # 480 ticks per beat at 120 BPM is half a second; the second note starts one
    # beat after the first ends.
    assert lead.start_seconds == pytest.approx([0.0, 1.0])
    assert lead.end_seconds == pytest.approx([0.5, 1.5])
    assert list(lead.pitch) == [60, 64]
    assert preview.duration_seconds == pytest.approx(1.5)


def test_tempo_is_honoured_rather_than_assumed(tmp_path: Path) -> None:
    """A transcription carries the detected tempo; ignoring it doubles every time."""
    slow = read_midi(write_midi(tmp_path / "slow.mid", tempo=1_000_000))

    assert slow.tempo_bpm == pytest.approx(60.0)
    assert slow.tracks[0].end_seconds[0] == pytest.approx(1.0)


def test_the_percussion_channel_is_recognised(tmp_path: Path) -> None:
    preview = read_midi(write_midi(tmp_path / "d.mid", drums=True))

    assert [track.is_drum for track in preview.tracks] == [False, True]


def test_a_file_with_no_notes_is_reported_not_crashed(tmp_path: Path) -> None:
    import mido

    empty = mido.MidiFile(ticks_per_beat=480)
    empty.tracks.append(mido.MidiTrack())
    path = tmp_path / "empty.mid"
    empty.save(str(path))

    preview = read_midi(path)

    assert preview.is_empty
    assert preview_audio(preview) is None
    assert preview_summary(preview) == t("midi.empty.notes")
    # The figure still renders, so the interface has something to show.
    assert piano_roll_figure(preview).layout.annotations[0].text == t(
        "midi.empty.notes"
    )


def test_the_piano_roll_draws_one_trace_per_track_and_syncs_to_the_player(
    tmp_path: Path,
) -> None:
    figure = piano_roll_figure(read_midi(write_midi(tmp_path / "a.mid")))

    assert [trace.name for trace in figure.data] == ["acoustic piano", "drums"]
    # Clicking the roll should seek the player, like every other time chart.
    assert figure.layout.meta["time_axis"] is True
    # NaN between notes, or one trace would draw a line across the silence.
    assert np.isnan(np.asarray(figure.data[0].x, dtype=float)[2])


def test_the_preview_is_audible_and_bounded(tmp_path: Path) -> None:
    preview = read_midi(write_midi(tmp_path / "a.mid", drums=True))

    rate, samples = preview_audio(preview)

    assert rate == 22_050
    assert samples.dtype == np.float32
    # Long enough to hold the last note, short enough not to be a mixdown.
    assert samples.size / rate == pytest.approx(preview.duration_seconds + 0.4, abs=0.2)
    peak = float(np.max(np.abs(samples)))
    assert 0.6 < peak <= 0.71  # normalised, with headroom left


def test_the_summary_states_what_was_transcribed(tmp_path: Path) -> None:
    preview = read_midi(write_midi(tmp_path / "a.mid"))

    summary = preview_summary(preview, t)

    assert "3" in summary
    assert "acoustic piano" in summary
    assert "120" in summary
