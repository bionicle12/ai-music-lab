# Setting up with an AI agent

[← Documentation](README.md) · [Русский](ru/agent-setup.md)

The setup is mechanical but fiddly: three repositories side by side, three Conda environments,
three checkpoint files in exact locations. If you use a coding agent (Claude Code, Codex,
Cursor, …), the prompts below hand it the whole job.

Everything here can also be done by hand — see [Getting started](getting-started.md). The
prompts are a convenience, not a requirement.

## What an agent cannot do for you

**The two FST checkpoints live on Google Drive and need a human.** Google Drive blocks
scripted downloads of large files behind a confirmation page, so an agent cannot reliably
fetch `Stage-1.ckpt` (1.2 GB) or `Stage-2.ckpt`. Download those two yourself; the agent can
verify them afterwards. The lofcz ONNX model is on Hugging Face with a direct URL and *can* be
fetched automatically.

Also worth knowing before you hand over control: the agent will create Conda environments and
clone two external repositories. Read the prompt before you run it, and keep the guardrail
about never modifying the upstream repositories — that rule is what keeps your measurements
reproducible.

## Prompt 1 — full setup from scratch

Paste this into an agent working inside the `ai-music-lab` folder.

```text
Set up this project (ai-music-lab) so its interface runs. Work on Windows with
PowerShell and Conda. Follow these steps exactly and stop to report if any step
fails.

HARD RULES
- Never modify, commit into, or reformat anything inside the two upstream
  detector repositories. They are read-only dependencies. This project is a
  wrapper and depends on them staying untouched.
- Do not upgrade pinned dependency versions. The environments/*.txt files are
  frozen snapshots that match the pinned upstream commits.
- Do not invent download URLs. Use only the ones in models/sources.json.

STEP 1 — clone the two detectors NEXT TO this repository, not inside it.
The target layout is:
    <parent>/
    ├── ai-music-lab/            (this repository)
    ├── ai-music-detector/       (lofcz upstream)
    └── FST-AI-Music-Detection/  (FST upstream)
Commands, run from the parent folder:
    git clone https://github.com/lofcz/ai-music-detector.git
    git clone https://github.com/Mippia/FST-AI-Music-Detection.git

STEP 2 — pin both upstreams to the commits this wrapper was verified against:
    git -C ..\ai-music-detector checkout 6ba389e94a179ac90f3eb134b741ef37baa30434
    git -C ..\FST-AI-Music-Detection checkout b564f8be8b3db6b7810c2aab61f0b4f86f889579
A detached HEAD here is expected and correct.

STEP 3 — create three Conda environments, all Python 3.11. They are separate
because the detectors pin incompatible dependency sets:
    conda create -n ai-music-ui python=3.11 -y
    conda run -n ai-music-ui python -m pip install -r environments\ai-music-ui.txt
    conda create -n ai-music-lofcz python=3.11 -y
    conda run -n ai-music-lofcz python -m pip install -r environments\ai-music-lofcz.txt
    conda create -n ai-music-fst python=3.11 -y
    conda run -n ai-music-fst python -m pip install -r environments\ai-music-fst.txt

STEP 4 — download the lofcz model. The URL is in models/sources.json. Save it to
    models\lofcz\ai_music_detector.onnx
Then verify with Get-FileHash -Algorithm SHA256. Expected:
    af7a75c6ed457bc5b6941c8bc76aa06a66d48de40db944b761ed2bebfc0fbbd3
If the hash does not match, stop and report it. Do not continue with a file you
cannot verify.

STEP 5 — the two FST checkpoints CANNOT be downloaded automatically (Google
Drive blocks scripted access). Print these instructions and wait for me:
    Stage-1.ckpt -> models\fst\Stage-1.ckpt
      https://drive.google.com/file/d/1frT4Mn0l6rso407Sy3eWCKbZmgwuVceN/view
      expected SHA-256 f9099df5c618a2f92bcd8f4ba48d1c6606f2e4610385b8eea4a03f1a7319629f
    Stage-2.ckpt -> models\fst\Stage-2.ckpt
      https://drive.google.com/file/d/1E_xPsosYWI4UjKT8XQCbZW4ILvsWnmda/view
      expected SHA-256 ed133c261c5d367fc6adf53813a5c93b62a59de5bef546cf5899a5c157eba7a0
After I confirm they are in place, verify both hashes.

STEP 6 — verify the installation:
    conda run -n ai-music-ui python -m pytest -q
    conda run -n ai-music-fst python scripts\make_smoke_wav.py --kind rhythm --seconds 32 --output artifacts\rhythm-smoke.wav
    conda run -n ai-music-lofcz python ..\ai-music-detector\src\python\inference.py --model models\lofcz\ai_music_detector.onnx --input artifacts\rhythm-smoke.wav --output artifacts\lofcz-smoke.csv
    conda run -n ai-music-fst python adapters\fst_cli.py --upstream ..\FST-AI-Music-Detection --stage1 models\fst\Stage-1.ckpt --stage2 models\fst\Stage-2.ckpt --audio artifacts\rhythm-smoke.wav --json-output artifacts\fst-smoke.json
The smoke file is synthetic. Its score proves the pipeline runs and says nothing
about model accuracy — do not interpret it.

STEP 7 — write artifacts\model-manifest.json:
    conda run -n ai-music-fst python scripts\write_model_manifest.py --output artifacts\model-manifest.json models\lofcz\ai_music_detector.onnx models\fst\Stage-1.ckpt models\fst\Stage-2.ckpt

Then report: which steps succeeded, any hash mismatches, and the exact command to
start the interface.
```

## Prompt 2 — diagnose a broken installation

When something used to work and no longer does.

```text
Diagnose this ai-music-lab installation without changing anything until you have
reported findings. Check, in order:

1. Do ..\ai-music-detector and ..\FST-AI-Music-Detection exist as siblings of
   this folder?
2. Is each one clean and on the pinned commit?
     git -C ..\ai-music-detector rev-parse HEAD    -> 6ba389e94a179ac90f3eb134b741ef37baa30434
     git -C ..\FST-AI-Music-Detection rev-parse HEAD -> b564f8be8b3db6b7810c2aab61f0b4f86f889579
   Report any local modification: an edited upstream invalidates comparability
   with previously saved runs.
3. Do all three Conda environments exist, and is each one on Python 3.11?
     conda env list
4. Are all three model files present, and do their SHA-256 hashes match
   docs\models.md?
5. Does the test suite pass?  conda run -n ai-music-ui python -m pytest -q
6. Is torchaudio still at 2.8.x in ai-music-lofcz and ai-music-fst? Version 2.9
   and later require TorchCodec plus a full-shared FFmpeg build on Windows and
   will break the detectors.

Report what is wrong and what you propose to fix, then wait for my approval
before making any change.
```

## Prompt 3 — update the upstream detectors

Only when you actually want newer detector code, and knowing it breaks
comparability with runs you already saved.

```text
Update the two upstream detector repositories for ai-music-lab.

Before anything: confirm both repositories are clean. If either has local
changes, stop and show me the diff — this project never modifies upstream, so
local changes mean something went wrong earlier.

    git -C ..\ai-music-detector status --short
    git -C ..\ai-music-detector fetch origin
    git -C ..\ai-music-detector pull --ff-only

    git -C ..\FST-AI-Music-Detection status --short
    git -C ..\FST-AI-Music-Detection fetch origin
    git -C ..\FST-AI-Music-Detection pull --ff-only

Then re-run the smoke tests from docs\cli.md and report the new commit hashes.

Finally, remind me in your summary that scores produced before and after this
update are not guaranteed to sit on the same scale, so I should re-measure my
reference material and note the new commit next to any measurement I keep.
```

## Environments in a non-default location

The adapters look for the detector environments as siblings of the running
interpreter — that is, in the standard Conda `envs` directory. If yours live elsewhere, point
the project at them instead of moving anything:

```powershell
$env:AI_MUSIC_LOFCZ_PYTHON = "D:\envs\ai-music-lofcz\python.exe"
$env:AI_MUSIC_FST_PYTHON   = "D:\envs\ai-music-fst\python.exe"
```

`AI_MUSIC_UI_HOST` and `AI_MUSIC_UI_PORT` move the interface off `127.0.0.1:7860`. Changing
the port gives the browser a new origin, so the remembered language resets.

## Verifying the result yourself

Whatever the agent reports, these three checks are the ones that matter:

```powershell
git -C ..\ai-music-detector rev-parse HEAD
git -C ..\FST-AI-Music-Detection rev-parse HEAD
Get-FileHash models\fst\Stage-1.ckpt -Algorithm SHA256
conda run -n ai-music-ui python -m pytest -q
```

If the commits match, the hashes match and the tests pass, the installation is sound.
