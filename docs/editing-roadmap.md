# Editing — roadmap

[← Documentation](README.md) · [Русский](ru/editing-roadmap.md)

**Status: both halves ship.** See [Audio → MIDI](midi.md) for To MIDI. SunoFix landed as the
design below describes, with one addition the design did not have: the repair layer and the
taste layer are kept apart by construction, and a preset cannot reach into the repair.

The workspace is split in two:

| Group | What it does |
| --- | --- |
| **Analysis** | Measures a track. |
| **Editing** | Changes a track. Both `To MIDI` and `SunoFix` ship. |

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

The [Artifacts](artifact-metrics.md) tab measures attack, 95% rolloff, the HF cliff, the HF
edge, tonal prominence, noise floor and its flatness, and low/high stereo correlation. Each of
those is a defect with a known repair, and the repair is driven from the measurement rather
than by ear:

| Measured defect | Repair | Module |
| --- | --- | --- |
| Tonal ridges in the upper mids | Narrow notches at the measured frequencies | `de_artifact` |
| Smeared transients (low attack) | Transient shaping, driven by the measured attack | `fix_transients` |
| HF cliff, dead top end | Band extension above the wall | `restore_air` |
| Sterile, unnaturally flat noise floor | Restore a plausible floor | `restore_floor` |
| Collapsed or over-wide stereo image | Per-band correction from the correlation figures | `fix_stereo` |
| Chirps, warble, swirl in the highs | Downward expansion of quiet HF | `hf_cleanup` |

### The two layers, and why they are separate

**Repair** is ticked by the measurements. **Taste** — warmth and HF cleanup — is what presets
control. A preset may never touch the repair layer: if choosing a musical pass could silently
change which defects get fixed, the measurement has stopped being the thing that drives the
repair. A test asserts this for every preset.

The chain runs `de_artifact → fix_transients → hf_cleanup → restore_air → restore_floor →
fix_stereo → warmth → tone → true-peak check`. Two orderings in there are arguments, not
conventions: `de_artifact` goes before anything that adds harmonics, so its notches aim at the
spectrum that was measured; `restore_air` goes *after* cleanup, because a cleanup stage placed
downstream would expand away the band that was just synthesised.

### The level

Nothing is normalised and nothing is limited. Gain is only ever pulled back, and only when true
peak would leave -1 dBTP. An A/B where one side is louder proves nothing, because louder reads
as better whatever was done to it. The output is a mastering-ready WAV, not a master.

### Presets

Taste only. The starting values were measured off a working implementation rather than
invented, and are a hypothesis until an A/B of our own says otherwise.

| Preset | Warmth | Drive | Mix | Tone | HF cleanup |
| --- | --- | --- | --- | --- | --- |
| `repair_only` | off | — | — | — | soft |
| `soft_glue` | on | 0.08 | 0.12 | -0.05 | off |
| `open_top` | on | 0.08 | 0.12 | 0.00 | off |
| `de_harsh` | on | 0.10 | 0.14 | -0.05 | soft |
| `add_body` | on | 0.22 | 0.30 | -0.10 | off |

`mix` sits at roughly 1.4x `drive` throughout: they are two controls for one idea. `tone` is
negative everywhere except `open_top`, because it exists to pay back the brightness that
restored air and added harmonics put in — which is exactly what the one pass whose job is the
top end must not do.

Two execution paths, most likely both:

1. **Autonomous.** Ordinary DSP inside the project, no external tools. This is the path that
   keeps a run reproducible and is therefore the default.
2. **Optional VST bridge.** The same steps handed to installed plugins (iZotope RX and
   similar) through a plugin host. A VST run has to be marked non-reproducible in the history,
   because the plugin build becomes part of the result.

**The open question, now with a suspect.** `restore_air` and `restore_floor` both synthesise
material that was not in the file, and both remove a signal detectors read easily — a lowpass
wall, a floor too clean to be a recording. A lower score after either one is therefore not
evidence that it helped. Both are marked in the interface, and the way to settle it is to run
one on its own and check the score against a blind listen. `de_artifact` and `fix_transients`
are the honest ones by this test: they remove something audible.

That is still an open question, not a settled one. Nothing here has been through the blind
listen yet.

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
3. ~~Settle the SunoFix design.~~ Done — the two-layer split above.
4. ~~`SunoFix`, one repair at a time, each measured before and after.~~ Done; every pass
   returns the artifact metrics as an A/B against the source.
5. Prove the marked repairs, one at a time, against a blind listen. Until that happens,
   `restore_air` and `restore_floor` are switched on at your own risk.
6. The optional VST bridge, last, and only once the autonomous path works.
