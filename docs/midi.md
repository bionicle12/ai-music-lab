# Audio → MIDI

[← Documentation](README.md) · [Русский](ru/midi.md)

**The question this answers:** what are the actual notes, so they can be replayed with
something other than a generator?

Transcription runs on [muscriptor](https://github.com/muscriptor/muscriptor) — a
multi-instrument audio-to-MIDI model from Kyutai and Mirelo. It runs locally, in its own conda
environment, on your GPU.

## Before anything works

Four things have to line up. The checklist in **Settings** (the gear beside the title) shows
which of them do not, and the first failing row tells you what to do about it.

### 1. Clone and environment

muscriptor is a pip package, but it is cloned as a sibling anyway and installed in editable
mode: that way `git pull` updates the code that actually runs, which is the point of tracking a
project that is still being fixed.

```powershell
cd ..
git clone https://github.com/muscriptor/muscriptor.git
cd ai-music-lab
conda create -n ai-music-muscriptor python=3.11 -y
conda run -n ai-music-muscriptor python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
conda run -n ai-music-muscriptor python -m pip install -e ..\muscriptor
```

Verify the install landed on the clone rather than on a copy from PyPI — otherwise pulling the
clone changes nothing:

```powershell
conda run -n ai-music-muscriptor python -c "import muscriptor; print(muscriptor.__file__)"
```

The path must be inside `..\muscriptor`. The **Check the environment** button in Settings makes
the same assertion and turns the *Package check* row red if it fails.

### 2. Accept the licence on Hugging Face

The weights are gated. Open the page of the size you intend to use —
[small](https://huggingface.co/MuScriptor/muscriptor-small),
[medium](https://huggingface.co/MuScriptor/muscriptor-medium),
[large](https://huggingface.co/MuScriptor/muscriptor-large) — and accept CC BY-NC 4.0. Access is
granted automatically.

### 3. A token

Create one at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens). A
**Read** token is enough.

If you create a **fine-grained** token instead, it will not reach gated repositories unless you
tick *Read access to contents of all public gated repos you can access*. That one checkbox is
the most common reason a download fails with a permissions error despite a valid token.

Two places to put it:

| Where | Consequence |
| --- | --- |
| Settings panel | Stored in `data/settings.json` as plain text. Git-ignored, but a local file with no protection beyond your account. |
| `HF_TOKEN` in the environment | Nothing is written to disk. Takes priority over the stored one. |

Either way the token is handed to the muscriptor subprocess as an environment variable and
nowhere else — never as a command-line argument (those are visible to anything that can list
processes), never into the run history, the technical-data panel, or a log. The panel shows only
its last four characters.

### 4. Download the weights

| Variant | Parameters | Download |
| --- | ---: | ---: |
| `small` | 103M | ~0.4 GB |
| `medium` | 307M | ~1.2 GB |
| `large` | 1.4B | ~5.6 GB |

Pick one in Settings and press **Download weights**. They land in `models/muscriptor-cache/`
(the app points `HF_HOME` there) rather than on the system drive.

After downloading, the adapter immediately re-resolves the weights with `HF_HUB_OFFLINE=1`. A
green checkbox then means the cache really resolves, not merely that a file appeared.

The app runs one job at a time, so a download occupies the whole interface until it finishes.

## Transcribing

Three sources: a stem sent over from **Layers**, the audio of the current run, or a file you
upload.

**Send it stems.** Polyphonic transcription of a dense mix is not a solved problem, and the
difference between a bass stem and the full track it came from is the difference between a
result worth editing and one worth deleting. That is what the **Send to MIDI** button in Layers
is for: measure the stems, click the row you want, send it straight across.

`Only these instruments` filters the output — `drums, acoustic_piano` and so on, comma
separated. Leave it empty to keep everything muscriptor hears.

Decoding is **greedy**, with no sampling and no temperature, so the same audio with the same
settings produces the same MIDI. Every run writes a JSON file beside the `.mid` recording the
checkpoint, the decoding parameters and the muscriptor version, so an old transcription stays
interpretable after an update.

Output goes to `output/midi/<timestamp>-<name>.mid`, not into Gradio's cache — that is wiped
daily, and a file you are about to open in a DAW should outlive the day.

## Checking the result before you open a DAW

The finished file is read straight back and shown two ways.

A **piano roll**, one colour per instrument track, on the same time axis as every other chart in
the app — so clicking it seeks the player, and the playhead follows playback across it. This is
where you see whether the notes actually sit where the audio does.

A **preview player**, synthesised from the notes with plain sine and noise voices. It is not a
mixdown and does not try to be one: muscriptor's own auralisation needs a fluidsynth binary,
which is a system dependency too many for something whose only job is to answer "did it hear the
right thing". Drums come out as three coarse buckets — kick, snare, everything metallic.

Reading the file back is also the last check that the run really succeeded: a `.mid` that does
not parse is a failure whatever the payload says.

## What it will and will not give you

Pitch and timing, and a separate track per instrument it recognises. Not articulation: legato,
staccato, bowing, slides and bends are not in the MIDI and have to be played back in by hand.
Guitar arrives as notes with no fret or string information. Sub-bass below roughly 40 Hz often
lands an octave off, and heavily distorted bass has enough harmonic content that the model can
hear a harmonic as the note.

The `!` badges in the MIDI tab cover what to do with the result in FL Studio, per instrument
family.

## From the command line

```powershell
conda run -n ai-music-muscriptor python adapters\muscriptor_cli.py --mode probe --upstream ..\muscriptor --json-output artifacts\muscriptor-probe.json
```

```powershell
conda run -n ai-music-muscriptor python adapters\muscriptor_cli.py --mode download --model small --json-output artifacts\muscriptor-download.json
```

```powershell
conda run -n ai-music-muscriptor python adapters\muscriptor_cli.py --mode transcribe --model small --audio artifacts\stem-drums.wav --midi-output output\midi\smoke.mid --json-output artifacts\muscriptor-smoke.json
```

Set `HF_HOME` to `models\muscriptor-cache` and `HF_TOKEN` to your token first — the adapter has
no `--token` flag by design. Progress is written to stdout as one JSON object per line; human
logging goes to stderr.

## Updating muscriptor

Unlike the two detectors, muscriptor tracks its branch and can be fast-forwarded from Settings.
The update refuses on a dirty working copy, on a detached HEAD, and on anything that is not a
git repository, and `pull --ff-only` is the only mutating git command the app will ever run.

If the pull changes `pyproject.toml`, the result says so: an editable install picks up new code
for free but not new dependencies, and the environment would otherwise drift silently.

An upstream change means MIDI produced before and after is not guaranteed to match. Each
transcription records the version it was made with.

## Licence

The muscriptor **code** is MIT, and so is this wrapper. The **weights are CC BY-NC 4.0 —
non-commercial use only**, and the model card adds a condition on top: the output must not be
used for illegal or unauthorised activity, explicitly including transcribing music you hold no
rights to.

If you release music built on these transcriptions, that boundary is yours to judge. The app
states it rather than deciding it for you.
