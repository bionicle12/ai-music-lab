# Layers

[← Documentation](README.md) · [Русский](ru/layers.md)

**The question this answers:** what should I re-record first?

A score for the whole mix tells you the track reads as generated. It does not tell you whether
that is coming from the drums, the pads or the vocal. The **Слои** (Layers) tab measures each
stem separately and ranks them.

## How to use it

Load the individual tracks **before mixdown** — one file per layer. Each is measured on its
own, and the result comes back as a ranked table and a horizontal bar chart:

```text
drums          97%
synth pad      74%
bass           41%
live guitar    15%
```

That ordering is the output you act on. The guitar is fine. The drums are the reason the mix
reads as generated.

Three files take roughly nine seconds.

## Why it does not save to history

A layer run is **not** stored as a version and creates no history entry. One entry per stem
would bury the log of real experiments under diagnostic noise.

If you want to track a layer over time — measure it, edit it, measure again — analyse it the
normal way instead. It then becomes a version like any other and can be compared through
[A/B comparison](comparison.md).

## Why lofcz only

Layer analysis uses `lofcz` alone. `FST` needs detectable beats and downbeats, which most
individual stems do not have — a pad or a vocal would simply return "not applicable", so
running it would add time and no information.

## Do not split a finished mix

It is tempting to run a finished mix through a source-separation tool and analyse the
resulting stems. Do not use that for this measurement. Separation introduces its own
artifacts and raises the score by itself, so you would be measuring the separator rather than
your music.

Use the real pre-mixdown tracks, or accept that you can only measure the mix as a whole.

## Reading the ranking honestly

The percentages are comparable **to each other within this run**, because every layer was
measured by the same model under the same conditions. They are not calibrated probabilities,
and a stem in isolation is a different signal from the same stem inside a dense mix — a solo
pad has no masking around it.

Treat the ranking as a priority list, not as a verdict per instrument.
