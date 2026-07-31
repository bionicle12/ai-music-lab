# Getting started

[← Documentation](README.md) · [Русский](ru/getting-started.md)

## What you need

| Requirement | Why |
| --- | --- |
| Windows | The launcher and paths are PowerShell-native; see [platform note](#platform-note) |
| NVIDIA GPU + driver | FST runs on CUDA; a 32-second file takes about 19 s on an RTX 4090 |
| [Conda](https://docs.conda.io/projects/miniconda/) | Each detector needs its own dependency set |
| Git | The two upstream detectors are cloned, not vendored |

Docker is not required. A global FFmpeg is not required either — every environment reads WAV,
FLAC and MP3 through the `soundfile` backend. Windows Developer Mode is optional; without it
the Hugging Face cache works without symlinks and takes slightly more disk space.

## 1. Clone the wrapper and both detectors

The two detectors live *next to* this repository, not inside it. The adapters expect that
layout by default.

```powershell
git clone https://github.com/bionicle12/ai-music-lab.git
git clone https://github.com/lofcz/ai-music-detector.git
git clone https://github.com/Mippia/FST-AI-Music-Detection.git
```

Your folder tree should end up like this:

```text
<parent>/
├── ai-music-lab/            # this repository
├── ai-music-detector/       # lofcz upstream
└── FST-AI-Music-Detection/  # FST upstream
```

## 2. Create the environments

Three Conda environments, because the detectors pin incompatible dependency sets. The UI
environment is the only one you need for the interface itself.

```powershell
cd ai-music-lab

conda create -n ai-music-ui python=3.11 -y
conda run -n ai-music-ui python -m pip install -r environments\ai-music-ui.txt

conda create -n ai-music-lofcz python=3.11 -y
conda run -n ai-music-lofcz python -m pip install -r environments\ai-music-lofcz.txt

conda create -n ai-music-fst python=3.11 -y
conda run -n ai-music-fst python -m pip install -r environments\ai-music-fst.txt
```

The `environments/*.txt` files are frozen snapshots of what is actually installed, not
hand-written minimums.

## 3. Download the models

Three checkpoint files go into `models/`. They are not in Git — see
**[Models](models.md)** for the official sources and the SHA-256 values to verify against.

```text
models/lofcz/ai_music_detector.onnx
models/fst/Stage-1.ckpt
models/fst/Stage-2.ckpt
```

## 4. Run it

```powershell
.\start_ui.ps1
```

Open `http://127.0.0.1:7860`. The launcher forces UTF-8 on the console and the Python child
process — without that, Windows PowerShell 5.1 turns non-ASCII interface text into mojibake.

## Language

The interface is built separately per language and served on its own path:

| Language | URL |
| --- | --- |
| English (default) | `http://127.0.0.1:7860/` |
| Russian | `http://127.0.0.1:7860/ru` |

The switcher sits under the title. Your choice is stored in the browser's `localStorage`, so
the next visit to `/` goes straight to the language you picked.

Two caveats worth knowing. `localStorage` is scoped to the exact origin, so
`http://localhost:7860` and `http://127.0.0.1:7860` keep **separate** choices, and changing
the port starts fresh. In a private window nothing is remembered at all — the default
language is served every time.

Switching reloads the page, because each language is a separately built interface. That is
what keeps everything translated, including Plotly axis titles and the generated detector
cards. Analyses already saved are untouched — reopen the run from the history.

## Your first analysis

1. Drop a WAV, FLAC or MP3 into the upload field — a mix, a stem, or a single layer.
2. Optionally add a note describing this version (`vocal stem after de-esser v2`).
3. Choose `lofcz`, `FST`, or both.
4. Press **Run analysis**.

Each run is saved to `data/runs/<run_id>/`, indexed in `data/history.sqlite3`. The `data/`
folder is git-ignored. Analysing one file does not create a baseline and does not compare it
against previous tracks — comparison is explicit, see [A/B comparison](comparison.md).

If you only want to confirm the plumbing works before finding real audio, generate a synthetic
file — see [Command line](cli.md#smoke-tests). Its score says nothing about model accuracy.

## Troubleshooting

**The language keeps resetting to English.** The choice lives in `localStorage`, which is
per-origin. Reaching the app through a different host spelling or port is a different origin,
and private windows never persist it.

**`/ru` shows a 404.** The locale mounts have to be registered before the root mount, which
`build_server()` does. If you mount the interface yourself, keep that order.

**Non-ASCII text shows as `????` or mojibake.** Launch through `start_ui.ps1` rather than
calling the module directly — the encoding setup lives in that script.

**`FST preprocessing found no beat-aligned segments`.** Not a bug. FST needs detectable
beats and downbeats; vocals, ambience and pads often have none. Use lofcz for that material.
See [Limitations](limitations.md).

**FST is slow on first run.** It downloads MERT weights into the Hugging Face cache once.

**Re-creating just the UI environment:**

```powershell
conda create -n ai-music-ui python=3.11 -y
conda run -n ai-music-ui python -m pip install -r environments\ai-music-ui.txt
```

## Platform note

Built and used on Windows with a single RTX 4090, and cross-platform support is not planned.
Nothing in the analysis code is deliberately Windows-only, but the launcher, the documented
commands and the paths all assume PowerShell and Conda, and no other platform is tested.

## Pinned environment

| Component | Version |
| --- | --- |
| lofcz upstream | `6ba389e94a179ac90f3eb134b741ef37baa30434` |
| FST upstream | `b564f8be8b3db6b7810c2aab61f0b4f86f889579` |
| Python | `3.11` |
| PyTorch / TorchAudio | `2.8.0+cu128` |
| Gradio | `6.20.0` |
| GPU | NVIDIA GeForce RTX 4090 |

TorchAudio is held at 2.8 deliberately: upstream uses the old `torchaudio.load` path, and from
2.9 onwards that path requires TorchCodec plus a separate full-shared FFmpeg build on Windows.
