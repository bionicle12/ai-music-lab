# FST on Apple Silicon MPS Design

## Goal

Run the existing FST detector on the current 24 GB Apple Silicon Mac while
preserving the existing Windows/CUDA behavior and keeping both upstream
repositories pristine.

The macOS path targets a hard PyTorch MPS allocation ceiling of approximately
13.3 GiB. It prioritizes an explicit, measurable execution plan over a global
CPU fallback that could silently change performance or numerical behavior.

## Verified Inputs and Host

- Host: Apple Silicon `arm64`, macOS 26.5, 24 GB unified memory.
- PyTorch 2.8 reports MPS built and available.
- `torch.mps.recommended_max_memory()` reports approximately 17.76 GiB.
- MPS memory fraction `0.75` therefore limits PyTorch allocations to
  approximately 13.3 GiB.
- `models/fst/Stage-1.ckpt` SHA-256:
  `f9099df5c618a2f92bcd8f4ba48d1c6606f2e4610385b8eea4a03f1a7319629f`.
- `models/fst/Stage-2.ckpt` SHA-256:
  `ed133c261c5d367fc6adf53813a5c93b62a59de5bef546cf5899a5c157eba7a0`.
- FST upstream remains at
  `b564f8be8b3db6b7810c2aab61f0b4f86f889579`.

## Selected Architecture

Use a staged hybrid pipeline on macOS:

```text
audio
  → Beat This on CPU
  → segment construction on CPU
  → MERT Stage-1 on MPS in bounded batches
  → release Stage-1 and cached MPS allocations
  → Stage-2 classifier on MPS
  → JSON/NPZ plus sampled memory telemetry
```

Windows retains the current CUDA pipeline. A host with neither CUDA nor MPS
receives an explicit unsupported-device error; the adapter does not silently
run the complete detector on CPU.

Beat tracking stays on CPU on macOS because it is a separate, comparatively
small preprocessing model. Keeping it off MPS reduces compatibility risk and
prevents it from occupying allocator state before the much larger MERT model.
Stage-1 and Stage-2 stay on MPS because Stage-1 dominates compute and Stage-2
uses fp16 in the published inference path.

## Environment and Provisioning

Add `environments/ai-music-fst-macos.txt`, derived from the existing FST
snapshot with these platform substitutions:

- CUDA Torch/TorchAudio builds become native macOS ARM builds at version 2.8.0.
- Windows-only `pyreadline3` is removed.
- Other package versions remain pinned unless installation proves a specific
  package unavailable on Apple Silicon.

The macOS bootstrap creates `.venv-fst`, installs the snapshot, and verifies
MPS availability. It does not download the two FST checkpoints: they remain
manual Google Drive downloads and are verified against their published hashes.
Existing local checkpoint files are accepted only when both hashes match; the
files remain ignored by Git.

The first real run may download the official MERT weights and Beat This
`final0` checkpoint into their normal caches. These are upstream runtime
dependencies, not substitutes for the FST checkpoints.

## Device Plan

Introduce a small, testable device-plan value used by the adapter:

| Runtime | Beat tracking | Stage-1 | Stage-2 | Memory control |
| --- | --- | --- | --- | --- |
| CUDA available | CUDA | CUDA | CUDA | Existing behavior |
| MPS available | CPU | MPS | MPS | Fraction `0.75` |
| Neither | unsupported | unsupported | unsupported | N/A |

Device selection defaults to `auto`. An explicit CLI device may request
`cuda` or `mps` for diagnostics, but it must pass availability checks. There is
no public full-CPU FST mode in this milestone.

`PYTORCH_ENABLE_MPS_FALLBACK` is not enabled. An unsupported MPS operator must
fail visibly so a targeted decision can be made for that stage.

## Batch Defaults and Settings

The existing CUDA default remains eight segments per Stage-1 forward pass.
The macOS default is two segments. Valid choices become `1`, `2`, `4`, `8`,
and `0`, where zero retains the upstream all-48 behavior.

The stored setting remains a single `fst_backbone_batch` field. Its default is
platform-aware only for a new settings file: two on macOS, eight elsewhere.
An existing explicit stored value is preserved. Every run records the actual
batch size and device plan that produced it.

Batch zero remains selectable for CUDA reproducibility but is unsafe on this
Mac and must be rejected before allocation when the selected device is MPS.

## MPS Memory Control

Before allocating an MPS model, the adapter calls
`torch.mps.set_per_process_memory_fraction(0.75)`. It records:

- requested fraction;
- `recommended_max_memory`;
- computed allocation ceiling;
- `current_allocated_memory`;
- `driver_allocated_memory`;
- maximum sampled current and driver allocations;
- the pipeline stage attached to every sample.

Memory is sampled only after `torch.mps.synchronize()` at these boundaries:

1. MPS initialization;
2. Stage-1 checkpoint loaded;
3. every Stage-1 batch;
4. Stage-1 outputs copied to CPU;
5. Stage-1 deleted and `torch.mps.empty_cache()` completed;
6. Stage-2 checkpoint loaded;
7. Stage-2 inference completed;
8. final cleanup.

The reported maximum is named a sampled peak. It is not presented as a
continuous profiler measurement and may miss a shorter-lived allocation
between boundaries.

## Stage Lifecycle

### CPU preprocessing

Call the pristine upstream `get_segments_from_wav` with `device="cpu"`. Build
the 24 kHz ten-second segments and padding mask on CPU exactly as the adapter
does now. Delete the Beat This object through its existing upstream lifecycle
before MPS initialization.

### Stage-1

Load the published Stage-1 checkpoint, move the model to MPS, and run the
existing sliced forward loop. Start with a batch of two. Copy logits and
embeddings needed for telemetry to CPU after the loop.

Retain only the small MPS embedding tensor needed by Stage-2. Delete the
Stage-1 model, audio segments, temporary outputs, and other large references,
then synchronize and empty the MPS cache before loading Stage-2.

### Stage-2

Load the published classifier checkpoint on MPS and preserve its fp16
inference behavior. Capture the existing fusion-gate telemetry. After the
result and arrays have been copied to CPU, delete Stage-2 and perform final MPS
cleanup.

If the pristine upstream `run_inference` fails because of an MPS-specific
implementation detail, the wrapper may implement an equivalent Stage-2 call in
the adapter. It must preserve checkpoint weights, fp16 behavior, scaled sigmoid
calculation, padding semantics, and output fields; the upstream clone remains
unchanged.

## Results and Telemetry

The result keeps the existing detector probability and telemetry fields and
adds:

- logical device (`cuda` or `mps`);
- device label;
- beat-tracking device;
- Stage-1 and Stage-2 devices;
- requested and actual backbone batch;
- MPS memory fraction and ceiling when applicable;
- ordered memory samples and sampled peaks;
- whether any targeted CPU stage was used.

Run history therefore distinguishes CUDA and MPS measurements. Scores from the
two devices are not assumed byte-identical.

## Error Handling

- Missing or mismatched checkpoints stop before model allocation.
- Unavailable explicit devices produce a device-specific precondition error.
- MPS batch zero is rejected before model allocation.
- MPS OOM reports the stage, actual batch, fraction, ceiling, and last memory
  sample, then recommends the next smaller batch when one exists.
- Unsupported operations report the failing stage and operator text. They do
  not activate global CPU fallback.
- Empty beat-aligned segmentation retains the existing not-applicable result.
- Partial output files are not treated as successful results.

## Verification Strategy

Implementation follows test-driven development.

Unit coverage includes:

- device-plan selection for CUDA, MPS, and unsupported hosts;
- platform-aware batch defaults and accepted batch choices;
- rejection of MPS batch zero;
- conversion of fraction to the recorded byte ceiling;
- ordered sampled-memory telemetry using a narrow injected probe;
- controlled OOM and unsupported-operator messages;
- macOS dependency policy and bootstrap idempotence;
- preservation of existing CUDA defaults and commands.

Integration verification on this Mac requires:

1. Complete project tests pass.
2. `.venv-fst` reports Torch 2.8 and MPS available.
3. Both FST checkpoint hashes match.
4. The 32-second deterministic rhythm smoke succeeds at batch two.
5. JSON and NPZ contain the existing result fields and new device/memory data.
6. A second batch-two run produces the same prediction and probabilities,
   with any raw numerical difference reported rather than hidden.
7. The sampled driver peak stays below the recorded approximately 13.3 GiB
   allocation ceiling.
8. Batch four is attempted only after batch two succeeds.
9. Batch eight is attempted only when batch four remains within the ceiling.
10. The UI launches FST through `.venv-fst` and persists the result.

If a real MPS incompatibility appears, stop at the exact failing stage. A
targeted CPU stage is designed and documented only from that evidence, rather
than enabling blanket fallback preemptively.

## Documentation

Update English and Russian setup and model documentation with:

- `.venv-fst` provisioning on Apple Silicon;
- both manual checkpoint locations and hashes;
- the MPS/CPU staged execution plan;
- default fraction and batch;
- first-run MERT and Beat This downloads;
- device-dependent numerical comparability caveat;
- recovery instructions for OOM and unsupported operators.
