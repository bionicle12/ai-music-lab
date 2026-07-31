# Limitations

[← Documentation](README.md) · [Русский](ru/limitations.md)

Read this before drawing a conclusion from any number this tool prints.

## What a detector score is

A score is a measurement tied to four things: the version of the code, the version of the
weights, the input file, and the conditions of the run. Change any of them and you have a
different measurement.

**It is not proof of where a track came from.** No score here — high or low — establishes
origin. The honest framing is "this file produces this response from this model", and every
useful conclusion has to be built on top of that sentence rather than around it.

## Compare like with like

Most wrong conclusions come from comparing things that were never comparable.

| Do not compare | Because you are measuring |
| --- | --- |
| MP3 against WAV | The codec's high-frequency cutoff, not the generator |
| A single stem against a full mix | The difference between sparse and dense material |
| Different sample rates | The resampling, in the rolloff figures |
| Two different songs | The musical material |
| Runs from before and after an upstream update | Two different models |

The comparison this tool is built for is **one source in two states**: original and edited.
See [A/B comparison](comparison.md).

## Detector-specific limits

**lofcz** averages over the whole track. It cannot say which second carries the fingerprint,
which is why the [timeline map](timeline.md) exists as a separate sliding-window pass — and
those window values are a relative map inside one track, not a calibrated per-second
probability.

**FST** requires detectable beats and downbeats. On vocals, ambience or pads it returns
"not applicable" instead of a number. Its output scale is bounded at `0.011 … 0.989`, so `1.1%`
and `98.9%` are the ends of the scale, not certainty. Its Stage-1 class indices are not
published with a reliable `Real`/`Fake` mapping and are therefore left unrenamed.

## When the two detectors disagree

A low FST score with a high lofcz score is a real result. Record it as a disagreement.

The temptation is to average the two into one comfortable number. Don't. The two models were
trained differently, and a new generator can easily fall outside FST's training domain while
still being obvious to lofcz — or the reverse. The disagreement itself carries information that
the average destroys.

This is also the case where the [artifact metrics](artifact-metrics.md) matter most: they are
computed straight from the signal, with no training domain to fall outside of.

## Do not split a mix to analyse it

Running a finished mix through a source-separation tool and analysing the stems measures the
separator. Separation adds its own artifacts and raises the score on its own. Use real
pre-mixdown tracks, or measure the mix as a whole. See [Layers](layers.md).

## Synthetic test files

`scripts/make_smoke_wav.py` generates a file that proves the pipeline runs. Its score is
meaningless as a statement about model accuracy — it is a synthetic rhythm, not music.

## What this tool will not do

It will not tell you a track is "safe", certify anything, or assign a verdict. It measures, it
localizes, and it records what changed between two versions. Every interpretation past that
point is yours to make and yours to defend.
