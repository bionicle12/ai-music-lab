# Timeline map

[← Documentation](README.md) · [Русский](ru/timeline.md)

**The question this answers:** which seconds of the track carry the fingerprint?

A global score does not say what to fix. A sliding window over the same track shows which
sections produce it.

## In the interface

Open the **Карта по времени** (Timeline) tab after an analysis, choose a window length and a
hop, then press **Построить карту**. `lofcz` is re-run over successive windows on top of the
run you already have.

No new run is created. The map is stored as telemetry belonging to the existing version, under
`data/runs/<run_id>/telemetry/lofcz-timeline/`, which means you can also build a map for an old
run without disturbing its history entry. Clicking the curve seeks the player to that moment.

If the run also has FST telemetry, its per-segment signals are overlaid on a separate right-hand
axis with its own fixed `0–1` scale: both Stage-1 class values and the `fusion gate`. These are
raw model outputs, not per-segment probabilities of "AI", and they are deliberately not renamed:
upstream does not publish a reliable mapping from Stage-1 classes to `Real`/`Fake`.

The separate axis is the whole point. `lofcz` is drawn in percent on the left and FST in `0–1`
on the right; put both on one scale and FST lies flat along the bottom of the chart, which reads
as "FST found nothing" even on a track it scored at 98%.

## From the command line

```powershell
conda run -n ai-music-lofcz python adapters\lofcz_cli.py --upstream ..\ai-music-detector --model models\lofcz\ai_music_detector.onnx --audio "path\to\track.mp3" --mode timeline --window-seconds 15 --hop-seconds 5 --json-output artifacts\timeline.json --npz-output artifacts\timeline.npz
```

The JSON holds a summary and the hottest windows. The NPZ holds the full arrays:

| Array | Meaning |
| --- | --- |
| `window_start_seconds` | Start of each window |
| `window_end_seconds` | End of each window |
| `window_center_seconds` | Centre, useful as the plotting x-axis |
| `probability` | Model output for that window |
| `mean_residue_db` | Raw signal measurement, no model involved |
| `stft_frames_per_window` | How many frames were averaged |
| `fakeprint_by_window` | Matrix of shape `windows × 3585` |

## The limitation that matters

The model was trained on an average over a whole track. Window values are therefore a
**relative map inside one track**, not a calibrated probability per second. Two rules follow:

- Compare windows against other windows *of the same track*. Comparing a window value against
  another track's global score is not meaningful.
- The shorter the window, the fewer STFT frames are averaged, and the noisier the estimate. A
  15-second window with a 5-second hop is a reasonable starting point.

`mean_residue_db` is the built-in sanity check. It is a raw measurement with no model in the
path, so if it does not correlate with the model curve at all, treat the window values with
more suspicion than usual.
