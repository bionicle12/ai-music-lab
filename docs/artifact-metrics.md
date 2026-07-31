# Artifact metrics

[← Documentation](README.md) · [Русский](ru/artifact-metrics.md)

**The question this answers:** what is measurably different about this audio, regardless of
what any model thinks?

The **Артефакты** (Artifacts) tab computes measurements directly from the signal. No detector,
no weights, no training domain — just the waveform.

## What is measured

| Metric | Definition |
| --- | --- |
| **Attack** | The typical sharpest rise in loudness over 20 ms |
| **Rolloff 95%** | The frequency below which 95% of the energy sits |
| **High-frequency slope** | The steepest decay above 4 kHz, in dB per octave |
| **Noise floor level** | How loud the quietest part of the signal is |
| **Noise floor flatness** | How spectrally flat that floor is |
| **Channel correlation** | Left/right correlation, measured separately in the low and high bands |

## Why they exist

Detectors have a training domain. A new generator, an unusual genre or a heavily processed
stem can fall outside it, and then the score stops carrying information. These measurements
keep working there, because nothing about them depends on having seen a particular generator
before.

They also point at edits you can actually hear. "The 95% rolloff sits at 15 kHz and the slope
above 4 kHz is very steep" is something you can address at the mixing stage. "The score is
0.83" is not.

## The methodological warning

**Compare like with like.** This is the mistake that invalidates most artifact comparisons:

- **MP3 against WAV** shows the codec, not the generator. MP3 imposes a high-frequency cutoff
  on any audio regardless of where it came from, so this comparison measures the encoder.
- **A single stem against a full mix** is not a comparison either. A solo pad and a dense mix
  have completely different spectral and dynamic profiles by definition.
- **Different sample rates** shift the rolloff figures on their own.

The numbers mean very little in isolation. They become useful when you add reference files to
the track and measure everything the same way: same format, same sample rate, same kind of
material.

## A workable routine

1. Collect two or three references — real recordings in the genre you are aiming at.
2. Convert everything to the same format and sample rate.
3. Measure the references and your track.
4. Look at which metric is furthest from the reference range, and fix that first.
5. Re-measure through [A/B comparison](comparison.md) to confirm the edit moved it.

Step 5 is the point. Without it you are guessing about your own edits.
