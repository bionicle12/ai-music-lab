# Command line

[← Documentation](README.md) · [Русский](ru/cli.md)

Everything the interface does can be run directly. Run all commands from the repository root.

## lofcz

One file or a whole folder; the result is written to CSV:

```powershell
conda run -n ai-music-lofcz python ..\ai-music-detector\src\python\inference.py --model models\lofcz\ai_music_detector.onnx --input "path\to\stem.wav" --output artifacts\lofcz-result.csv
```

The timeline mode goes through this repository's adapter instead — see
[Timeline map](timeline.md#from-the-command-line).

## FST

One file; the result is printed and saved as JSON:

```powershell
conda run -n ai-music-fst python adapters\fst_cli.py --upstream ..\FST-AI-Music-Detection --stage1 models\fst\Stage-1.ckpt --stage2 models\fst\Stage-2.ckpt --audio "path\to\stem.wav" --json-output artifacts\fst-result.json
```

FST looks for beats and downbeats first. Full mixes, drums and rhythmic stems suit it best. On
vocals, ambience or anything without a detectable pulse the adapter exits with
`FST preprocessing found no beat-aligned segments` rather than recording a false `Real / NaN`.

`--backbone-batch` sets how many of the 48 segments go through the backbone at once. The default
of 8 peaks at 4.8 GB of VRAM; `0` sends all 48 in one pass as upstream does, at 16 GB and in the
same wall-clock time. The value used is recorded in the run's telemetry — it can move the raw
logit by one float16 ulp, so it is part of what produced the score. See
[what it costs to run](../README.md#what-it-costs-to-run).

## Smoke tests

```powershell
conda run -n ai-music-ui python -m pytest -q
conda run -n ai-music-ui python -m scripts.smoke_ui_pipeline artifacts\rhythm-smoke.wav
conda run -n ai-music-fst python -m pytest tests -v
conda run -n ai-music-fst python scripts\make_smoke_wav.py --kind rhythm --seconds 32 --output artifacts\rhythm-smoke.wav
conda run -n ai-music-fst python adapters\fst_cli.py --upstream ..\FST-AI-Music-Detection --stage1 models\fst\Stage-1.ckpt --stage2 models\fst\Stage-2.ckpt --audio artifacts\rhythm-smoke.wav --json-output artifacts\fst-smoke.json
conda run -n ai-music-lofcz python ..\ai-music-detector\src\python\inference.py --model models\lofcz\ai_music_detector.onnx --input artifacts\rhythm-smoke.wav --output artifacts\lofcz-smoke.csv
```

The synthetic file exists to prove the path works end to end. **Its score says nothing about
real model accuracy** — it is a generated rhythm, not music.

## muscriptor

The MIDI adapter has three modes. Set `HF_HOME` to the repo-local cache first; there is no
`--token` argument by design, so a gated download needs `HF_TOKEN` in the environment. Full
context: [Audio → MIDI](midi.md).

```powershell
$env:HF_HOME = "$PWD\models\muscriptor-cache"
conda run -n ai-music-muscriptor python adapters\muscriptor_cli.py --mode probe --upstream ..\muscriptor --json-output artifacts\muscriptor-probe.json
```

```powershell
conda run -n ai-music-muscriptor python adapters\muscriptor_cli.py --mode download --model small --json-output artifacts\muscriptor-download.json
```

```powershell
conda run -n ai-music-muscriptor python adapters\muscriptor_cli.py --mode transcribe --model small --audio artifacts\rhythm-smoke.wav --midi-output output\midi\smoke.mid --json-output artifacts\muscriptor-smoke.json
```

`small` is the right smoke target: it downloads quickly and still passes through the same gate
as the larger checkpoints. Progress is written to stdout as one JSON object per line; human
logging goes to stderr, so stdout stays parseable.

## Updating upstream

Update each repository separately, and only from a clean status:

```powershell
git -C ..\ai-music-detector status --short
git -C ..\ai-music-detector fetch origin
git -C ..\ai-music-detector pull --ff-only

git -C ..\FST-AI-Music-Detection status --short
git -C ..\FST-AI-Music-Detection fetch origin
git -C ..\FST-AI-Music-Detection pull --ff-only

git -C ..\muscriptor status --short
git -C ..\muscriptor fetch origin
git -C ..\muscriptor pull --ff-only
```

muscriptor is also updatable from the settings panel, which runs exactly that last block and
refuses on a dirty tree, a detached HEAD or a non-repository. The two detectors are not: they
are held at verified commits so their scores stay comparable, and moving them is a deliberate
act taken here rather than through a button.

If a muscriptor pull touches `pyproject.toml`, reinstall it — an editable install picks up new
code but not new dependencies:

```powershell
conda run -n ai-music-muscriptor python -m pip install -e ..\muscriptor
```

Re-run the smoke tests afterwards. Never commit wrapper files or checkpoints into an upstream
repository.

An upstream update invalidates comparability: scores produced before and after are not
guaranteed to be on the same scale. Note the new commit alongside any measurement you intend to
keep, and re-measure your reference material.

## Dependency snapshots

`environments/ai-music-lofcz.txt` and `environments/ai-music-fst.txt` are frozen snapshots of
what was actually installed when the pinned commits were verified.
