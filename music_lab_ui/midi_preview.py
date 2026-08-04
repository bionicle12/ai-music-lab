"""Reads a transcribed ``.mid`` back so it can be seen and heard in the app.

A MIDI file is the deliverable, but it is also unverifiable by eye: whether the
transcription actually followed the audio is a question you answer by looking at
a piano roll and listening, not by reading a byte count.

The preview synthesiser here is deliberately crude — sines and noise bursts,
no soundfont. muscriptor's own auralisation needs a fluidsynth binary, which is
one more system dependency for something whose only job is to tell you whether
the notes line up. This is a check, not a rendering, and the interface says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from .i18n import Translator, get_translator
from .plots import AMBER, CYAN, GRID, MUTED, VIOLET, _base_layout, empty_figure

#: General MIDI puts percussion on channel 10, which is index 9.
DRUM_CHANNEL = 9

PREVIEW_SAMPLE_RATE = 22_050
#: Enough to audition a track; a transcription longer than this is a mix, and
#: the workflow this supports is stems.
PREVIEW_MAX_SECONDS = 420.0
#: A runaway file must not turn a preview into a minute of numpy.
PREVIEW_MAX_NOTES = 20_000

TRACK_COLOURS = (CYAN, AMBER, VIOLET, "#5fd7a7", "#f07ab0", "#9fb4c7")


@dataclass(frozen=True)
class MidiTrackNotes:
    name: str
    is_drum: bool
    start_seconds: np.ndarray
    end_seconds: np.ndarray
    pitch: np.ndarray

    def __len__(self) -> int:
        return int(self.pitch.size)


@dataclass(frozen=True)
class MidiPreview:
    tracks: tuple[MidiTrackNotes, ...]
    duration_seconds: float
    note_count: int
    tempo_bpm: float

    @property
    def is_empty(self) -> bool:
        return self.note_count == 0


def _tempo_map(midi) -> list[tuple[int, int]]:
    """Absolute ticks -> microseconds per beat, in tick order.

    Tempo changes usually live in track 0, but nothing in the format says they
    have to, so every track is scanned.
    """
    changes: list[tuple[int, int]] = []
    for track in midi.tracks:
        tick = 0
        for message in track:
            tick += message.time
            if message.type == "set_tempo":
                changes.append((tick, message.tempo))
    changes.sort(key=lambda item: item[0])
    if not changes or changes[0][0] != 0:
        # 120 bpm is what the format assumes in the absence of a marker.
        changes.insert(0, (0, 500_000))
    return changes


def _tick_to_seconds(tick: int, tempo_map: list[tuple[int, int]], ticks_per_beat: int):
    """Walk the tempo map, accumulating real time segment by segment."""
    seconds = 0.0
    previous_tick, tempo = tempo_map[0]
    for change_tick, change_tempo in tempo_map[1:]:
        if change_tick >= tick:
            break
        seconds += (change_tick - previous_tick) * tempo / 1_000_000.0 / ticks_per_beat
        previous_tick, tempo = change_tick, change_tempo
    seconds += (tick - previous_tick) * tempo / 1_000_000.0 / ticks_per_beat
    return seconds


def read_midi(path: Path | str) -> MidiPreview:
    """Parse a MIDI file into per-track note arrays with absolute times.

    Tracks are kept separate rather than merged: muscriptor writes one per
    instrument and names it, which is exactly the grouping worth seeing.
    """
    import mido

    midi = mido.MidiFile(str(path))
    tempo_map = _tempo_map(midi)
    ticks_per_beat = midi.ticks_per_beat or 480
    tracks: list[MidiTrackNotes] = []
    duration = 0.0
    total = 0

    for index, track in enumerate(midi.tracks):
        tick = 0
        # (channel, pitch) -> tick of the note-on still waiting for its end.
        open_notes: dict[tuple[int, int], int] = {}
        starts: list[float] = []
        ends: list[float] = []
        pitches: list[int] = []
        drum = False
        for message in track:
            tick += message.time
            if message.type == "note_on" and message.velocity > 0:
                open_notes[(message.channel, message.note)] = tick
                drum = drum or message.channel == DRUM_CHANNEL
            elif message.type in ("note_off", "note_on"):
                started = open_notes.pop((message.channel, message.note), None)
                if started is None:
                    continue
                start = _tick_to_seconds(started, tempo_map, ticks_per_beat)
                end = _tick_to_seconds(tick, tempo_map, ticks_per_beat)
                starts.append(start)
                # A zero-length note is inaudible and invisible; give it a floor.
                ends.append(max(end, start + 0.02))
                pitches.append(message.note)
        if not pitches:
            continue
        name = (track.name or "").strip() or f"track {index + 1}"
        tracks.append(
            MidiTrackNotes(
                name=name,
                is_drum=drum,
                start_seconds=np.asarray(starts, dtype=float),
                end_seconds=np.asarray(ends, dtype=float),
                pitch=np.asarray(pitches, dtype=int),
            )
        )
        duration = max(duration, float(max(ends)))
        total += len(pitches)

    return MidiPreview(
        tracks=tuple(tracks),
        duration_seconds=duration,
        note_count=total,
        tempo_bpm=round(60_000_000.0 / tempo_map[0][1], 2),
    )


def piano_roll_figure(
    preview: MidiPreview,
    t: Translator | None = None,
) -> go.Figure:
    """Every note as a horizontal bar, one colour per instrument track."""
    translate = t or get_translator()
    if preview.is_empty:
        return empty_figure(translate("midi.empty.notes"))

    figure = go.Figure()
    for index, track in enumerate(preview.tracks):
        colour = TRACK_COLOURS[index % len(TRACK_COLOURS)]
        # NaN between segments is what keeps one trace from drawing a line from
        # the end of one note to the start of the next.
        count = len(track)
        x = np.empty(count * 3, dtype=float)
        y = np.empty(count * 3, dtype=float)
        x[0::3] = track.start_seconds
        x[1::3] = track.end_seconds
        x[2::3] = np.nan
        y[0::3] = track.pitch
        y[1::3] = track.pitch
        y[2::3] = np.nan
        figure.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                name=track.name,
                line={"color": colour, "width": 6},
                hoverinfo="name",
                connectgaps=False,
            )
        )

    lowest = min(int(track.pitch.min()) for track in preview.tracks)
    highest = max(int(track.pitch.max()) for track in preview.tracks)
    _base_layout(
        figure,
        translate("midi.plot.title"),
        height=max(300, min(620, 40 + (highest - lowest + 2) * 9)),
        time_axis=True,
    )
    figure.update_xaxes(title=translate("plot.axis.time"))
    figure.update_layout(
        yaxis={
            "title": {"text": translate("midi.plot.pitch")},
            "range": [lowest - 1.5, highest + 1.5],
            "gridcolor": GRID,
            "zerolinecolor": GRID,
        }
    )
    return figure


def _envelope(length: int, sample_rate: int, decay: float) -> np.ndarray:
    """Short attack, exponential decay — enough shape to hear note boundaries."""
    time = np.arange(length, dtype=np.float32) / sample_rate
    attack_samples = max(1, int(0.005 * sample_rate))
    envelope = np.exp(-time / decay).astype(np.float32)
    envelope[:attack_samples] *= np.linspace(0.0, 1.0, attack_samples, dtype=np.float32)
    return envelope


def _drum_voice(pitch: int, length: int, sample_rate: int) -> np.ndarray:
    """Three coarse buckets: kick, snare, everything metallic."""
    generator = np.random.default_rng(pitch)
    noise = generator.standard_normal(length).astype(np.float32)
    if pitch <= 37:  # kick and low toms
        time = np.arange(length, dtype=np.float32) / sample_rate
        sweep = np.sin(2 * np.pi * (110.0 * np.exp(-time * 28.0)) * time)
        return (sweep * _envelope(length, sample_rate, 0.12)).astype(np.float32)
    if pitch <= 41:  # snare
        return (noise * _envelope(length, sample_rate, 0.09)).astype(np.float32)
    # Hats and cymbals: brighter, so the noise is differenced to tilt it up.
    bright = np.diff(noise, prepend=np.float32(0.0))
    return (bright * _envelope(length, sample_rate, 0.05)).astype(np.float32)


def preview_audio(
    preview: MidiPreview,
    sample_rate: int = PREVIEW_SAMPLE_RATE,
) -> tuple[int, np.ndarray] | None:
    """Render an audible check of the transcription, or None if there is nothing.

    Not a mixdown and not trying to be one — the point is to hear whether the
    notes land where the audio does.
    """
    if preview.is_empty:
        return None

    duration = min(preview.duration_seconds, PREVIEW_MAX_SECONDS) + 0.4
    buffer = np.zeros(int(duration * sample_rate) + 1, dtype=np.float32)
    rendered = 0

    for track in preview.tracks:
        for start, end, pitch in zip(
            track.start_seconds, track.end_seconds, track.pitch
        ):
            if rendered >= PREVIEW_MAX_NOTES or start > PREVIEW_MAX_SECONDS:
                break
            begin = int(start * sample_rate)
            # A little tail past the note end, or every note clicks off.
            length = int(min(end - start + 0.15, 4.0) * sample_rate)
            if length <= 0 or begin >= buffer.size:
                continue
            length = min(length, buffer.size - begin)
            if track.is_drum:
                voice = _drum_voice(int(pitch), length, sample_rate)
            else:
                frequency = 440.0 * 2.0 ** ((int(pitch) - 69) / 12.0)
                time = np.arange(length, dtype=np.float32) / sample_rate
                phase = 2 * np.pi * frequency * time
                voice = (
                    np.sin(phase)
                    + 0.35 * np.sin(2 * phase)
                    + 0.15 * np.sin(3 * phase)
                ).astype(np.float32)
                voice *= _envelope(length, sample_rate, max(0.25, end - start))
            buffer[begin : begin + length] += voice
            rendered += 1

    peak = float(np.max(np.abs(buffer))) if buffer.size else 0.0
    if peak > 0:
        buffer *= 0.7 / peak
    return sample_rate, buffer


def preview_summary(preview: MidiPreview, t: Translator | None = None) -> str:
    translate = t or get_translator()
    if preview.is_empty:
        return translate("midi.empty.notes")
    return translate(
        "midi.preview.summary",
        notes=preview.note_count,
        tracks=len(preview.tracks),
        seconds=f"{preview.duration_seconds:.1f}",
        tempo=f"{preview.tempo_bpm:g}",
        names=", ".join(track.name for track in preview.tracks),
    )
