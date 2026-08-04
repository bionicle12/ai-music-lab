<p align="right"><b>English</b> · <a href="README.ru.md">Русский</a></p>

<p align="center">
  <img src="./assets/readme/hero.svg" width="100%"
       alt="AI Music Lab — a local forensic audio workspace running two open AI-music detectors, with a time-frequency panel marking the window that carries the strongest fingerprint">
</p>

<p align="center">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-23b7e5?style=flat-square">
  <img alt="Platform Windows, macOS planned" src="https://img.shields.io/badge/platform-Windows%20%C2%B7%20macOS%20planned-91a3b3?style=flat-square">
  <img alt="Python 3.11" src="https://img.shields.io/badge/python-3.11-4bd19b?style=flat-square">
  <img alt="CUDA 12.8" src="https://img.shields.io/badge/CUDA-12.8-4bd19b?style=flat-square">
  <img alt="Tests 356 passing" src="https://img.shields.io/badge/tests-356%20passing-4bd19b?style=flat-square">
</p>

You finished a track, and something about it still sounds *generated* — but a single
percentage from a detector will not tell you which part. **AI Music Lab** runs two open
AI-music detectors on your own machine and adds what they are missing: a map of **where**
the fingerprint sits, and an A/B history that shows whether your edit actually moved the
number.

Drop in a mix, a stem, or a single layer. Get a score from each detector, a ranking of which
layers carry the most, a timeline of which seconds are strongest, and signal measurements
that stay meaningful even when the two models disagree.

<p align="center">
  <a href="https://github.com/bionicle12/ai-music-lab/raw/refs/heads/main/assets/readme/demo.mp4">
    <img src="./assets/readme/demo.webp" width="100%"
         alt="A real run in the AI Music Lab interface: lofcz and FST score cards side by side, both reading high, an interactive spectrogram with a hover readout, and the sliding-window timeline map">
  </a>
</p>

<p align="center"><sub>
  A looping preview of the first 12 seconds ·
  ▶ <a href="https://github.com/bionicle12/ai-music-lab/raw/refs/heads/main/assets/readme/demo.mp4"><b>full 30-second run (MP4, 1.8 MB)</b></a>
</sub></p>

## How it works

Two detectors and one set of model-free signal metrics measure the file. Four views turn
those measurements into something you can act on. Every run is written to disk, so any two
runs of the same source can be compared later.

<p align="center">
  <img src="./assets/readme/pipeline.svg" width="100%"
       alt="Four stages: one audio file goes in; lofcz, FST and model-free signal metrics measure it; layer ranking, timeline map, artifact metrics and detector telemetry localize the result; version B is compared against version A">
</p>

The part that makes this more than a wrapper is stage 3. `lofcz` and `FST` each return one
number for a whole track, which is useless as production feedback. Splitting the same track
by **layer** (drums 97%, live guitar 15%) and by **time window** tells you what to re-record
first. The **artifact metrics** — attack sharpness, 95% rolloff, high-frequency slope, noise
floor, channel correlation — are computed straight from the signal with no model involved,
so they keep working when a detector goes outside its training domain.

## What it costs to run

Every figure below was measured on the machine this was built on — Windows, RTX 4090 (24 GB),
CUDA 12.8 — by sampling total GPU memory while one adapter ran alone. The test file is a 3:26
stereo track at 44.1 kHz.

| Stage | GPU memory | Time | Grows with track length? |
| --- | ---: | ---: | --- |
| Interface, charts, artifact metrics | none — CPU only | seconds | time only |
| lofcz | 0.5 GB | 8 s | barely |
| FST | **16 GB** | 25 s | **neither** |
| muscriptor `large` | 11 GB | 50 s per 30 s of audio | time only |
| muscriptor `medium` / `small` | not measured | — | — |

Two of those rows need explaining, because both are counter-intuitive.

**FST sets the floor, and it does not care how long your track is.** It always runs 48
ten-second segments: a short file is padded up to 48 rather than run as fewer. A 32-second file
and an eight-minute file cost the same 16 GB — measured, not assumed. That is how the upstream
batches, not a knob this wrapper can turn. The practical consequence: **a card below 24 GB runs
everything here except FST**, and 12 GB is a perfectly good machine for lofcz, the artifact
metrics, the timeline map and MIDI export.

**muscriptor spends length on time, not on memory.** It transcribes in five-second chunks, so a
three-minute track is around forty of them — expect minutes, not seconds. `large` is 1.4B
parameters in fp32. `medium` and `small` exist precisely for smaller cards, and their downloads
are 1.2 GB and 0.4 GB against 5.6 GB, but I have only measured `large` and will not publish a
number I did not take.

Disk: ~1.4 GB for the two detector checkpoints, ~0.6 GB for the MERT embeddings FST fetches on
its first run, and 0.4–5.6 GB for whichever transcription weights you download. The transcription
cache is redirected into `models/muscriptor-cache/` so gigabytes do not land on the system drive.

Host RAM is not the constraint on Windows — the interface itself sits around 0.3 GB and the
checkpoints live on the GPU. It becomes the constraint on Apple Silicon, where the two are one
pool; see [Platform](#platform).

## Quick start

Windows with an NVIDIA GPU, [Conda](https://docs.conda.io/projects/miniconda/), and Git.

### How the pieces fit together

This repository contains no detector or transcription code. Every upstream is cloned **next to**
it and left completely untouched:

```text
<parent>/
├── ai-music-lab/            ← this repository: UI, adapters, history
├── ai-music-detector/       ← lofcz upstream, pinned at 6ba389e
├── FST-AI-Music-Detection/  ← FST upstream, pinned at b564f8b
└── muscriptor/              ← audio → MIDI, tracks main (optional)
```

Keeping them as separate, unmodified clones is deliberate. A measurement is only reproducible
if you can say exactly which detector code produced it, and a patched upstream silently
invalidates every score you saved before the patch. It also means you can update either
detector on its own, or check what upstream actually does, without untangling it from wrapper
code.

Three Conda environments, all Python 3.11, because the two detectors pin incompatible
dependency sets:

| Environment | Used for |
| --- | --- |
| `ai-music-ui` | The interface and everything model-free |
| `ai-music-lofcz` | The lofcz detector |
| `ai-music-fst` | The FST detector |

Model weights are **not** in Git. They go into `models/`, downloaded from their official
sources:

| File | Source | Automatable? |
| --- | --- | --- |
| `models/lofcz/ai_music_detector.onnx` | Hugging Face | yes, direct URL |
| `models/fst/Stage-1.ckpt` | Google Drive | no — download manually |
| `models/fst/Stage-2.ckpt` | Google Drive | no — download manually |

Every file has a published SHA-256 in **[Models](docs/models.md)**. Verify before you trust
any measurement made with it.

### Install

```powershell
git clone https://github.com/bionicle12/ai-music-lab.git
git clone https://github.com/lofcz/ai-music-detector.git
git clone https://github.com/Mippia/FST-AI-Music-Detection.git

cd ai-music-lab
conda create -n ai-music-ui python=3.11 -y
conda run -n ai-music-ui python -m pip install -r environments\ai-music-ui.txt
```

Then create the two detector environments, download the three model files, and start it:

```powershell
.\start_ui.ps1
```

Open `http://127.0.0.1:7860`, drop in an audio file, pick the detectors, and press
**Run analysis**. The full step-by-step, including pinning the upstream commits and the
smoke tests, is in **[Getting started](docs/getting-started.md)**.

> **Prefer to delegate it?** **[Setting up with an AI agent](docs/agent-setup.md)** has
> copy-paste prompts that walk a coding agent through the whole installation, plus prompts for
> diagnosing a broken install and updating upstream safely.

> **Languages.** The interface is served in English at `/` and in Russian at `/ru`. The
> switcher sits under the title and your choice is remembered in the browser.

## Documentation

| Page | What it covers |
| --- | --- |
| [Getting started](docs/getting-started.md) | Environments, models, first run, troubleshooting |
| [AI agent setup](docs/agent-setup.md) | Copy-paste prompts to install, diagnose and update |
| [Models](docs/models.md) | Official download sources, sizes, verified SHA-256 |
| [Analysis](docs/analysis.md) | The single-file run: spectrum, 3D surface, player sync |
| [Layers](docs/layers.md) | Ranking stems to find what to re-record first |
| [Timeline map](docs/timeline.md) | Sliding-window localization inside one track |
| [Artifact metrics](docs/artifact-metrics.md) | Model-free measurements straight from the signal |
| [A/B comparison](docs/comparison.md) | Pinning version A and measuring what an edit changed |
| [Detector data](docs/detector-data.md) | Native telemetry from lofcz and FST |
| [Audio → MIDI](docs/midi.md) | Transcription setup, the token, the weights and their licence |
| [Editing roadmap](docs/editing-roadmap.md) | What repairing a generated stem would have to do |
| [Command line](docs/cli.md) | Running the adapters without the UI, smoke tests |
| [Limitations](docs/limitations.md) | What the numbers do and do not mean — read this one |
| [A few honest words](docs/about.md) | Why this exists, and what it is not for |

## Roadmap

The lab can measure a track and now get MIDI out of it. What it cannot do yet is *repair*
anything, and that is the direction.

**SunoFix — repairing generated stems.** Suno and its neighbours leave recognisable damage:
smeared transients, a hard ceiling in the top octave, artefacts that surface under dense
sections, stems that were never truly separate. The plan is a repair pass aimed at those named
faults on a single stem, not a general "enhance" button — and held to the same discipline as
everything else here: measure the stem, repair it, and let the A/B comparison say whether the
number actually moved. The groundwork is already in place, because the artifact metrics were
chosen to be exactly the measurements such a pass has to improve. Current thinking:
**[Editing roadmap](docs/editing-roadmap.md)**.

**More detectors, on the same terms.** Every detector here is an unmodified upstream clone
pinned at a commit, so adding one is a matter of an adapter and an environment rather than of
vendoring somebody's code. Two models that disagree already tell you more than one; four will
tell you more than two.

**Per-detector configuration in the interface.** Thresholds, window and segment lengths, and
device choice currently live in adapter defaults. They belong in the settings panel, saved per
detector and recorded into the run — a saved score should always be able to say which settings
produced it.

**macOS.** Planned, not promised, and gated on hardware — see just below.

## What this is not

A detector score is a measurement tied to a version of code, weights, an input file and the
conditions of the run. **It is not proof of where a track came from**, and this project will
not tell you otherwise.

- Compare like with like. MP3 rolls off high frequencies on its own, so MP3 against WAV shows
  the codec, not the generator.
- `FST` needs detectable beats. On vocals or ambience it returns a clear "not applicable"
  rather than a fake number.
- The timeline map is a *relative* map inside one track, not a calibrated per-second
  probability.
- A low score from one model and a high score from the other is a real disagreement worth
  keeping, not a bug to average away.

The full reasoning is in **[Limitations](docs/limitations.md)**.

And no, this is not a tool for fooling detectors — I wrote down why, along with how the
project came about, in **[A few honest words](docs/about.md)**.

## Built on

This repository is a wrapper. It does not modify, vendor or redistribute any upstream — each is
cloned separately and recorded at a known commit.

| Upstream | Commit | License |
| --- | --- | --- |
| [lofcz/ai-music-detector](https://github.com/lofcz/ai-music-detector) | `6ba389e` | MIT |
| [Mippia/FST-AI-Music-Detection](https://github.com/Mippia/FST-AI-Music-Detection) | `b564f8b` | none declared upstream |
| [muscriptor/muscriptor](https://github.com/muscriptor/muscriptor) | `e2bd0fc` | MIT code · **weights CC BY-NC 4.0** |

The two detector commits are pins — a score is only comparable across runs if the code behind it
did not move. muscriptor's is the version this wrapper was verified against; it tracks `main` and
can be fast-forwarded from the settings panel.

**The muscriptor weights are non-commercial.** The code is MIT, the checkpoints are not, and the
model card adds a condition on top: the output must not be used for illegal or unauthorised
activity, transcribing music you hold no rights to included. See
[Audio → MIDI](docs/midi.md).

## Platform

Built and used on Windows with a single RTX 4090. Commands, paths and scripts are PowerShell-
and Conda-native. Everything runs locally; no audio is uploaded anywhere.

**macOS is planned**, and worth being precise about. Two things have to happen. The adapters ask
for CUDA by name — FST refuses to start without it — so the port means an MPS path through each
adapter and the PowerShell scripts in a portable form. The harder half is memory: Apple Silicon
shares one pool between CPU and GPU, so FST's fixed 16 GB working set is 16 GB of everything the
machine has. A 16 GB MacBook will not run that detector; 32 GB is the realistic bar for it, while
the rest of the lab is comfortable far below. It happens when there is a Mac here to test on — a
port nobody has run is not support.

## License

[MIT](LICENSE) © 2026 Miroslav. The wrapper is MIT.

**Every other product this workspace touches carries its own terms — read them, and do not
break the law with what you make here.** The upstream detectors, the transcription weights, the
vendored fonts and any sample pack or plugin you bring in are all licensed by their own authors,
not by this repository. The one that will catch you out first is muscriptor: its code is MIT but
its **weights are CC BY-NC 4.0, non-commercial only**, with a further condition against
transcribing music you hold no rights to. The interface states that where it matters; the full
list is in the table above and in [docs/models.md](docs/models.md).

<p align="center">from Russia with ❤️</p>
