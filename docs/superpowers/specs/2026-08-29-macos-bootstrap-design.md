# macOS Bootstrap and lofcz Support Design

## Goal

Make AI Music Lab usable on the current Apple Silicon Mac in a stable first
milestone: launch the web interface, run all model-free analysis, and run the
`lofcz` detector. Preserve the existing Windows and CUDA workflow.

FST-on-MPS and muscriptor are explicitly deferred to later milestones. The FST
adapter already supports lowering CUDA memory use by slicing its 48 segments;
the later MPS milestone will retain that control and target a measured unified
memory budget of 12–14 GB on this Mac rather than assuming CUDA measurements
transfer directly to MPS.

## Current Constraints

- The machine is Apple Silicon (`arm64`) with 24 GB unified memory.
- Homebrew Python 3.11 is available at `/opt/homebrew/bin/python3.11`.
- Conda is not installed.
- Existing dependency snapshots contain Windows-only and CUDA-only packages,
  including `pyreadline3`, `onnxruntime-gpu`, and `torch` wheels with a
  `+cu128` build suffix.
- Default detector interpreter paths end in `python.exe` and assume Conda's
  named-environment layout.
- The only launcher is a PowerShell script.
- Upstream repositories intentionally remain pristine sibling clones at known
  commits.

## Selected Approach

Use standard Python virtual environments for the macOS installation:

```text
<parent>/
├── ai-music-lab/
│   ├── .venv-ui/
│   └── .venv-lofcz/
├── ai-music-detector/
└── FST-AI-Music-Detection/
```

The upstream detector repositories remain siblings and are checked out at the
commits already recorded by the project. The FST repository is cloned now so
the installation layout is complete, but its environment, model checkpoints,
and execution path are not part of this milestone.

This approach avoids installing a new package manager on the machine and keeps
the macOS setup isolated inside the project. Environment-variable overrides
remain supported for users who keep environments elsewhere.

## Components and Changes

### Platform-aware paths

`LabPaths` will resolve detector interpreters in this order:

1. `AI_MUSIC_*_PYTHON`, when explicitly set.
2. Project-local macOS/Linux virtual environments such as
   `.venv-lofcz/bin/python`.
3. The existing Conda-style Windows defaults.

The implementation will isolate path selection in a small function that can be
unit-tested for Windows and POSIX layouts without depending on the host OS.

### macOS dependency snapshots

Add dedicated requirement files for the UI and lofcz environments. They will
retain the versions used by the project where compatible, while replacing:

- `onnxruntime-gpu` with `onnxruntime` on Apple Silicon;
- CUDA-specific Torch/TorchAudio wheels with native macOS ARM wheels;
- Windows-only `pyreadline3` with no macOS equivalent.

The UI environment will not install Torch because model-free analysis and the
Gradio application do not require it. The lofcz environment will contain its
own native Torch/TorchAudio stack and ONNX Runtime.

### Bootstrap and launcher

Add a checked-in macOS bootstrap script that:

- validates Python 3.11 and Git;
- creates `.venv-ui` and `.venv-lofcz` idempotently;
- installs the corresponding macOS dependencies;
- refuses to overwrite occupied sibling clone directories;
- clones the two detector repositories when absent;
- checks out their recorded commits without modifying an existing dirty clone;
- downloads the automatable lofcz ONNX file only when absent;
- verifies its published SHA-256 checksum;
- prints precise manual recovery instructions on failure.

Add `start_ui.sh`, which resolves the repository root, sets UTF-8 behavior, and
executes `.venv-ui/bin/python -m music_lab_ui.app`. It will fail early with a
helpful message if bootstrap has not completed.

### Documentation

Document a macOS quick start, the supported first-milestone features, and the
fact that FST/MPS and muscriptor are deferred. Windows instructions remain
unchanged.

## Data and Execution Flow

The user runs the bootstrap script once. It creates both environments, prepares
the sibling clones, downloads and verifies the lofcz weight, and runs a compact
installation check. The user then runs `start_ui.sh` and opens the existing
Russian or English URL.

When lofcz is selected, the UI launches the adapter using
`.venv-lofcz/bin/python`. The adapter imports the pristine sibling upstream and
uses native macOS Torch plus CPU ONNX Runtime. Model-free UI analysis remains in
the UI environment.

## Error Handling and Safety

- Existing non-empty clone targets are never overwritten.
- Existing dirty upstream clones are reported and left untouched.
- Existing model files are verified rather than silently replaced.
- Downloads use a temporary partial file and become visible at the final path
  only after a successful checksum verification.
- Scripts use absolute paths derived from their own location and do not depend
  on the caller's working directory.
- Bootstrap failures leave already completed steps reusable on the next run.

## Verification

Implementation follows test-driven development for platform path behavior and
any new bootstrap logic that is practical to isolate.

Completion requires:

1. Existing Python tests pass in `.venv-ui`.
2. New path-selection tests pass for POSIX and Windows cases.
3. Both upstream commit hashes match the recorded pins.
4. The lofcz model SHA-256 matches `models/sources.json`.
5. The smoke WAV generator succeeds.
6. The lofcz adapter analyzes the smoke WAV successfully.
7. The UI starts on `127.0.0.1:7860` and responds over HTTP.

## Deferred Milestones

### FST on MPS

Add explicit device selection (`cuda`, `mps`, or `cpu` where supported), native
ARM dependencies, MPS-safe checkpoint loading, and a configurable segment batch
size. Measure real unified-memory use on this Mac and tune the default to stay
within a 12–14 GB budget. The existing RTX 4090 result (approximately 4.8 GB at
a segment batch of eight versus 16 GB upstream) is a useful baseline, not an
MPS guarantee.

### muscriptor on macOS

Add a separate native environment, MPS device support where upstream permits,
and preserve the existing license/token acceptance flow. This remains optional
and does not block detector use.
