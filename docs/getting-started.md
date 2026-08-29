# Getting started

[← Documentation](README.md) · [Русский](ru/getting-started.md)

## What you need

| Requirement | Why |
| --- | --- |
| Windows or Apple Silicon macOS | macOS currently supports UI, model-free analysis and lofcz |
| NVIDIA GPU + driver | Required for FST; a 32-second file takes about 19 s on an RTX 4090 |
| [Conda](https://docs.conda.io/projects/miniconda/) | Windows only; macOS uses project-local venvs |
| Git | The two upstream detectors are cloned, not vendored |

Docker is not required. A global FFmpeg is not required either — every environment reads WAV,
FLAC and MP3 through the `soundfile` backend. Windows Developer Mode is optional; without it
the Hugging Face cache works without symlinks and takes slightly more disk space.

> **From the interface instead.** Once the wrapper itself is cloned and the `ai-music-ui`
> environment exists (steps 1 and 2 below, for that one environment only), the rest can be done
> from inside the app: each detector has a gear beside its checkbox, and its dialog lists what is
> missing and offers to fetch it. Sections 1–3 are what that button does, written out — read them
> if you would rather do it yourself, or if a step fails and you want to know what it was trying.

### What the interface will and will not do for you

| Step | Automated? | |
| --- | --- | --- |
| `git clone` of the three upstreams | yes | Refused if the target folder already has files in it |
| Conda environment + pinned requirements | yes | Conda must already be installed; it will not install it |
| `models/lofcz/ai_music_detector.onnx` | yes | Verified against its published SHA-256 |
| `models/fst/Stage-1.ckpt`, `Stage-2.ckpt` | **no** | Google Drive serves files this size behind a confirmation page, so there is no stable direct link. The dialog prints both URLs and the exact destination paths; drop the files there and press **Check again** |
| muscriptor transcription weights | yes | Gated — needs a Hugging Face token, from the MIDI settings dialog |

If an environment refuses to build — a proxy, a resolver conflict, a locked file — the dialog
stops and hands you a ready-made prompt for a coding agent, with the commands, the paths and the
tail of the log already in it. Finish that one step however works, press **Check again**, and the
remaining steps carry on from there.

## Apple Silicon macOS quick start

Install Homebrew Python 3.11 and Git, then run from this repository:

```bash
chmod +x bootstrap_macos.sh start_ui.sh
./bootstrap_macos.sh
./start_ui.sh
```

The idempotent bootstrap creates `.venv-ui` and `.venv-lofcz`, clones both detector upstreams
next to this repository at the recorded commits, and downloads and verifies the lofcz ONNX
model. This milestone supports the UI, model-free metrics, and lofcz. FST/MPS and muscriptor
are not installed yet. The remaining numbered sections describe the full Windows setup.

## 1. Clone the wrapper and the upstreams

The upstream projects live *next to* this repository, not inside it. The adapters expect that
layout by default.

```powershell
git clone https://github.com/bionicle12/ai-music-lab.git
git clone https://github.com/lofcz/ai-music-detector.git
git clone https://github.com/Mippia/FST-AI-Music-Detection.git
git clone https://github.com/muscriptor/muscriptor.git
```

Your folder tree should end up like this:

```text
<parent>/
├── ai-music-lab/            # this repository
├── ai-music-detector/       # lofcz upstream
├── FST-AI-Music-Detection/  # FST upstream
└── muscriptor/              # audio → MIDI, optional
```

`muscriptor` is only needed for MIDI transcription — skip it if you only want detection.

## 2. Create the environments

Conda environments, because the upstreams pin incompatible dependency sets. The UI environment
is the only one you need for the interface itself.

```powershell
cd ai-music-lab

conda create -n ai-music-ui python=3.11 -y
conda run -n ai-music-ui python -m pip install -r environments\ai-music-ui.txt

conda create -n ai-music-lofcz python=3.11 -y
conda run -n ai-music-lofcz python -m pip install -r environments\ai-music-lofcz.txt

conda create -n ai-music-fst python=3.11 -y
conda run -n ai-music-fst python -m pip install -r environments\ai-music-fst.txt
```

For MIDI transcription, a fourth environment. muscriptor is installed **editable from the
clone**, so a later `git pull` updates the code that actually runs — see
[Audio → MIDI](midi.md). It is another full torch install, roughly 2.5 GB on disk.

```powershell
conda create -n ai-music-muscriptor python=3.11 -y
conda run -n ai-music-muscriptor python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
conda run -n ai-music-muscriptor python -m pip install -e ..\muscriptor
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

The full FST and muscriptor stack is built and measured on Windows with a single RTX 4090.
Apple Silicon macOS supports the UI, model-free analysis, and lofcz through the bootstrap above.
FST/MPS and muscriptor remain follow-up milestones.

## Pinned environment

| Component | Version |
| --- | --- |
| lofcz upstream | `6ba389e94a179ac90f3eb134b741ef37baa30434` |
| FST upstream | `b564f8be8b3db6b7810c2aab61f0b4f86f889579` |
| muscriptor upstream | `e2bd0fc5994f9acba7c1387ca5df67eb8d95df44` (`0.2.2`) |
| Python | `3.11` |
| PyTorch / TorchAudio | `2.8.0+cu128` in the detector environments |
| Gradio | `6.20.0` |
| GPU | NVIDIA GeForce RTX 4090 |

TorchAudio is held at 2.8 deliberately: upstream uses the old `torchaudio.load` path, and from
2.9 onwards that path requires TorchCodec plus a separate full-shared FFmpeg build on Windows.
The muscriptor environment is separate and unaffected, so it takes a current torch.

The two detector commits are *pins*: their scores are only comparable across runs if the code
that produced them did not change. muscriptor is not pinned in the same sense — its commit is
the version the wrapper was verified against, and Settings can fast-forward it.
