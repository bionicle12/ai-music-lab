# macOS Bootstrap and lofcz Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Launch AI Music Lab on Apple Silicon with model-free analysis and the lofcz detector using project-local Python 3.11 virtual environments.

**Architecture:** Keep upstream repositories as pristine sibling clones and keep the Windows/Conda path intact. Add platform-aware interpreter resolution, macOS-specific dependency snapshots, a testable Python bootstrap utility with a thin shell entry point, and a POSIX UI launcher.

**Tech Stack:** Python 3.11, `venv`, pip, Bash, Gradio/FastAPI, PyTorch/TorchAudio for macOS ARM, ONNX Runtime CPU, pytest, Git.

**Spec:** `docs/superpowers/specs/2026-08-29-macos-bootstrap-design.md`

## Global Constraints

- Target machine: Apple Silicon `arm64`, macOS 26.5, 24 GB unified memory.
- Use `/opt/homebrew/bin/python3.11`; do not install Conda or another package manager.
- Preserve the existing Windows/CUDA/PowerShell workflow.
- Never overwrite non-empty sibling repository directories, dirty upstream clones, or existing model files.
- Pin `ai-music-detector` to `6ba389e94a179ac90f3eb134b741ef37baa30434`.
- Pin `FST-AI-Music-Detection` to `b564f8be8b3db6b7810c2aab61f0b4f86f889579`.
- Verify the lofcz model SHA-256 as `af7a75c6ed457bc5b6941c8bc76aa06a66d48de40db944b761ed2bebfc0fbbd3`.
- FST execution and muscriptor are deferred; cloning FST is included only to complete the sibling layout.
- Follow test-driven development: observe every behavior test fail before production code is added.

---

### Task 1: Platform-aware detector interpreter paths

**Files:**
- Modify: `tests/test_ui_config.py`
- Modify: `music_lab_ui/config.py`

**Interfaces:**
- Produces: `environment_python(root: Path, environment_name: str, environ: Mapping[str, str], override_name: str, os_name: str) -> Path`
- Consumed by: `LabPaths.from_root()` for lofcz, FST, and muscriptor interpreter paths.

- [ ] **Step 1: Write failing POSIX and compatibility tests**

Add tests that call the desired helper directly so host platform state does not make the assertions conditional:

```python
def test_project_local_posix_environment_is_the_default(tmp_path: Path) -> None:
    assert environment_python(
        tmp_path,
        "ai-music-lofcz",
        {},
        "AI_MUSIC_LOFCZ_PYTHON",
        "posix",
    ) == tmp_path / ".venv-lofcz" / "bin" / "python"


def test_windows_conda_default_is_preserved(tmp_path: Path) -> None:
    assert environment_python(
        tmp_path,
        "ai-music-lofcz",
        {},
        "AI_MUSIC_LOFCZ_PYTHON",
        "nt",
        envs_dir=tmp_path / "conda" / "envs",
    ) == tmp_path / "conda" / "envs" / "ai-music-lofcz" / "python.exe"


def test_interpreter_override_wins_on_every_platform(tmp_path: Path) -> None:
    chosen = tmp_path / "custom-python"
    assert environment_python(
        tmp_path,
        "ai-music-fst",
        {"AI_MUSIC_FST_PYTHON": str(chosen)},
        "AI_MUSIC_FST_PYTHON",
        "posix",
    ) == chosen
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3.11 -m pytest tests/test_ui_config.py -q`

Expected: collection fails because `environment_python` does not exist.

- [ ] **Step 3: Implement the minimal resolver and use it from `LabPaths`**

Implement a pure helper with an optional `envs_dir` argument. Map named environments to local directories by removing the `ai-music-` prefix: `ai-music-lofcz` becomes `.venv-lofcz`. On POSIX return `<root>/.venv-<name>/bin/python`; on Windows retain `<envs_dir>/<environment_name>/python.exe`. Explicit environment-variable paths always win.

- [ ] **Step 4: Run focused and regression tests**

Run: `python3.11 -m pytest tests/test_ui_config.py -q`

Expected: all config tests pass.

- [ ] **Step 5: Commit**

```bash
git add music_lab_ui/config.py tests/test_ui_config.py
git commit -m "feat: resolve local venvs on macOS"
```

### Task 2: macOS dependency snapshots

**Files:**
- Create: `environments/ai-music-ui-macos.txt`
- Create: `environments/ai-music-lofcz-macos.txt`
- Create: `tests/test_macos_requirements.py`

**Interfaces:**
- Produces: two pip-installable UTF-8 requirement files consumed by the bootstrap utility.
- The UI snapshot must provide imports used by `music_lab_ui` and pytest without installing Torch.
- The lofcz snapshot must provide upstream inference imports with native `torch==2.8.0`, `torchaudio==2.8.0`, and CPU `onnxruntime`.

- [ ] **Step 1: Write failing snapshot-policy tests**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def requirement_text(name: str) -> str:
    return (ROOT / "environments" / name).read_text(encoding="utf-8-sig")


def test_macos_ui_snapshot_has_no_windows_or_cuda_packages() -> None:
    text = requirement_text("ai-music-ui-macos.txt")
    assert "gradio==6.20.0" in text
    assert "pytest==9.1.1" in text
    assert "pyreadline3" not in text
    assert "+cu128" not in text


def test_macos_lofcz_snapshot_uses_native_runtime_packages() -> None:
    text = requirement_text("ai-music-lofcz-macos.txt")
    assert "onnxruntime==" in text
    assert "onnxruntime-gpu" not in text
    assert "torch==2.8.0" in text
    assert "torchaudio==2.8.0" in text
    assert "pyreadline3" not in text
    assert "+cu128" not in text
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3.11 -m pytest tests/test_macos_requirements.py -q`

Expected: both tests fail with `FileNotFoundError`.

- [ ] **Step 3: Create the snapshots**

Create `ai-music-ui-macos.txt` from the existing UI snapshot, preserving all versions and removing only `pyreadline3`. Create `ai-music-lofcz-macos.txt` from the existing lofcz snapshot with these exact substitutions:

```text
onnxruntime-gpu==1.28.0  -> onnxruntime==1.28.0
torch==2.8.0+cu128      -> torch==2.8.0
torchaudio==2.8.0+cu128 -> torchaudio==2.8.0
```

Remove `pyreadline3==3.5.4`; leave all other lines and versions unchanged.

- [ ] **Step 4: Run the policy tests**

Run: `python3.11 -m pytest tests/test_macos_requirements.py -q`

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add environments/ai-music-ui-macos.txt environments/ai-music-lofcz-macos.txt tests/test_macos_requirements.py
git commit -m "build: add macOS dependency snapshots"
```

### Task 3: Safe, idempotent macOS bootstrap utility

**Files:**
- Create: `scripts/bootstrap_macos.py`
- Create: `tests/test_bootstrap_macos.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `RepositorySpec`, `sha256(path: Path) -> str`, `validate_clone_target(path: Path) -> None`, `validate_existing_clone(path: Path, commit: str) -> str`, `download_verified(url: str, destination: Path, expected_sha256: str) -> None`, `run(argv: Sequence[str], cwd: Path | None = None) -> None`, and `main() -> int`.
- `main()` creates `.venv-ui` and `.venv-lofcz`, installs macOS snapshots, prepares both sibling clones, downloads the lofcz model, and runs compact checks.

- [ ] **Step 1: Read the shared test-quality rules**

Read `superpowers:test-driven-development/writing-good-tests.md` before adding the new tests.

- [ ] **Step 2: Write failing safety tests**

Cover real filesystem behavior without network mocks:

```python
def test_nonempty_non_git_clone_target_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "occupied"
    target.mkdir()
    (target / "mine.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(BootstrapError, match="not an existing Git clone"):
        validate_clone_target(target)


def test_existing_matching_file_is_accepted(tmp_path: Path) -> None:
    destination = tmp_path / "model.onnx"
    destination.write_bytes(b"known")
    download_verified(
        "https://invalid.example/model",
        destination,
        hashlib.sha256(b"known").hexdigest(),
    )
    assert destination.read_bytes() == b"known"


def test_existing_wrong_file_is_never_replaced(tmp_path: Path) -> None:
    destination = tmp_path / "model.onnx"
    destination.write_bytes(b"mine")
    with pytest.raises(BootstrapError, match="checksum"):
        download_verified(
            "https://invalid.example/model",
            destination,
            hashlib.sha256(b"expected").hexdigest(),
        )
    assert destination.read_bytes() == b"mine"
```

Also initialize temporary local Git repositories to verify that matching clean clones are accepted and dirty clones are rejected without checkout/reset.

- [ ] **Step 3: Run tests and verify RED**

Run: `python3.11 -m pytest tests/test_bootstrap_macos.py -q`

Expected: collection fails because `scripts.bootstrap_macos` does not exist.

- [ ] **Step 4: Implement minimal safe primitives**

Use only the Python standard library. `download_verified` must stream into `<destination>.part`, verify the temporary file, then use `os.replace`; delete only its own `.part` file after an error. Existing files are verified and returned unchanged. Git commands use argument arrays, `check=True`, captured UTF-8 output, and no shell.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `python3.11 -m pytest tests/test_bootstrap_macos.py -q`

Expected: all bootstrap safety tests pass.

- [ ] **Step 6: Add orchestration and local-environment ignores**

`main()` must:

```text
1. Require macOS arm64, Git, and Python 3.11.
2. Create .venv-ui and .venv-lofcz with `python -m venv` when their Python executables are absent.
3. Upgrade pip in each environment.
4. Install environments/ai-music-ui-macos.txt and environments/ai-music-lofcz-macos.txt.
5. Clone missing sibling repositories and checkout the exact recorded commits.
6. Accept existing clean clones only when HEAD equals the recorded commit; refuse dirty or mismatched clones.
7. Download and verify models/lofcz/ai_music_detector.onnx.
8. Print the resolved interpreters, commit hashes, model hash, and next command.
```

Add `.venv-ui/` and `.venv-lofcz/` to `.gitignore`.

- [ ] **Step 7: Run focused and provisioning regression tests**

Run: `python3.11 -m pytest tests/test_bootstrap_macos.py tests/test_provisioning.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add .gitignore scripts/bootstrap_macos.py tests/test_bootstrap_macos.py
git commit -m "feat: add safe macOS bootstrap"
```

### Task 4: POSIX entry points and macOS documentation

**Files:**
- Create: `bootstrap_macos.sh`
- Create: `start_ui.sh`
- Create: `tests/test_macos_scripts.py`
- Modify: `README.ru.md`
- Modify: `README.md`
- Modify: `docs/ru/getting-started.md`
- Modify: `docs/getting-started.md`

**Interfaces:**
- `bootstrap_macos.sh` executes `/opt/homebrew/bin/python3.11 scripts/bootstrap_macos.py` from the repository root.
- `start_ui.sh` executes `.venv-ui/bin/python -m music_lab_ui.app` from the repository root with UTF-8 environment variables.

- [ ] **Step 1: Write failing launcher contract tests**

```python
def test_bootstrap_launcher_is_location_independent() -> None:
    text = (ROOT / "bootstrap_macos.sh").read_text(encoding="utf-8")
    assert 'SCRIPT_DIR=' in text
    assert 'scripts/bootstrap_macos.py' in text
    assert '/opt/homebrew/bin/python3.11' in text


def test_ui_launcher_uses_project_venv_and_utf8() -> None:
    text = (ROOT / "start_ui.sh").read_text(encoding="utf-8")
    assert 'SCRIPT_DIR=' in text
    assert '.venv-ui/bin/python' in text
    assert 'PYTHONUTF8=1' in text
    assert '-m music_lab_ui.app' in text
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3.11 -m pytest tests/test_macos_scripts.py -q`

Expected: both tests fail with `FileNotFoundError`.

- [ ] **Step 3: Add the two shell entry points**

Both scripts use `#!/usr/bin/env bash`, `set -euo pipefail`, derive `SCRIPT_DIR` from `${BASH_SOURCE[0]}`, and use quoted absolute paths. `start_ui.sh` checks for its interpreter and tells the user to run `./bootstrap_macos.sh` when absent.

- [ ] **Step 4: Validate shell syntax and focused tests**

Run: `bash -n bootstrap_macos.sh start_ui.sh`

Run: `python3.11 -m pytest tests/test_macos_scripts.py -q`

Expected: syntax validation succeeds and tests pass.

- [ ] **Step 5: Document exact macOS commands and scope**

Add the following quick-start flow to English and Russian documentation:

```bash
chmod +x bootstrap_macos.sh start_ui.sh
./bootstrap_macos.sh
./start_ui.sh
```

State that this milestone supports the UI, model-free metrics, and lofcz on Apple Silicon. State that FST/MPS and muscriptor are later milestones, and retain all existing Windows instructions.

- [ ] **Step 6: Commit**

```bash
git add bootstrap_macos.sh start_ui.sh tests/test_macos_scripts.py README.md README.ru.md docs/getting-started.md docs/ru/getting-started.md
git commit -m "docs: add macOS launch workflow"
```

### Task 5: Provision and verify the current Mac

**Files:**
- Runtime-only ignored directories: `.venv-ui/`, `.venv-lofcz/`
- Runtime-only sibling clones: `../ai-music-detector/`, `../FST-AI-Music-Detection/`
- Runtime-only ignored model: `models/lofcz/ai_music_detector.onnx`
- Runtime-only smoke artifacts under `artifacts/`

**Interfaces:**
- Consumes all deliverables from Tasks 1–4.
- Produces a locally runnable installation and evidence for each completion criterion.

- [ ] **Step 1: Execute bootstrap**

Run: `chmod +x bootstrap_macos.sh start_ui.sh && ./bootstrap_macos.sh`

Expected: both venvs install, both repositories reach their recorded commits, and the lofcz model hash is verified.

- [ ] **Step 2: Run the complete UI test suite**

Run: `.venv-ui/bin/python -m pytest -q`

Expected: all tests pass with no failures.

- [ ] **Step 3: Generate a deterministic smoke WAV**

Run: `.venv-ui/bin/python scripts/make_smoke_wav.py --kind rhythm --seconds 32 --output artifacts/macos-rhythm-smoke.wav`

Expected: `artifacts/macos-rhythm-smoke.wav` exists and is non-empty.

- [ ] **Step 4: Run lofcz through the project adapter**

Run:

```bash
.venv-lofcz/bin/python adapters/lofcz_cli.py \
  --upstream ../ai-music-detector \
  --model models/lofcz/ai_music_detector.onnx \
  --audio artifacts/macos-rhythm-smoke.wav \
  --json-output artifacts/macos-lofcz-smoke.json \
  --npz-output artifacts/macos-lofcz-smoke.npz
```

Expected: exit code 0; JSON contains `probability`, `is_ai`, and `telemetry`.

- [ ] **Step 5: Start the UI and verify HTTP readiness**

Run `./start_ui.sh` in a PTY, then request `http://127.0.0.1:7860/ru` with `curl --fail --silent --show-error --max-time 10`.

Expected: HTTP success and returned HTML. Stop the foreground server cleanly with Ctrl+C after verification.

- [ ] **Step 6: Record final evidence**

Run:

```bash
git -C ../ai-music-detector rev-parse HEAD
git -C ../FST-AI-Music-Detection rev-parse HEAD
shasum -a 256 models/lofcz/ai_music_detector.onnx
git status --short --branch
```

Expected: both recorded commits and the recorded model digest match the global constraints; only intentional repository changes are present.

- [ ] **Step 7: Commit any verification-only documentation corrections**

If real execution exposed inaccurate commands, update only the affected documentation and commit:

```bash
git add README.md README.ru.md docs/getting-started.md docs/ru/getting-started.md
git commit -m "docs: correct verified macOS setup"
```

If no correction was needed, do not create an empty commit.
