# A/B comparison

[← Documentation](README.md) · [Русский](ru/comparison.md)

**The question this answers:** did my edit actually change anything, or does it only feel like
it did?

Two saved runs of the same source are compared as **version B − version A**.

## How to set it up

1. Analyse the original. Add a note describing it.
2. In the history, pin that run as the permanent **Версия A**.
3. Edit the audio in your DAW and analyse the result. It automatically becomes **Версия B**.
4. Open the **Сравнение версий** (Compare) tab.

Every new analysis becomes version B while A stays pinned, so you can try five different edits
against the same baseline without re-pinning anything.

## What you get

| View | What it shows |
| --- | --- |
| Detector deltas | Change in each detector's score, B relative to A |
| Scalar deltas | Change in every scalar metric, as a table |
| Average spectrum overlay | Both spectra on one plot |
| Spectral heatmap | Where in time and frequency the two versions differ |
| Native A/B plots | lofcz and FST telemetry side by side |

The spectral heatmap is the one to read when a score moved and you want to know why. It shows
*where* the change landed, which is usually more actionable than the score delta itself.

## Requirements and limits

The **temporal** heatmap needs the two files to be within 5% of each other in duration. Beyond
that, detector scores, average spectra and scalar metrics remain available — only the
time-aligned view is dropped, because aligning meaningfully different lengths would produce a
convincing-looking picture of nothing.

Comparing two different songs is technically possible and practically useless: it mostly
measures the difference in musical material. The comparison is designed for one source in two
states.

## The useful pattern

```text
Version A: original stem
Version B: the same stem after one specific edit
```

One edit at a time. If you change the de-esser, the saturation and the stereo width in the same
pass, you have measured "all three together" and learned nothing about which one mattered.

## Reading a delta honestly

A moved score means the model responds differently to the new file. That is genuinely useful
production feedback, and it is also the whole claim — it is not evidence that the track's
origin changed, and a model that moves a lot may simply be sensitive to something incidental
like level or codec.

Keep the artifact metrics in view alongside the score: if the score dropped but no signal
metric moved, be suspicious of the score rather than pleased with it.
