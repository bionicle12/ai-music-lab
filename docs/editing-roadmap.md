# Editing — roadmap

[← Documentation](README.md) · [Русский](ru/editing-roadmap.md)

**Status: SunoFix is not implemented.** To MIDI is — see [Audio → MIDI](midi.md). What remains
here is the SunoFix design, held so it can be argued with before any of it is written.

The workspace is split in two:

| Group | What it does |
| --- | --- |
| **Analysis** | Measures a track. |
| **Editing** | Changes a track. `To MIDI` ships; `SunoFix` is still a placeholder. |

## The rules this half inherits

Nothing here gets to break what the analysis side already guarantees:

- **The original is never overwritten.** An edit produces a new file, which becomes a new
  version in the history.
- **Every step is reproducible.** Same input, same parameters, same output — on any machine
  that can install the environments.
- **The result is measured, not asserted.** An edit is followed by the same artifact metrics
  and detector scores as any other version, and read as an A/B against the version it came
  from. "It got better" has to be a number.
- **No step requires a paid tool.** Optional bridges to commercial plugins are allowed; a
  dependency on one is not.

## SunoFix — repairing generation artifacts

The [Artifacts](artifact-metrics.md) tab already measures attack, 95% rolloff, the HF cliff,
noise floor and its flatness, and low/high stereo correlation. Each of those is a defect with a
known repair. The plan is to drive the repair from the measurement instead of by ear:

| Measured defect | Intended repair |
| --- | --- |
| HF cliff, dead top end | Spectral resynthesis above the wall |
| Smeared transients (low attack) | Transient shaping, driven by the measured attack |
| Sterile, unnaturally flat noise floor | Restore a plausible floor |
| Collapsed or over-wide stereo image | Per-band correction from the correlation figures |
| Chirps, warble, swirl in the highs | Spectral de-noise |

Two execution paths, most likely both:

1. **Autonomous.** Ordinary DSP inside the project, no external tools. This is the path that
   keeps a run reproducible and is therefore the default.
2. **Optional VST bridge.** The same steps handed to installed plugins (iZotope RX and
   similar) through a plugin host. A VST run has to be marked non-reproducible in the history,
   because the plugin build becomes part of the result.

**Open question before anything is written:** which of these repairs actually lowers a detector
score for the right reason, and which merely masks the signal the detector reads. A repair that
only fools the detector while the audio still sounds wrong is a failure, not a feature.

## To MIDI — done

Built on [muscriptor](https://github.com/muscriptor/muscriptor), with per-stem hand-off from the
Layers tab. Full documentation: [Audio → MIDI](midi.md).

Two things it delivered that SunoFix will reuse: settings with a Hugging Face token
(`data/settings.json`, environment variable takes priority), and an upstream registry that
reports the state of every clone and can fast-forward the one repository meant to move.

The limit stayed where it was predicted: polyphonic transcription of a dense mix is not solved,
so the workflow is stems in, sketch out.

## Order of work

1. ~~Hugging Face token handling and model download.~~ Done, shared by both features.
2. ~~`To MIDI`, end to end on a single stem.~~ Done.
3. Brainstorm and settle the SunoFix design — in particular the open question above.
4. `SunoFix`, one repair at a time, each one measured before and after.
5. The optional VST bridge, last, and only once the autonomous path works.
