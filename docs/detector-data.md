# Detector data

[← Documentation](README.md) · [Русский](ru/detector-data.md)

**The question this answers:** what did the model actually compute, before it was reduced to
one number?

Telemetry is stored separately from the final score, per run:

```text
data/runs/<run_id>/telemetry/<detector>/
├── telemetry.json   # configuration, scalar values, warnings, shapes, checksum
└── arrays.npz       # the full raw arrays, downloadable from the interface
```

## lofcz

| Signal | What it is |
| --- | --- |
| Average spectrum 1–8 kHz | The band the model works in |
| Lower hull | The lower envelope fitted to that spectrum |
| Residue | The distance between spectrum and hull |
| Fakeprint | The exact 3585-value vector fed into the ONNX model |

These are **averaged over time**. lofcz does not report which second an "AI fragment" sits in —
that is exactly why the [timeline map](timeline.md) exists as a separate sliding-window pass.

## FST

| Signal | What it is |
| --- | --- |
| Beats / downbeats | The rhythmic grid it detected |
| Valid segments | 10-second beat-aligned segments it could use |
| Stage-1 class outputs | Both raw class outputs |
| MERT embeddings | The embedding representation |
| Self-similarity matrix | Structural repetition within the track |
| Fusion-gate timeline | How the two stages were combined over time |

Stage-1 indices are deliberately **not** renamed from `class 0 / class 1` to `Real / Fake`.
Upstream does not publish an unambiguous mapping, and inventing one here would turn a raw model
output into a false claim.

## Reading the plots correctly

These graphs describe **signals and model contribution**. They do not mark regions as "AI
here". A peak in the fusion gate means the model weighted that segment differently, which is
not the same statement as "this section is generated".

## Boundary values

`1.1%` and `98.9%` are the lower and upper bounds of upstream FST's output scale
(`0.011 … 0.989`), not a calibrated guarantee. Seeing `1.1%` means "at or below the floor of
this scale", not "certainly real".

## When FST returns "not applicable"

FST can decline vocals and other stems that have no stable beats or downbeats. That is an
expected upstream limitation, not a UI failure — the adapter fails with the explicit message
`FST preprocessing found no beat-aligned segments` rather than recording a fabricated
`Real / NaN`.

## Older runs

Runs created before telemetry existed remain readable, but they have no telemetry attached. To
get it, analyse the file again — that creates a new version rather than backfilling the old
one, which keeps each history entry an honest record of what was actually measured at the time.
