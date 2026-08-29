"""Translation catalogue for the interface.

Each locale gets its own ``gr.Blocks`` instance, mounted on its own path (see
``app.main``), so a translator is chosen once per interface build and captured by
the event-handler closures. Nothing switches language mid-session, which is what
keeps dynamically generated content — Plotly axis titles, detector-card HTML,
table headers — consistent with the rest of the page.

Keys are namespaced by area: ``app.*`` for layout and controls, ``detector.*``
for score cards, ``plot.*`` and ``telemetry.*`` for figures, ``table.*`` for
column headers, ``service.*`` for status messages.
"""

from __future__ import annotations

from typing import Final

DEFAULT_LOCALE: Final[str] = "en"
LOCALES: Final[tuple[str, ...]] = ("en", "ru")

#: Locale code -> path the interface is mounted on. The default locale owns the
#: root, so a first-time visitor lands on English without a redirect.
LOCALE_PATHS: Final[dict[str, str]] = {"en": "/", "ru": "/ru"}

#: Names shown in the language switcher, always written in their own language.
LOCALE_NAMES: Final[dict[str, str]] = {"en": "English", "ru": "Русский"}


_EN: dict[str, str] = {
    # ---- shell ---------------------------------------------------------
    "app.title": "AI Music Lab",
    "app.eyebrow": "LOCAL FORENSIC AUDIO WORKSPACE",
    "app.tagline": "Local analysis of a single track or stem",
    "app.language": "Language",
    "app.restart.confirm": (
        "Restart the server?\n\n"
        "It picks up changes to the stylesheet, the translations and the "
        "Python. This page reloads from scratch; anything not yet analysed is "
        "lost. Saved runs are untouched."
    ),
    "app.restart.running": "Restarting — this page will reload itself.",
    "app.audio.label": "1. Audio file",
    "app.note.label": "Version note",
    "app.note.placeholder": "For example: vocal after de-esser v2",
    "app.detectors.label": "2. Detectors",
    "app.detectors.lofcz": "lofcz · signal model",
    "app.detectors.fst": "FST · structural model",
    "app.analyze": "▷  Run analysis",
    "app.status.ready": "Status: ready to analyse.",
    "app.method_note": (
        "> Results are measurements of specific model versions, not proof of "
        "where the audio came from."
    ),
    "app.empty.detectors": (
        "lofcz and FST results appear here after an analysis. Read the two "
        "scores against each other first."
    ),
    # ---- tabs ----------------------------------------------------------
    "tab.group.analysis": "Analysis",
    "tab.group.editing": "Editing",
    "tab.edit.sunofix": "SunoFix",
    "tab.edit.midi": "To MIDI",
    "tab.spectrum": "Spectrum",
    "tab.timeline": "Timeline map",
    "tab.layers": "Layers",
    "tab.artifacts": "Artifacts",
    "tab.detector_data": "Detector data",
    "tab.comparison": "Compare versions",
    "tab.technical": "Technical data",
    # ---- settings panel --------------------------------------------------
    "settings.open": "⚙  muscriptor setup",
    "settings.title": "### muscriptor setup",
    "settings.close": "Close",
    "settings.token.heading": "#### Hugging Face token",
    "settings.token.intro": (
        "Needed only to download the gated muscriptor weights. It stays on this "
        "machine."
    ),
    "disc.token.handling.title": "Where the token goes, and where it does not",
    "disc.token.handling.body": (
        "It is handed to the local muscriptor process as an environment "
        "variable and goes nowhere else: not into the run history, not into the "
        "technical-data panel, not into any log. It is never shown back to you "
        "here either — only its last four characters, so you can tell which "
        "token is stored.\n\n"
        "Stored here it lives in `data/settings.json` as plain text, which is a "
        "local file with no protection beyond your account. If you would rather "
        "not keep it on disk at all, set `HF_TOKEN` in the environment before "
        "starting the app — that takes priority over anything stored here."
    ),
    "settings.token.label": "Token",
    "settings.token.placeholder": "hf_…",
    "settings.token.save": "Save token",
    "settings.token.clear": "Delete token",
    "settings.token.status.env": (
        "In use: `HF_TOKEN` from the environment. Anything stored here is ignored."
    ),
    "settings.token.status.stored": "Stored in `data/settings.json`: `{fingerprint}`",
    "settings.token.status.none": (
        "No token. Transcription weights cannot be downloaded."
    ),
    "settings.token.cleared": "Token deleted from `data/settings.json`.",
    "settings.token.empty": "Enter a token first.",
    "settings.links": (
        '<ul class="settings-links">'
        '<li><a href="https://huggingface.co/settings/tokens" target="_blank" '
        'rel="noopener">Create a token</a> — a <strong>Read</strong> token is '
        "enough. If you make a <em>fine-grained</em> one instead, it will not "
        "reach gated repositories unless you tick "
        "<em>Read access to contents of all public gated repos you can "
        "access</em>. That single checkbox is the most common reason a download "
        "fails.</li>"
        '<li><a href="https://huggingface.co/MuScriptor/muscriptor-large" '
        'target="_blank" rel="noopener">Accept the model licence</a> — open the '
        "page for the size you intend to use and accept its terms. Access is "
        "granted automatically.</li></ul>"
    ),
    "settings.license.accept": "I have read the CC BY-NC 4.0 terms on the weights",
    "settings.model.heading": "#### Transcription model",
    "settings.model.label": "Checkpoint",
    "settings.model.small": "small · 103M · ~0.4 GB",
    "settings.model.medium": "medium · 307M · ~1.2 GB",
    "settings.model.large": "large · 1.4B · ~5.6 GB",
    "settings.model.note": (
        "Bigger transcribes better and costs more VRAM. The download occupies "
        "the whole interface until it finishes — the app runs one job at a time."
    ),
    "settings.download": "Download weights",
    "settings.download.done": "`{model}` downloaded and verified.",
    "settings.check": "Check the environment",
    "settings.repos.heading": "#### Upstream repositories",
    "settings.repos.note": (
        "The detectors and the transcriber are separate clones sitting beside "
        "this repository. The detectors are held at the commits this wrapper "
        "was verified against, so their scores stay comparable across runs — "
        "they are shown here but not updated from the interface. muscriptor "
        "tracks its branch and can be fast-forwarded."
    ),
    "settings.repos.refresh": "Refresh status",
    "settings.repos.pull": "Update muscriptor",
    # ---- readiness checklist ---------------------------------------------
    "readiness.heading": "MIDI transcription",
    "readiness.ready": "Ready.",
    "readiness.blocked": "Not set up yet — {detail}",
    "readiness.unverified": (
        "Ready. The package check has not been run; a transcription would "
        "report the problem itself."
    ),
    "readiness.item.clone": "muscriptor clone",
    "readiness.item.env": "Conda environment",
    "readiness.item.license": "Licence acknowledged",
    "readiness.item.token": "Hugging Face token",
    "readiness.item.weights": "Weights downloaded",
    "readiness.item.package": "Package check",
    "readiness.fix.clone": (
        "Clone `https://github.com/muscriptor/muscriptor.git` next to this "
        "repository."
    ),
    "readiness.fix.env": (
        "Create the `ai-music-muscriptor` environment — see the MIDI page in "
        "the documentation."
    ),
    "readiness.fix.license": (
        "Open Settings and confirm you have read the CC BY-NC 4.0 terms."
    ),
    "readiness.fix.token": "Add a Hugging Face token in Settings.",
    "readiness.fix.weights": "Download the selected checkpoint in Settings.",
    "readiness.fix.package": (
        "Run the environment check in Settings to see what the adapter reports."
    ),
    "readiness.not_checked": "not checked",
    # ---- per-detector settings -------------------------------------------
    "detector.settings.open": "Settings",
    "detector.settings.title": "{detector} · settings",
    "detector.settings.state": "State",
    "detector.settings.run": "Run parameters",
    "detector.settings.upstream": "Upstream",
    "detector.settings.none": (
        "Nothing to set for this detector yet — it runs the upstream defaults."
    ),
    "detector.settings.save": "Save",
    "detector.settings.saved": "Saved. Applies to the next run.",
    "detector.settings.close": "Close",
    "detector.ready.item.clone": "Upstream clone",
    "detector.ready.item.env": "Conda environment",
    "detector.ready.item.weights": "Weights",
    "detector.ready.ok": "Ready to run.",
    "detector.ready.blocked": "Cannot run — {detail}",
    "detector.ready.fix.clone": (
        "Clone the upstream repository next to this one — see Getting started."
    ),
    "detector.ready.fix.env": (
        "The environment's Python is not at that path. Create it, or point "
        "`AI_MUSIC_*_PYTHON` at the one you have."
    ),
    "detector.ready.fix.weights": (
        "Download the checkpoints into `models/` — sources and checksums are on "
        "the Models page."
    ),
    "provision.install": "Install what is missing",
    "provision.recheck": "Check again",
    "provision.log": "Progress",
    "provision.handover": "Hand this to a coding agent",
    "provision.done": "Done. Re-checked above.",
    "provision.no_conda": (
        "Conda was not found. It is a prerequisite, not something this app "
        "installs — get Miniconda, then come back."
    ),
    "provision.occupied": (
        "That folder already has files in it and will not be cloned over: {detail}"
    ),
    "provision.stalled": (
        "The step went silent and was stopped — usually a prompt waiting for "
        "input, which cannot be answered from here. {detail}"
    ),
    "provision.timeout": "The step ran too long and was stopped. {detail}",
    "provision.failed": "The step failed. {detail}",
    "provision.checksum": (
        "The download did not match its published checksum and was discarded: "
        "{detail}"
    ),
    "provision.error": "{detail}",
    "disc.provision.manual.title": "Two checkpoints have to be fetched by hand",
    "disc.provision.manual.body": (
        "FST's `Stage-1.ckpt` and `Stage-2.ckpt` live on Google Drive, which "
        "serves files this large behind a confirmation page — there is no "
        "stable direct link to automate. The install step prints both URLs and "
        "the exact paths they belong at; drop the files there and press "
        "**Check again**, and the checksums are verified before anything goes "
        "green. Everything else — the clone, the environment, the small ONNX "
        "model — is automated."
    ),
    "detector.upstream.repository": "Repository",
    "detector.upstream.head": "HEAD",
    "detector.upstream.match": "the verified commit",
    "detector.upstream.drift": "verified against {pinned}",
    "detector.upstream.missing": "no clone found",
    "detector.fst.batch.title": "Why this is the whole memory question",
    "detector.fst.batch.label": "Segments per backbone pass",
    "detector.fst.batch.1": "1 · lowest MPS memory",
    "detector.fst.batch.2": "2 · macOS default",
    "detector.fst.batch.4": "4 · 3.7 GB of VRAM",
    "detector.fst.batch.8": "8 · 4.8 GB",
    "detector.fst.batch.0": "all 48 · 16 GB, as upstream runs it",
    "detector.fst.batch.note": (
        "FST always processes 48 ten-second segments, padding short files up to "
        "48, so this is the whole of its memory appetite. The segments are "
        "independent until Stage-2 mixes them, and the measured times are the "
        "same for every choice."
    ),
    # ---- upstream repositories -------------------------------------------
    "table.repo.name": "Repository",
    "table.repo.head": "HEAD",
    "table.repo.branch": "Branch",
    "table.repo.state": "State",
    "table.repo.pinned": "Verified commit",
    "repo.state.missing": "not cloned",
    "repo.state.not_git": "not a git repository",
    "repo.state.dirty": "local changes",
    "repo.state.behind": "{count} commits behind",
    "repo.state.current": "up to date",
    "repo.state.clean": "clean",
    "repo.state.detached": "detached",
    "repo.pin.match": "matches",
    "repo.pin.drift": "ahead of `{commit}`",
    "repo.license.upstream": "upstream licence",
    "repo.license.mit_nc_weights": "MIT code · CC BY-NC weights",
    "repo.pull.pinned": (
        "This repository is deliberately held at a verified commit and is not "
        "updated from here."
    ),
    "repo.pull.missing": "The clone is not there.",
    "repo.pull.not_a_repository": "That directory is not a git repository.",
    "repo.pull.detached": (
        "HEAD is detached. Check out a branch by hand first, if that is really "
        "what you want."
    ),
    "repo.pull.dirty": (
        "The working copy has local changes, so nothing was pulled. Git reports:"
    ),
    "repo.pull.pull_failed": "git refused to fast-forward:",
    "repo.pull.unchanged": "Already up to date at `{commit}`.",
    "repo.pull.done": "Updated `{previous}` → `{current}` — {subject}",
    "repo.pull.dependencies": (
        "`pyproject.toml` changed. Re-run `pip install -e ..\\muscriptor` in "
        "the `ai-music-muscriptor` environment and refresh "
        "`environments/ai-music-muscriptor.txt`."
    ),
    "repo.pull.comparability": (
        "An upstream change means MIDI produced before and after is not "
        "guaranteed to match. Each transcription records the version it used."
    ),
    "repo.pull.pin_line": (
        "If this version works, record it: `{commit}` in `README.md` and "
        "`music_lab_ui/repositories.py`."
    ),
    # ---- MIDI transcription ----------------------------------------------
    "midi.source.label": "What to transcribe",
    "midi.source.stem": "Stem sent from Layers",
    "midi.source.run": "Audio of the current run",
    "midi.source.upload": "A file",
    "midi.source.none": "Nothing selected yet.",
    "midi.source.selected": "Source: `{name}`",
    "midi.upload.label": "Audio file (WAV, FLAC, MP3)",
    "midi.model.label": "Checkpoint for this run",
    "midi.instruments.label": "Only these instruments",
    "midi.instruments.placeholder": "drums, acoustic_piano",
    "midi.instruments.info": (
        "Leave everything unticked to transcribe whatever muscriptor hears."
    ),
    "midi.run": "▷  Transcribe to MIDI",
    "midi.status.idle": "Pick a source and press transcribe.",
    "midi.status.done": "Saved to `{path}` · {seconds} s",
    "midi.file.label": "MIDI file",
    "midi.payload.label": "What produced this file",
    "midi.plot.title": "Transcribed notes",
    "midi.plot.pitch": "MIDI pitch",
    "midi.plot.label": "Piano roll",
    "midi.preview.label": "Preview",
    "midi.empty.notes": "The transcription appears here",
    "midi.preview.summary": (
        "**{notes} notes** across {tracks} track(s) · {seconds} s · {tempo} BPM\n\n"
        "Tracks: {names}"
    ),
    "midi.preview.note": (
        "> The preview is synthesised from the notes with plain sine and noise "
        "voices — a check that they land where the audio does, not a rendering. "
        "Clicking the piano roll seeks the player."
    ),
    # ---- layers -> MIDI ----------------------------------------------------
    "layers.pick.none": "That row has no file behind it.",
    "layers.pick.selected": "Selected: `{name}`",
    "layers.send_to_midi": "→  Send to MIDI",
    # ---- muscriptor failures ------------------------------------------------
    "muscriptor.error.gated_repo": (
        "The weights are gated. Open the model page, accept CC BY-NC 4.0 — "
        "access is granted automatically — and try again."
    ),
    "muscriptor.error.token_missing": (
        "Hugging Face rejected the request as unauthenticated. Add a token in "
        "Settings, or set `HF_TOKEN` before starting the app."
    ),
    "muscriptor.error.token_scope": (
        "The token works but cannot read gated repositories. A fine-grained "
        "token needs *Read access to contents of all public gated repos you "
        "can access*."
    ),
    "muscriptor.error.repo_missing": "Hugging Face has no such repository.",
    "muscriptor.error.offline": (
        "Hugging Face is unreachable. Downloading needs a connection; "
        "transcribing with weights you already have does not."
    ),
    "muscriptor.error.cuda_oom": (
        "Not enough VRAM for this checkpoint. Try a smaller one, or switch the "
        "device to CPU."
    ),
    "muscriptor.error.package_missing": (
        "muscriptor is not installed in the `ai-music-muscriptor` environment."
    ),
    "muscriptor.error.file_missing": "The file is not there.",
    "muscriptor.error.stalled": (
        "The transcription process went silent. It was stopped; nothing was "
        "left half-written."
    ),
    "muscriptor.error.timeout": "The run went past its time limit and was stopped.",
    "muscriptor.error.http_error": "Hugging Face returned an error.",
    "muscriptor.error.failed": "The run failed.",
    "error.no_midi_source": "Choose what to transcribe",
    "error.no_sunofix_source": "Choose what to repair",
    "error.measure_first": "Measure the file before running a pass",
    "error.pick_stem": "Pick a stem in the table first",
    "error.midi_not_ready": "MIDI transcription is not set up yet — see Settings",
    # ---- detector cards ------------------------------------------------
    "detector.kind": "AI music detector",
    "detector.probability": "AI probability",
    "detector.status": "Status",
    "detector.caveat": "Caveat",
    "detector.caveat.title": "Caveat",
    "detector.unknown_device": "unknown",
    "detector.seconds": "{value} s",
    "status.not_applicable": "Not applicable",
    "status.error": "Error",
    "status.high": "High",
    "status.medium": "Medium",
    "status.low": "Low",
    "caveat.fst.floor": (
        "Lower bound of the FST scale; a false negative on newer generators is possible."
    ),
    "caveat.fst.ceiling": "Upper bound of the FST scale; this is not a calibrated guarantee.",
    "caveat.fst.general": (
        "Structural model; it can miss under generator shift and on material "
        "without a steady rhythm."
    ),
    "caveat.lofcz": (
        "Signal model; confirm the result with a second detector and with a "
        "known origin for the file."
    ),
    "caveat.generic": "The result depends on the model version and the input file.",
    # ---- metadata table ------------------------------------------------
    "meta.file": "File",
    "meta.format": "Format",
    "meta.duration": "Duration",
    "meta.sample_rate": "Sample rate",
    "meta.channels": "Channels",
    "meta.size": "Size",
    "meta.peak": "Peak",
    "meta.rms": "RMS",
    "meta.crest": "Crest factor",
    "meta.stereo_correlation": "Stereo correlation",
    "meta.mid_side": "Mid / Side",
    "unit.seconds": "s",
    "unit.hertz": "Hz",
    "unit.megabytes": "MB",
    "unit.kilohertz": "kHz",
    "unit.stereo": "stereo",
    "meta.empty": "No file loaded",
    "disc.file.stereo.title": "Stereo image",
    "unit.mono": "mono",
    "unit.percentage_points": "pp",
    # ---- help ----------------------------------------------------------
    "help.aria": "Explanation: {title}",
    "help.aria.warn": "Important: {title}",
    "help.measured": "What is measured",
    "help.reading": "How to read it",
    "help.limits": "Limitations",
    "help.lofcz.fakeprint.title": "lofcz: native fakeprint",
    "help.lofcz.lower_hull.title": "lofcz: spectrum and lower hull",
    "help.fst.stage1.title": "FST: Stage-1 classes",
    "help.fst.self_similarity.title": "FST: self-similarity",
    "help.fst.fusion_gate.title": "FST: fusion gate",
    "help.lofcz.fakeprint.measured": "The normalized frequency residue that is fed into the ONNX model.",
    "help.lofcz.fakeprint.reading": "Compare the shape, the peak frequencies and the change between A and B.",
    "help.lofcz.fakeprint.limits": "A single bin value is not an AI probability and carries no time information.",
    "help.lofcz.lower_hull.measured": "The local lower spectral floor, subtracted from the average spectrum.",
    "help.lofcz.lower_hull.reading": "The gap between spectrum and hull forms the model's residue.",
    "help.lofcz.lower_hull.limits": "The hull is preprocessing, not a separate classifier decision.",
    "help.fst.stage1.measured": "The two native class scores of a short 10-second segment.",
    "help.fst.stage1.reading": "Watch the stability of both classes and how they change between versions.",
    "help.fst.stage1.limits": "Upstream does not publish how indices 0/1 map to Real/Fake.",
    "help.fst.self_similarity.measured": "Pairwise similarity of MERT embeddings across beat-aligned segments.",
    "help.fst.self_similarity.reading": "A bright cell means the segments sit closer in the model's feature space.",
    "help.fst.self_similarity.limits": "Similarity is not a probability and depends on how the material is structured.",
    "help.fst.fusion_gate.measured": "The weight mixing content and structure inside Stage-2.",
    "help.fst.fusion_gate.reading": "Closer to 1 means more content; closer to 0 means more structure.",
    "help.fst.fusion_gate.limits": "The gate is an internal mixing weight, not a probability of AI.",
    # ---- interpretation ------------------------------------------------
    "interpret.heading": "How to read this run",
    "interpret.experimental_label": "Experimental interpretation.",
    "interpret.experimental_body": "The original detector outputs are above and are left unchanged.",
    "interpret.lofcz_available": "lofcz fakeprint is available as a native frequency input{peak}.",
    "interpret.lofcz_peak": "; strongest bin near {frequency} Hz",
    "interpret.fst_spread": "FST Stage-1 class 1 varies by {spread} across the stored segments.",
    "interpret.fst_gate": "Mean FST fusion gate = {value}; this is a content/structure mixing weight.",
    "interpret.missing": "Extended telemetry is missing; run the analysis again.",
    # ---- timeline summary ----------------------------------------------
    "timeline.empty": "The map is empty: no windows were built.",
    "timeline.window": "{start}–{end} s ({probability}%)",
    "timeline.summary": (
        "**Windows:** {count} (window {window} s, hop {hop} s) · "
        "**above 50%:** {above} · "
        "**range:** {minimum}–{maximum}%\n\n"
        "**Most prominent sections:** {hottest}"
    ),
    # ---- layers ---------------------------------------------------------
    "layer.not_measured": "not measured",
    "layer.high_priority": "rework first",
    "layer.low_priority": "low priority",
    # ---- plots ----------------------------------------------------------
    "plot.spectrogram": "Spectrogram",
    "plot.spectrogram_3d": "3D spectrogram",
    "plot.dynamics": "Dynamics over time",
    "plot.average_spectrum": "Average spectrum",
    "plot.difference": "Difference: current − baseline",
    "plot.axis.time": "Time, s",
    "plot.axis.frequency": "Frequency, Hz",
    "plot.axis.level": "Level, dBFS",
    "plot.axis.rms": "RMS, dBFS",
    "plot.hover.time": "Time",
    "plot.hover.frequency": "Frequency",
    "plot.hover.level": "Level",
    "plot.hover.zone": "Zone",
    "plot.hover.change": "Change",
    "plot.current": "Current",
    "plot.baseline": "Baseline",
    "zone.sub_bass": "Sub-bass: foundation and infra-low",
    "zone.bass": "Bass: weight and fundamental",
    "zone.low_mid": "Low mid: density and mud",
    "zone.mid": "Mid: body and intelligibility",
    "zone.presence": "Presence: attack and definition",
    "zone.highs": "Highs: brightness and sibilance",
    "zone.air": "Air: top end and noise",
    # ---- telemetry plots -------------------------------------------------
    "telemetry.lofcz.spectrum": "lofcz · spectrum and lower hull",
    "telemetry.lofcz.residue": "Normalized residue",
    "telemetry.fst.stage1": "FST · native Stage-1 classes",
    "telemetry.axis.segment_start": "Segment start, s",
    "telemetry.axis.segment": "Segment, s",
    "telemetry.axis.segment_b": "Segment B, s",
    "telemetry.layers.empty": "No layer could be measured",
    "telemetry.layers.title": "Layers by fingerprint strength",
    "telemetry.timeline.name": "lofcz per window",
    "telemetry.timeline.window": "Window: %{customdata[0]:.1f}–%{customdata[1]:.1f} s",
    "telemetry.timeline.residue": "Mean residue: %{customdata[2]:.2f} dB",
    "telemetry.timeline.threshold": "50% threshold",
    "telemetry.timeline.gate": "FST fusion gate (right axis)",
    "telemetry.timeline.gate_hover": "Segment at %{x:.1f} s",
    "telemetry.timeline.fst_class": "FST Stage-1 class {index} (right axis)",
    "telemetry.timeline.fst_axis": "FST per segment, 0–1",
    "telemetry.timeline.title": "Map: where the fingerprint shows",
    "telemetry.timeline.axis": "lofcz per window, %",
    "telemetry.version_a": "Version A",
    "telemetry.version_b": "Version B",
    "telemetry.similarity.mismatch": (
        "The beat-aligned segment grids of A and B do not match; no Δ matrix is built"
    ),
    # ---- service messages -------------------------------------------------
    "error.restart_remote": (
        "The server is bound to {host}, not to this machine — restart it from "
        "the terminal that started it."
    ),
    "error.no_audio": "Add an audio file",
    "error.no_detector": "Select at least one detector",
    "error.unsupported_format": "WAV, FLAC and MP3 are supported",
    "error.audio_missing": "Audio file not found: {path}",
    "error.no_layers": "Add layer files",
    "error.no_reference": "An analysed track or reference files are required",
    "error.no_run": "Analyse a file first, or select a run",
    "error.run_audio_missing": "Run audio file not found: {path}",
    "error.same_version": "Select two different versions",
    "error.window_positive": "Window and hop must be greater than zero",
    "error.files_missing": "Files not found: {files}",
    "error.no_audio_data": "{name} contains no audio data",
    "progress.features": "Extracting audio features",
    "progress.saving": "Saving the result",
    "progress.done": "Done",
    "progress.layer": "Layer {index} of {total}: {name}",
    "progress.layers_done": "Layers processed",
    "progress.metrics": "Metrics {index} of {total}: {name}",
    "progress.metrics_done": "Metrics computed",
    "progress.detector": "Running {detector}",
    "progress.detectors_done": "Detectors finished",
    # ---- empty-plot placeholders -----------------------------------------
    "empty.start": "Add a file and run the analysis",
    "empty.surface": "The 3D surface appears after an analysis",
    "empty.rms": "The whole track appears once a file is loaded",
    "empty.spectrum": "The average spectrum appears after an analysis",
    "empty.timeline": "Build the map after an analysis",
    "empty.layers": "Add layers and run the measurement",
    "empty.run_lofcz": "Run lofcz",
    "empty.run_fst": "Run FST",
    "empty.lofcz_telemetry": "No lofcz telemetry — analyse the run again",
    "empty.fakeprint": "Native fakeprint is unavailable",
    "empty.fst_telemetry": "No FST telemetry — analyse the run again",
    "empty.similarity": "Self-similarity is unavailable",
    "empty.gate": "Fusion gate is unavailable",
    "empty.lofcz_ab": "lofcz A/B needs telemetry from both versions",
    "empty.fst_ab": "FST A/B needs telemetry from both versions",
    "empty.pick_two": "Select two versions",
    "empty.pick_ab_telemetry": "Select A and B with stored telemetry",
    "empty.pick_lofcz": "Select A and B with lofcz telemetry",
    "empty.pick_fst": "Select A and B with FST telemetry",
    "empty.difference": "The B − A map appears after a comparison",
    "empty.heatmap_duration": "Heatmap unavailable: durations differ by more than 5%",
    # ---- controls ---------------------------------------------------------
    "app.high_detail": "Increase 3D detail",
    "app.plot.fulltrack": "Whole track",
    "app.timeline.window": "Window, s",
    "app.timeline.hop": "Hop, s",
    "app.timeline.build": "Build map",
    "app.layers.files": "Layers (WAV, FLAC, MP3)",
    "app.layers.button": "Measure layers",
    "app.artifacts.references": "References (optional)",
    "app.artifacts.button": "Compute metrics",
    "app.fst_npz": "FST · full telemetry NPZ",
    "app.version_a.info": "The original or previous processing",
    "app.version_b.info": "New processing of the same material",
    "app.compare.button": "Compare versions",
    "app.compare.pin": "Pin as A",
    "app.compare.unpin": "Unpin",
    "app.compare.detector_label": "Change in detector scores",
    "app.compare.spectrum_label": "Average spectrum overlay",
    "app.compare.difference_label": "Spectral difference B − A",
    "app.compare.metric_label": "Change in metrics",
    "app.compare.native_heading": "#### Change in the detectors' native measurements",
    "app.history.title": "Analysis history",
    "app.history.subtitle": "Saved runs are used for manual version comparison.",
    "app.status.done": "Status: done · run `{run_id}` saved.",
    # ---- table headers ----------------------------------------------------
    "table.metadata.parameter": "Parameter",
    "table.metadata.value": "Value",
    "table.metadata.unit": "Unit",
    "table.layer.name": "Layer",
    "table.layer.residue": "Mean residue, dB",
    "table.layer.duration": "Duration, s",
    "table.layer.priority": "Priority",
    "table.artifact.file": "File",
    "table.artifact.attack": "Attack, dB",
    "table.artifact.rolloff": "Rolloff 95%, kHz",
    "table.artifact.cliff": "HF cliff, dB/oct",
    "table.artifact.noise_floor": "Noise floor, dBFS",
    "table.artifact.flatness": "Floor flatness",
    "table.artifact.corr_low": "Corr. low",
    "table.artifact.corr_high": "Corr. high",
    # Distinct from `cliff`, which is the steepness: this is where it stops.
    "table.artifact.cutoff": "HF edge, kHz",
    "table.artifact.tonal": "Strongest ridge, dB",
    "table.sunofix.before": "Before",
    "table.sunofix.after": "After",
    # `table.delta` reads "Δ B−A", which belongs to the version comparison. The
    # A/B here is one file against itself, so it says so.
    "table.sunofix.delta": "Δ after−before",
    "table.peaks.frequency": "Frequency, Hz",
    "table.peaks.fakeprint": "Fakeprint",
    "table.detector": "Detector",
    "table.delta": "Δ B−A",
    "table.metric": "Metric",
    "table.unit": "Unit",
    "table.history.date": "Date UTC",
    "table.history.note": "Note",
    "table.history.run_id": "Run ID",
    # ---- comparison messages ----------------------------------------------
    "compare.initial": "Select two different saved versions.",
    "compare.reset": "Comparison reset after a new analysis. Select two versions again.",
    "compare.pinned": "Version A pinned: `{filename}`.",
    "compare.unpinned": "Version A unpinned; the two latest runs are selected.",
    "compare.result": "Version B − Version A: `{version_b}` − `{version_a}`.",
    "compare.duration_mismatch": (
        "Comparing `{version_a}` and `{version_b}`. Durations differ by more "
        "than 5%, so the temporal heatmap is hidden; scalar and detector "
        "deltas are available."
    ),
    "error.analyze_first": "Analyse a track first",
    "error.pick_both": "Select Version A and Version B",
    "error.pick_a": "Select Version A",
    # ---- tab documentation -------------------------------------------------
    "lead.detector_data": (
        "The models' own preprocessing and outputs, unaltered. Each badge "
        "explains the chart below it."
    ),
    "lead.timeline": (
        "Where along the track the fingerprint shows. Clicking the curve seeks "
        "the player."
    ),
    "lead.layers": (
        "Measure the separate tracks a mix was built from, to see which one "
        "carries the fingerprint."
    ),
    "lead.artifacts": (
        "Measured from the signal, with no detector involved — so add "
        "references and read your track next to them."
    ),
    "lead.comparison": "Two processings of one source, read as `B − A`.",
    "lead.midi": (
        "Transcribe audio into notes with muscriptor. Runs locally, on your GPU."
    ),
    "lead.sunofix": (
        "Repairing generation artifacts, aimed by the **Artifacts** "
        "measurements rather than by ear. Measure first — the repairs tick "
        "themselves, and each says which figure put it there."
    ),
    # ---- SunoFix -----------------------------------------------------------
    "disc.sunofix.level.title": "What happens to the level",
    "disc.sunofix.level.body": (
        "The level of the source is kept. Gain is only ever pulled back, and "
        "only when true peak would leave -1 dBTP.\n\n"
        "There is no normalisation and no limiter, because an A/B where one "
        "side is louder proves nothing: louder reads as better whatever was "
        "done to it. The output is a mastering-ready WAV, not a master."
    ),
    "disc.sunofix.masking.title": "Repairs that have to be proven separately",
    "disc.sunofix.masking.body": (
        "**Restore air** and **noise floor** both synthesise material that was "
        "not in the file. Both remove a signal detectors read easily — a "
        "lowpass wall, a floor too clean to be a recording.\n\n"
        "A lower score is therefore not evidence that either one helped. Run "
        "it on its own, and check the score against a blind listen. A repair "
        "that only fools the detector is a failure, not a feature."
    ),
    "sunofix.source.label": "1. What to repair",
    "sunofix.source.run": "The analysed track",
    "sunofix.source.upload": "A file",
    "sunofix.source.none": "Nothing chosen yet.",
    "sunofix.upload.label": "Audio file",
    "sunofix.measure": "▷  Measure and recommend",
    "sunofix.repair.heading": "### 2. Repair — ticked by the measurements",
    "sunofix.repair.pending": "Measure first — until then there is nothing to argue from.",
    "sunofix.taste.heading": "### 3. Musical pass — taste only",
    "sunofix.preset.label": "Preset",
    "sunofix.preset.repair_only": "Repair only",
    "sunofix.preset.soft_glue": "Soft glue",
    "sunofix.preset.open_top": "Open top",
    "sunofix.preset.de_harsh": "De-harsh",
    "sunofix.preset.add_body": "Add body",
    "sunofix.preset.desc.repair_only": (
        "The repairs and nothing else, plus a gentle cleanup. No colour added."
    ),
    "sunofix.preset.desc.soft_glue": (
        "A softer pass for a track that already sounds close."
    ),
    "sunofix.preset.desc.open_top": (
        "Opens the top end. The only pass that leaves tone flat, because "
        "darkening it would undo the point."
    ),
    "sunofix.preset.desc.de_harsh": (
        "Takes the harshness down while keeping the track musical."
    ),
    "sunofix.preset.desc.add_body": "More body, warmth and perceived fullness.",
    "sunofix.finetune": "Fine-tune",
    "sunofix.warmth.heading": "**Warmth** — harmonic density. Subtle on a loud master.",
    "sunofix.warmth.enabled": "Warmth on",
    "sunofix.warmth.character": "Character",
    "sunofix.warmth.character.tape": "Tape",
    "sunofix.warmth.character.tube": "Tube",
    "sunofix.warmth.character.console": "Console",
    "sunofix.warmth.character.warm": "Warm",
    "sunofix.warmth.drive": "Drive",
    "sunofix.warmth.mix": "Mix",
    "sunofix.warmth.tone": "Tone",
    "sunofix.warmth.tone.info": "Tilt around 1 kHz. Off when warmth is off.",
    "sunofix.cleanup.heading": (
        "**HF cleanup** — quiet high-frequency debris only."
    ),
    "sunofix.cleanup.enabled": "Cleanup on",
    "sunofix.cleanup.strength": "Strength",
    "sunofix.cleanup.strength.soft": "Soft",
    "sunofix.cleanup.strength.medium": "Medium",
    "sunofix.cleanup.strength.strong": "Strong",
    "sunofix.cleanup.strength.tails_only": "Tails only",
    "sunofix.cleanup.strength.air_clean": "Air clean",
    "sunofix.run": "▷  Run the pass",
    "sunofix.status.idle": "Status: measure a file, then run a pass.",
    "sunofix.status.measured": (
        "Measured `{name}`. Repairs recommended: {count}. Every tick below says "
        "which figure put it there."
    ),
    "sunofix.status.nothing": (
        "Nothing was switched on, so nothing changed. Tick a repair or enable a "
        "musical pass."
    ),
    "sunofix.status.done": "Wrote `{name}`. Ran: {modules}. {level}",
    "sunofix.status.level_kept": "The level of the source was kept.",
    "sunofix.status.level_pulled": (
        "True peak was over the ceiling, so the output was pulled back by "
        "{gain} dB."
    ),
    "sunofix.delta.label": "What the pass measurably did (after − before)",
    "sunofix.preview.label": "Result",
    "sunofix.file.label": "Repaired WAV",
    "sunofix.badge.masking": "prove separately",
    "sunofix.module.de_artifact": "De-artifact",
    "sunofix.module.fix_transients": "Transients",
    "sunofix.module.restore_air": "Restore air",
    "sunofix.module.restore_floor": "Noise floor",
    "sunofix.module.fix_stereo": "Stereo image",
    "sunofix.module.hf_cleanup": "HF cleanup",
    "sunofix.module.warmth": "Warmth",
    "sunofix.module.tone_tilt": "Tone",
    "sunofix.module.level_policy": "Level",
    "sunofix.why.de_artifact": (
        "{prominence} dB of tonal prominence at {frequencies} kHz — steady "
        "ridges of the kind a generator leaves."
    ),
    "sunofix.why.de_artifact.none": (
        "Nothing stands out of the upper mids; there is no ridge to notch."
    ),
    "sunofix.why.fix_transients": (
        "Attacks rise by only {attack} dB, which reads as smearing."
    ),
    "sunofix.why.fix_transients.none": (
        "Attacks rise by {attack} dB — inside the range real material sits in."
    ),
    "sunofix.why.restore_air": (
        "The top end stops at {cutoff} kHz and falls at {slope} dB per octave: "
        "a wall, not a rolloff."
    ),
    "sunofix.why.restore_air.none": (
        "The top end rolls off on its own; there is no wall to build above."
    ),
    "sunofix.why.restore_floor": (
        "The floor sits at {floor} dBFS with a flatness of {flatness} — "
        "cleaner and flatter than a recording ever is."
    ),
    "sunofix.why.restore_floor.none": (
        "The floor already looks like something that was recorded."
    ),
    "sunofix.why.fix_stereo": (
        "High-band correlation is {correlation}: outside the range where the "
        "image reads as an image."
    ),
    "sunofix.why.fix_stereo.none": (
        "High-band correlation is {correlation} — an ordinary stereo image, "
        "left alone."
    ),
    # ---- moved method notes --------------------------------------------------
    "disc.spectrum.reading.title": "Reading the spectrogram",
    "disc.spectrum.reading.measured": (
        "Level per frequency band over time, straight from the audio."
    ),
    "disc.spectrum.reading.reading": (
        "Use it as a measurement of the audio, not as an AI classifier in its "
        "own right. Compare the two detector scores first."
    ),
    "disc.spectrum.reading.limits": (
        "A spectrogram shows what a codec or a generator did to the signal; it "
        "says nothing on its own about where the music came from."
    ),
    "disc.timeline.method.title": "What a window value is, and is not",
    "disc.timeline.method.body": (
        "A global score does not say what to fix. Here the fakeprint is "
        "computed with a sliding window, so you can see which sections pull the "
        "score up.\n\n"
        "The model was trained on an average over a whole track, so window "
        "values are a **relative map inside one track**, not a calibrated "
        "probability per second. Compare windows against other windows of the "
        "same track; comparing one against another track's global score means "
        "nothing. The shorter the window, the noisier the estimate."
    ),
    "disc.layers.what_to_load.title": "What to load, and what comes back",
    "disc.layers.what_to_load.body": (
        "Load the individual tracks **before mixdown** — the ones the studio "
        "track was built from. Each is measured separately, so you can see "
        "which one carries the fingerprint: drums 97% and live guitar 15%, for "
        "example.\n\n"
        "This is a diagnostic pass. It is **not saved** to the history and "
        "creates no version: to record a layer as a version, analyse it the "
        "normal way on the left.\n\n"
        "Only lofcz is used. FST needs detectable beats, which most stems do "
        "not have, and on a full mix it is available in the main analysis "
        "anyway."
    ),
    "disc.layers.separation.title": "Do not split a finished mix for this",
    "disc.layers.separation.body": (
        "A separation tool adds its own artifacts and raises the score by "
        "itself, so what you would be measuring is the separator rather than "
        "the material. Use the tracks you actually recorded or generated."
    ),
    "disc.artifacts.metrics.title": "What each column measures",
    "disc.artifacts.metrics.body": """
      <ul>
        <li><strong>Attack</strong> — the typical sharpest rise in loudness over
        20 ms. Smeared transients lower it.</li>
        <li><strong>Rolloff 95%</strong> — where the bulk of the spectral energy
        ends.</li>
        <li><strong>HF cliff</strong> — the steepest decay above 4 kHz. A
        strongly negative value means a hard wall from a codec or generator;
        live material rolls off gently.</li>
        <li><strong>Noise floor and its flatness</strong> — a very low and very
        flat floor means sterile digital material with no room and no
        signal-path noise.</li>
        <li><strong>Low and high correlation</strong> — a collapsed or
        unnaturally wide stereo image.</li>
      </ul>
    """,
    "disc.artifacts.compare.title": "Compare like with like",
    "disc.artifacts.compare.body": (
        "**MP3 produces an HF cliff on its own**, regardless of where the music "
        "came from, so MP3 against WAV shows the codec rather than the "
        "generator. For the same reason, do not compare a single stem against a "
        "full mix.\n\n"
        "On their own these numbers mean almost nothing. Add references — your "
        "own live recordings, or commercial tracks — and read your track next "
        "to them. The measurement method is identical for every file."
    ),
    "disc.comparison.method.title": "What makes a comparison useful",
    "disc.comparison.method.body": (
        "Choose, for example, the original stem as **Version A** and the same "
        "stem after processing as **Version B**. The difference is built as "
        "`B − A`.\n\n"
        "Comparing different songs mostly reflects differences in the musical "
        "material and rarely produces a useful conclusion."
    ),
    "disc.midi.stems.title": "Send it stems, not mixes",
    "disc.midi.stems.body": (
        "Polyphonic transcription of a dense mix is not a solved problem, and "
        "the difference between a bass stem and the full track it came from is "
        "the difference between a result worth editing and one worth deleting."
        "\n\n"
        "That is what the button on the **Layers** tab is for: measure the "
        "stems, click the row you want, send it straight here."
    ),
    "disc.midi.reproducibility.title": "What is recorded with every file",
    "disc.midi.reproducibility.body": (
        "Decoding is greedy — no sampling, no temperature — so the same audio "
        "with the same settings produces the same MIDI.\n\n"
        "Every run writes a JSON file beside the `.mid` with the checkpoint, "
        "the decoding parameters and the muscriptor version, so an old "
        "transcription stays interpretable after an update. Files land in "
        "`output/midi/`, not in a cache that is wiped daily."
    ),
    "disc.midi.setup.title": "Setup",
    # ---- the app's one long-form licence statement ---------------------------
    "disc.licence.weights.title": "Licence on the transcription weights",
    "disc.licence.weights.body": (
        "The muscriptor **code** is MIT, and so is this wrapper. The **model "
        "weights are CC BY-NC 4.0 — non-commercial use only**, and the model "
        "card adds a further condition: the output must not be used for illegal "
        "or unauthorised activity, explicitly including transcribing music you "
        "hold no rights to.\n\n"
        "If you release what you build from these transcriptions, that boundary "
        "is yours to judge. Every tool in this workspace carries its own terms; "
        "the README lists them."
    ),
    # ---- MIDI guides ---------------------------------------------------------
    # Authored markup, not user input: these bodies carry lists and links and are
    # inserted unescaped by disclosure_html.
    "guide.midi.basics.title": "Opening the MIDI in FL Studio",
    "guide.midi.basics.body": """
      <p>Two routes in. Dragging the <code>.mid</code> from the browser onto the
      playlist is the fast one; <em>File &rarr; Import &rarr; MIDI file</em>
      gives you the import options, including one channel per track, which is
      what you want when muscriptor found several instruments.</p>
      <ol>
        <li><strong>Set the project tempo first.</strong> The transcription
        carries a detected tempo; if the project disagrees, everything lands off
        the grid and looks like a transcription error when it is not.</li>
        <li><strong>Do not quantise straight away.</strong> Listen to the raw
        notes against the audio first. Quantising a bad transcription hides the
        mistakes instead of showing them.</li>
        <li><strong>Clean the piano roll before anything else.</strong> Short
        ghost notes and octave doubles are the usual junk. Deleting them takes a
        minute and saves an hour of wondering why a part sounds wrong.</li>
        <li><strong>Keep the original file.</strong> Every transcription is
        saved to <code>output/midi/</code> with a JSON note of the checkpoint and
        settings beside it, so an edited version never becomes the only copy.</li>
      </ol>
      <p>Reference:
      <a href="https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/fformats_other_mid.htm"
      target="_blank" rel="noopener">MIDI files in the FL Studio manual</a> ·
      <a href="https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/pianoroll.htm"
      target="_blank" rel="noopener">Piano roll</a> ·
      <a href="https://www.image-line.com/fl-studio-learning/" target="_blank"
      rel="noopener">Image-Line's own video tutorials</a>.</p>
    """,
    "guide.midi.drums.title": "Drums: MIDI into FPC, and where breaks come from",
    "guide.midi.drums.body": """
      <p>Drum MIDI is the one part that pays off immediately, because replacing
      a generated kit with real samples is exactly the kind of substitution that
      lowers a detector score for the right reason.</p>
      <p><strong>FPC</strong> is FL Studio's pad sampler and the natural
      destination. Load an empty FPC, drop your samples onto the pads, then open
      the transcribed MIDI in its piano roll and line the pad keys up with the
      notes that arrived. Each pad's trigger key is set in Play Key/Octave, so
      the mapping is adjusted on the pad, not by moving every note.</p>
      <p>What to watch for in a transcription: hi-hats come out dense and often
      over-detected, kick and snare are usually solid, and ghost snares are the
      first thing to thin out. Transcribe the drum stem on its own rather than
      the full mix — bass leaking into the kick band is what produces phantom
      hits.</p>
      <p>Sources for the samples themselves:
      <a href="https://www.musicradar.com/tag/sampleradar" target="_blank"
      rel="noopener">MusicRadar SampleRadar</a> for free packs, including a lot
      of breakbeat material (check each pack's own terms) ·
      <a href="https://splice.com/sounds/genres/drum-and-bass/packs"
      target="_blank" rel="noopener">Splice drum &amp; bass packs</a> on a
      subscription, which is where most current one-shots and breaks live.</p>
      <p>Reference:
      <a href="https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/plugins/FPC.htm"
      target="_blank" rel="noopener">FPC in the FL Studio manual</a>.</p>
    """,
    "guide.midi.acoustic.title": "Guitar, strings, orchestra",
    "guide.midi.acoustic.body": """
      <p>Melodic parts need a sampler with real recordings behind it; a synth
      preset will not sell a violin line. Two free routes that cover most of it:</p>
      <ul>
        <li><a href="https://splice.com/instrument" target="_blank"
        rel="noopener">Splice INSTRUMENT</a> — the former Spitfire LABS library,
        now under Splice. VST3/AU, free presets covering strings, pianos and
        more, with paid packs on top.</li>
        <li><a href="https://www.plogue.com/products/sforzando.html"
        target="_blank" rel="noopener">Plogue sforzando</a> — a free SFZ player.
        Plain and ugly, but it opens the enormous body of free SFZ libraries
        that exist for orchestral and folk instruments, accordion included.</li>
      </ul>
      <p>What the transcription will and will not give you: pitch and timing,
      yes. Articulation, no — legato, staccato, bowing and slides are not in the
      MIDI and have to be played back in by hand, usually through a keyswitch or
      an expression lane. A transcribed string line always sounds mechanical
      until that is done; that is the work, not a bug.</p>
      <p>Guitar in particular transcribes as notes with no fret or string
      information, so chord voicings come out in whatever octave the model
      chose. It is usually faster to treat the result as a chord chart and
      re-voice it than to fight the notes it produced.</p>
    """,
    "guide.midi.bass.title": "Bass and synths",
    "guide.midi.bass.body": """
      <p>Bass is where transcription is least reliable, and it is worth knowing
      why before blaming the model: a sub-bass fundamental below roughly 40 Hz
      often lands an octave off, and heavily distorted or reese basses have so
      much harmonic content that the model hears the harmonics as the note.</p>
      <p>Practical order of work: transcribe the bass stem alone, check the
      octave against the audio before anything else, and expect to correct the
      octave on whole phrases rather than single notes.</p>
      <p>For playback, any subtractive or wavetable synth will do.
      <a href="https://vital.audio/" target="_blank" rel="noopener">Vital</a>
      has a free tier with the full synth and a limited preset library, and
      FL Studio's own Sytrus and 3xOsc are already installed and perfectly
      capable of a clean sub.</p>
      <p>One thing that matters more than the synth: a transcribed bass line
      keeps the note lengths of the original, which for a plucked or gated bass
      are usually too long. Shortening the notes to match the groove does more
      for the feel than any preset choice.</p>
    """,
}

_RU: dict[str, str] = {
    # ---- shell ---------------------------------------------------------
    "app.title": "AI Music Lab",
    "app.eyebrow": "LOCAL FORENSIC AUDIO WORKSPACE",
    "app.tagline": "Локальный анализ одного трека или стема",
    "app.language": "Язык",
    "app.restart.confirm": (
        "Перезапустить сервер?\n\n"
        "Подхватятся изменения в стилях, переводах и Python. Эта страница "
        "перезагрузится с нуля; всё, что не проанализировано, потеряется. "
        "Сохранённые запуски не трогаются."
    ),
    "app.restart.running": "Перезапуск — страница перезагрузится сама.",
    "app.audio.label": "1. Аудиофайл",
    "app.note.label": "Заметка к версии",
    "app.note.placeholder": "Например: vocal после de-esser v2",
    "app.detectors.label": "2. Детекторы",
    "app.detectors.lofcz": "lofcz · сигнальная модель",
    "app.detectors.fst": "FST · структурная модель",
    "app.analyze": "▷  Запустить анализ",
    "app.status.ready": "Статус: готов к анализу.",
    "app.method_note": (
        "> Результаты — измерения конкретных версий моделей, а не "
        "доказательство происхождения аудио."
    ),
    "app.empty.detectors": (
        "После анализа здесь появятся результаты lofcz и FST. Сначала "
        "сопоставьте два score между собой."
    ),
    # ---- tabs ----------------------------------------------------------
    "tab.group.analysis": "Анализ",
    "tab.group.editing": "Редактирование",
    "tab.edit.sunofix": "SunoFix",
    "tab.edit.midi": "В MIDI",
    "tab.spectrum": "Спектр",
    "tab.timeline": "Карта по времени",
    "tab.layers": "Слои",
    "tab.artifacts": "Артефакты",
    "tab.detector_data": "Данные детекторов",
    "tab.comparison": "Сравнение версий",
    "tab.technical": "Технические данные",
    # ---- settings panel --------------------------------------------------
    "settings.open": "⚙  Настройка muscriptor",
    "settings.title": "### Настройка muscriptor",
    "settings.close": "Закрыть",
    "settings.token.heading": "#### Токен Hugging Face",
    "settings.token.intro": (
        "Нужен только чтобы скачать gated-веса muscriptor. Остаётся на этой "
        "машине."
    ),
    "disc.token.handling.title": "Куда токен попадает и куда нет",
    "disc.token.handling.body": (
        "Он передаётся локальному процессу muscriptor переменной окружения и "
        "никуда больше не попадает: ни в историю запусков, ни в панель "
        "технических данных, ни в логи. Обратно он вам здесь тоже не "
        "показывается — только последние четыре символа, чтобы понимать, какой "
        "токен сохранён.\n\n"
        "Сохранённый здесь, он лежит в `data/settings.json` открытым текстом — "
        "это локальный файл без защиты сверх вашей учётной записи. Если держать "
        "его на диске не хочется, задайте `HF_TOKEN` в окружении до запуска "
        "приложения: он имеет приоритет над сохранённым здесь."
    ),
    "settings.token.label": "Токен",
    "settings.token.placeholder": "hf_…",
    "settings.token.save": "Сохранить токен",
    "settings.token.clear": "Удалить токен",
    "settings.token.status.env": (
        "Используется `HF_TOKEN` из окружения. Сохранённый здесь игнорируется."
    ),
    "settings.token.status.stored": "Сохранён в `data/settings.json`: `{fingerprint}`",
    "settings.token.status.none": "Токена нет. Веса скачать не получится.",
    "settings.token.cleared": "Токен удалён из `data/settings.json`.",
    "settings.token.empty": "Сначала введите токен.",
    "settings.links": (
        '<ul class="settings-links">'
        '<li><a href="https://huggingface.co/settings/tokens" target="_blank" '
        'rel="noopener">Создать токен</a> — достаточно токена типа '
        "<strong>Read</strong>. Если сделаете вместо него "
        "<em>fine-grained</em>, до gated-репозиториев он не достанет, пока не "
        "отмечен пункт <em>Read access to contents of all public gated repos "
        "you can access</em>. Эта одна галочка — самая частая причина, по "
        "которой загрузка не идёт.</li>"
        '<li><a href="https://huggingface.co/MuScriptor/muscriptor-large" '
        'target="_blank" rel="noopener">Принять лицензию модели</a> — откройте '
        "страницу того размера, которым собираетесь пользоваться, и примите "
        "её условия. Доступ выдаётся автоматически.</li></ul>"
    ),
    "settings.license.accept": "Я прочитал условия CC BY-NC 4.0 на веса",
    "settings.model.heading": "#### Модель транскрипции",
    "settings.model.label": "Чекпоинт",
    "settings.model.small": "small · 103M · ~0.4 ГБ",
    "settings.model.medium": "medium · 307M · ~1.2 ГБ",
    "settings.model.large": "large · 1.4B · ~5.6 ГБ",
    "settings.model.note": (
        "Больше — точнее транскрипция и больше VRAM. Загрузка занимает весь "
        "интерфейс до конца: приложение выполняет одну задачу за раз."
    ),
    "settings.download": "Скачать веса",
    "settings.download.done": "`{model}` скачан и проверен.",
    "settings.check": "Проверить окружение",
    "settings.repos.heading": "#### Апстрим-репозитории",
    "settings.repos.note": (
        "Детекторы и транскрайбер — отдельные клоны рядом с этим репозиторием. "
        "Детекторы удерживаются на коммитах, против которых обёртка проверялась, "
        "чтобы их score оставались сравнимыми между запусками: здесь они "
        "показываются, но из интерфейса не обновляются. muscriptor следит за "
        "своей веткой и может быть перемотан вперёд."
    ),
    "settings.repos.refresh": "Обновить статус",
    "settings.repos.pull": "Обновить muscriptor",
    # ---- readiness checklist ---------------------------------------------
    "readiness.heading": "Перевод в MIDI",
    "readiness.ready": "Готово к работе.",
    "readiness.blocked": "Ещё не настроено — {detail}",
    "readiness.unverified": (
        "Готово. Проверка пакета не запускалась; транскрипция сама сообщит о "
        "проблеме, если она есть."
    ),
    "readiness.item.clone": "Клон muscriptor",
    "readiness.item.env": "Conda-среда",
    "readiness.item.license": "Лицензия подтверждена",
    "readiness.item.token": "Токен Hugging Face",
    "readiness.item.weights": "Веса скачаны",
    "readiness.item.package": "Проверка пакета",
    "readiness.fix.clone": (
        "Клонируйте `https://github.com/muscriptor/muscriptor.git` рядом с этим "
        "репозиторием."
    ),
    "readiness.fix.env": (
        "Создайте среду `ai-music-muscriptor` — см. страницу MIDI в "
        "документации."
    ),
    "readiness.fix.license": (
        "Откройте настройки и подтвердите, что прочитали условия CC BY-NC 4.0."
    ),
    "readiness.fix.token": "Добавьте токен Hugging Face в настройках.",
    "readiness.fix.weights": "Скачайте выбранный чекпоинт в настройках.",
    "readiness.fix.package": (
        "Запустите проверку окружения в настройках, чтобы увидеть, что "
        "сообщает адаптер."
    ),
    "readiness.not_checked": "не проверялось",
    # ---- per-detector settings -------------------------------------------
    "detector.settings.open": "Настройки",
    "detector.settings.title": "{detector} · настройки",
    "detector.settings.state": "Состояние",
    "detector.settings.run": "Параметры запуска",
    "detector.settings.upstream": "Апстрим",
    "detector.settings.none": (
        "У этого детектора пока нечего настраивать — он работает на умолчаниях "
        "апстрима."
    ),
    "detector.settings.save": "Сохранить",
    "detector.settings.saved": "Сохранено. Применится со следующего запуска.",
    "detector.settings.close": "Закрыть",
    "detector.ready.item.clone": "Клон апстрима",
    "detector.ready.item.env": "Conda-среда",
    "detector.ready.item.weights": "Веса",
    "detector.ready.ok": "Готов к запуску.",
    "detector.ready.blocked": "Запустить нельзя — {detail}",
    "detector.ready.fix.clone": (
        "Склонируйте репозиторий апстрима рядом с этим — см. «Начало работы»."
    ),
    "detector.ready.fix.env": (
        "По этому пути нет Python нужной среды. Создайте её или укажите "
        "существующую через `AI_MUSIC_*_PYTHON`."
    ),
    "detector.ready.fix.weights": (
        "Скачайте контрольные точки в `models/` — источники и контрольные суммы "
        "на странице «Модели»."
    ),
    "provision.install": "Доустановить недостающее",
    "provision.recheck": "Проверить снова",
    "provision.log": "Ход установки",
    "provision.done": "Готово. Состояние выше перечитано.",
    "provision.handover": "Передайте это ИИ-агенту",
    "provision.no_conda": (
        "Conda не найдена. Это предусловие, а не то, что приложение ставит "
        "само, — установите Miniconda и возвращайтесь."
    ),
    "provision.occupied": (
        "В этой папке уже есть файлы, поверх них клонировать не буду: {detail}"
    ),
    "provision.stalled": (
        "Шаг замолчал и был остановлен — обычно это запрос ввода, ответить на "
        "который отсюда нельзя. {detail}"
    ),
    "provision.timeout": "Шаг шёл слишком долго и был остановлен. {detail}",
    "provision.failed": "Шаг завершился ошибкой. {detail}",
    "provision.checksum": (
        "Загруженный файл не сошёлся с опубликованной контрольной суммой и был "
        "удалён: {detail}"
    ),
    "provision.error": "{detail}",
    "disc.provision.manual.title": "Две контрольные точки придётся скачать руками",
    "disc.provision.manual.body": (
        "`Stage-1.ckpt` и `Stage-2.ckpt` для FST лежат на Google Drive, "
        "который отдаёт файлы такого размера через страницу подтверждения — "
        "стабильной прямой ссылки, которую можно автоматизировать, там нет. "
        "Шаг установки печатает обе ссылки и точные пути, куда файлы должны "
        "лечь; положите их туда и нажмите **Проверить снова** — контрольные "
        "суммы сверяются до того, как что-нибудь позеленеет. Всё остальное — "
        "клон, среда, маленькая ONNX-модель — делается само."
    ),
    "detector.upstream.repository": "Репозиторий",
    "detector.upstream.head": "HEAD",
    "detector.upstream.match": "проверенный коммит",
    "detector.upstream.drift": "проверялось на {pinned}",
    "detector.upstream.missing": "клон не найден",
    "detector.fst.batch.title": "Почему это и есть весь вопрос по памяти",
    "detector.fst.batch.label": "Сегментов за проход backbone",
    "detector.fst.batch.1": "1 · минимум памяти MPS",
    "detector.fst.batch.2": "2 · по умолчанию на macOS",
    "detector.fst.batch.4": "4 · 3,7 ГБ видеопамяти",
    "detector.fst.batch.8": "8 · 4,8 ГБ",
    "detector.fst.batch.0": "все 48 · 16 ГБ, как в апстриме",
    "detector.fst.batch.note": (
        "FST всегда обрабатывает 48 десятисекундных сегментов, дополняя ими "
        "короткие файлы, — так что это и есть весь его аппетит к памяти. До "
        "Stage-2 сегменты независимы, а замеренное время одинаково при любом "
        "выборе."
    ),
    # ---- upstream repositories -------------------------------------------
    "table.repo.name": "Репозиторий",
    "table.repo.head": "HEAD",
    "table.repo.branch": "Ветка",
    "table.repo.state": "Состояние",
    "table.repo.pinned": "Проверенный коммит",
    "repo.state.missing": "не клонирован",
    "repo.state.not_git": "не git-репозиторий",
    "repo.state.dirty": "есть локальные правки",
    "repo.state.behind": "отстаёт на {count} коммитов",
    "repo.state.current": "актуален",
    "repo.state.clean": "чисто",
    "repo.state.detached": "detached",
    "repo.pin.match": "совпадает",
    "repo.pin.drift": "ушёл вперёд от `{commit}`",
    "repo.license.upstream": "лицензия апстрима",
    "repo.license.mit_nc_weights": "код MIT · веса CC BY-NC",
    "repo.pull.pinned": (
        "Этот репозиторий намеренно удерживается на проверенном коммите и "
        "отсюда не обновляется."
    ),
    "repo.pull.missing": "Клона нет на месте.",
    "repo.pull.not_a_repository": "Эта папка не является git-репозиторием.",
    "repo.pull.detached": (
        "HEAD в detached-состоянии. Если это действительно то, что нужно, "
        "переключитесь на ветку вручную."
    ),
    "repo.pull.dirty": (
        "В рабочей копии есть локальные правки, поэтому ничего не подтягивалось. "
        "Git сообщает:"
    ),
    "repo.pull.pull_failed": "git отказался перематывать вперёд:",
    "repo.pull.unchanged": "Уже актуален на `{commit}`.",
    "repo.pull.done": "Обновлено `{previous}` → `{current}` — {subject}",
    "repo.pull.dependencies": (
        "Изменился `pyproject.toml`. Перезапустите `pip install -e "
        "..\\muscriptor` в среде `ai-music-muscriptor` и обновите "
        "`environments/ai-music-muscriptor.txt`."
    ),
    "repo.pull.comparability": (
        "Изменение апстрима означает, что MIDI до и после не гарантированно "
        "совпадёт. Каждая транскрипция записывает версию, которой сделана."
    ),
    "repo.pull.pin_line": (
        "Если эта версия работает, зафиксируйте её: `{commit}` в `README.md` и "
        "`music_lab_ui/repositories.py`."
    ),
    # ---- MIDI transcription ----------------------------------------------
    "midi.source.label": "Что переводить",
    "midi.source.stem": "Стем, присланный из «Слоёв»",
    "midi.source.run": "Аудио текущего запуска",
    "midi.source.upload": "Файл",
    "midi.source.none": "Пока ничего не выбрано.",
    "midi.source.selected": "Источник: `{name}`",
    "midi.upload.label": "Аудиофайл (WAV, FLAC, MP3)",
    "midi.model.label": "Чекпоинт для этого прогона",
    "midi.instruments.label": "Только эти инструменты",
    "midi.instruments.placeholder": "drums, acoustic_piano",
    "midi.instruments.info": (
        "Ничего не отмечено — транскрибировать всё, что muscriptor услышит."
    ),
    "midi.run": "▷  Перевести в MIDI",
    "midi.status.idle": "Выберите источник и запустите перевод.",
    "midi.status.done": "Сохранено в `{path}` · {seconds} с",
    "midi.file.label": "MIDI-файл",
    "midi.payload.label": "Чем сделан этот файл",
    "midi.plot.title": "Распознанные ноты",
    "midi.plot.pitch": "Высота MIDI",
    "midi.plot.label": "Пиано-ролл",
    "midi.preview.label": "Прослушать",
    "midi.empty.notes": "Здесь появится транскрипция",
    "midi.preview.summary": (
        "**{notes} нот** на {tracks} дорожк(ах) · {seconds} с · {tempo} BPM\n\n"
        "Дорожки: {names}"
    ),
    "midi.preview.note": (
        "> Превью синтезируется из нот простыми синусами и шумом — это проверка, "
        "что ноты попадают туда же, куда аудио, а не сведение. Клик по "
        "пиано-роллу перематывает плеер."
    ),
    # ---- layers -> MIDI ----------------------------------------------------
    "layers.pick.none": "За этой строкой нет файла.",
    "layers.pick.selected": "Выбрано: `{name}`",
    "layers.send_to_midi": "→  Отправить в MIDI",
    # ---- muscriptor failures ------------------------------------------------
    "muscriptor.error.gated_repo": (
        "Веса gated. Откройте страницу модели, примите CC BY-NC 4.0 — доступ "
        "выдаётся автоматически — и попробуйте снова."
    ),
    "muscriptor.error.token_missing": (
        "Hugging Face отклонил запрос как неаутентифицированный. Добавьте токен "
        "в настройках или задайте `HF_TOKEN` до запуска приложения."
    ),
    "muscriptor.error.token_scope": (
        "Токен работает, но не читает gated-репозитории. Токену fine-grained "
        "нужен пункт *Read access to contents of all public gated repos you can "
        "access*."
    ),
    "muscriptor.error.repo_missing": "На Hugging Face нет такого репозитория.",
    "muscriptor.error.offline": (
        "Hugging Face недоступен. Для загрузки нужно соединение; для "
        "транскрипции уже скачанными весами — нет."
    ),
    "muscriptor.error.cuda_oom": (
        "Не хватает VRAM под этот чекпоинт. Возьмите меньше или переключите "
        "устройство на CPU."
    ),
    "muscriptor.error.package_missing": (
        "muscriptor не установлен в среду `ai-music-muscriptor`."
    ),
    "muscriptor.error.file_missing": "Файла нет на месте.",
    "muscriptor.error.stalled": (
        "Процесс транскрипции замолчал. Он остановлен; недописанного не "
        "осталось."
    ),
    "muscriptor.error.timeout": "Прогон вышел за лимит времени и был остановлен.",
    "muscriptor.error.http_error": "Hugging Face вернул ошибку.",
    "muscriptor.error.failed": "Прогон не удался.",
    "error.no_midi_source": "Выберите, что переводить",
    "error.no_sunofix_source": "Выберите, что чинить",
    "error.measure_first": "Измерьте файл перед запуском прохода",
    "error.pick_stem": "Сначала выберите стем в таблице",
    "error.midi_not_ready": "Перевод в MIDI ещё не настроен — см. настройки",
    # ---- detector cards ------------------------------------------------
    "detector.kind": "AI music detector",
    "detector.probability": "Вероятность AI",
    "detector.status": "Статус",
    "detector.caveat": "Оговорка",
    "detector.caveat.title": "Оговорка",
    "detector.unknown_device": "неизвестно",
    "detector.seconds": "{value} с",
    "status.not_applicable": "Не применимо",
    "status.error": "Ошибка",
    "status.high": "Высокая",
    "status.medium": "Средняя",
    "status.low": "Низкая",
    "caveat.fst.floor": (
        "Нижняя граница шкалы FST; возможен false negative на новых генераторах."
    ),
    "caveat.fst.ceiling": "Верхняя граница шкалы FST; это не калиброванная гарантия.",
    "caveat.fst.general": (
        "Структурная модель; возможны пропуски при generator shift и на "
        "материале без устойчивого ритма."
    ),
    "caveat.lofcz": (
        "Сигнальная модель; проверяйте результат вторым детектором и известным "
        "происхождением файла."
    ),
    "caveat.generic": "Результат зависит от версии модели и входного файла.",
    # ---- metadata table ------------------------------------------------
    "meta.file": "Файл",
    "meta.format": "Формат",
    "meta.duration": "Длительность",
    "meta.sample_rate": "Sample rate",
    "meta.channels": "Каналы",
    "meta.size": "Размер",
    "meta.peak": "Peak",
    "meta.rms": "RMS",
    "meta.crest": "Crest factor",
    "meta.stereo_correlation": "Stereo correlation",
    "meta.mid_side": "Mid / Side",
    "unit.seconds": "с",
    "unit.hertz": "Гц",
    "unit.megabytes": "МБ",
    "unit.kilohertz": "кГц",
    "unit.stereo": "стерео",
    "meta.empty": "Файл не загружен",
    "disc.file.stereo.title": "Стереокартина",
    "unit.mono": "моно",
    "unit.percentage_points": "п.п.",
    # ---- help ----------------------------------------------------------
    "help.aria": "Пояснение: {title}",
    "help.aria.warn": "Важно: {title}",
    "help.measured": "Что измеряется",
    "help.reading": "Как читать",
    "help.limits": "Ограничения",
    "help.lofcz.fakeprint.title": "lofcz: нативный fakeprint",
    "help.lofcz.lower_hull.title": "lofcz: спектр и нижняя огибающая",
    "help.fst.stage1.title": "FST: классы Stage-1",
    "help.fst.self_similarity.title": "FST: самоподобие",
    "help.fst.fusion_gate.title": "FST: fusion gate",
    "help.lofcz.fakeprint.measured": "Нормализованный частотный residue, который передаётся в ONNX.",
    "help.lofcz.fakeprint.reading": "Сравнивайте форму, частоты пиков и изменения между A/B.",
    "help.lofcz.fakeprint.limits": "Значение отдельного bin не является AI probability и не содержит времени.",
    "help.lofcz.lower_hull.measured": "Локальный нижний спектральный фон, вычитаемый из среднего спектра.",
    "help.lofcz.lower_hull.reading": "Разрыв между spectrum и hull образует residue модели.",
    "help.lofcz.lower_hull.limits": "Hull — preprocessing, а не отдельное решение классификатора.",
    "help.fst.stage1.measured": "Два нативных class score короткого 10-секундного сегмента.",
    "help.fst.stage1.reading": "Смотрите стабильность и изменение обоих классов между версиями.",
    "help.fst.stage1.limits": "Upstream не публикует соответствие индексов 0/1 меткам Real/Fake.",
    "help.fst.self_similarity.measured": "Попарное сходство MERT embeddings beat-aligned сегментов.",
    "help.fst.self_similarity.reading": "Яркая клетка означает более близкие сегменты в feature space модели.",
    "help.fst.self_similarity.limits": "Сходство не является вероятностью и зависит от структуры материала.",
    "help.fst.fusion_gate.measured": "Вес смешивания content и structure внутри Stage-2.",
    "help.fst.fusion_gate.reading": "Ближе к 1 — больше content; ближе к 0 — больше structure.",
    "help.fst.fusion_gate.limits": "Gate — внутренний mixing weight, а не вероятность AI.",
    # ---- interpretation ------------------------------------------------
    "interpret.heading": "Как прочитать этот run",
    "interpret.experimental_label": "Экспериментальная интерпретация.",
    "interpret.experimental_body": "Исходные detector outputs находятся выше и не изменены.",
    "interpret.lofcz_available": "lofcz fakeprint доступен как нативный частотный вход{peak}.",
    "interpret.lofcz_peak": "; strongest bin около {frequency} Hz",
    "interpret.fst_spread": "FST Stage-1 class 1 меняется на {spread} между сохранёнными сегментами.",
    "interpret.fst_gate": "Средний FST fusion gate = {value}; это mixing weight content/structure.",
    "interpret.missing": "Расширенная телеметрия отсутствует; запустите анализ заново.",
    # ---- timeline summary ----------------------------------------------
    "timeline.empty": "Карта пуста: окна не построены.",
    "timeline.window": "{start}–{end} с ({probability}%)",
    "timeline.summary": (
        "**Окон:** {count} (окно {window} с, шаг {hop} с) · "
        "**выше 50%:** {above} · "
        "**разброс:** {minimum}–{maximum}%\n\n"
        "**Самые заметные участки:** {hottest}"
    ),
    # ---- layers ---------------------------------------------------------
    "layer.not_measured": "не измерено",
    "layer.high_priority": "переделывать в первую очередь",
    "layer.low_priority": "низкий приоритет",
    # ---- plots ----------------------------------------------------------
    "plot.spectrogram": "Спектрограмма",
    "plot.spectrogram_3d": "3D-спектрограмма",
    "plot.dynamics": "Динамика по времени",
    "plot.average_spectrum": "Средний спектр",
    "plot.difference": "Разница: текущий − baseline",
    "plot.axis.time": "Время, с",
    "plot.axis.frequency": "Частота, Гц",
    "plot.axis.level": "Уровень, dBFS",
    "plot.axis.rms": "RMS, dBFS",
    "plot.hover.time": "Время",
    "plot.hover.frequency": "Частота",
    "plot.hover.level": "Уровень",
    "plot.hover.zone": "Зона",
    "plot.hover.change": "Изменение",
    "plot.current": "Текущий",
    "plot.baseline": "Baseline",
    "zone.sub_bass": "Суб-бас: фундамент и инфраниз",
    "zone.bass": "Бас: вес и основной тон",
    "zone.low_mid": "Низкая середина: плотность и мутность",
    "zone.mid": "Середина: тело и разборчивость",
    "zone.presence": "Присутствие: атака и чёткость",
    "zone.highs": "Высокие: яркость и сибилянты",
    "zone.air": "Воздух: верхний спектр и шум",
    # ---- telemetry plots -------------------------------------------------
    "telemetry.lofcz.spectrum": "lofcz · spectrum и lower hull",
    "telemetry.lofcz.residue": "Нормализованный residue",
    "telemetry.fst.stage1": "FST · нативные Stage-1 classes",
    "telemetry.axis.segment_start": "Начало сегмента, с",
    "telemetry.axis.segment": "Сегмент, с",
    "telemetry.axis.segment_b": "Сегмент B, с",
    "telemetry.layers.empty": "Ни один слой не удалось измерить",
    "telemetry.layers.title": "Слои по силе отпечатка",
    "telemetry.timeline.name": "lofcz по окнам",
    "telemetry.timeline.window": "Окно: %{customdata[0]:.1f}–%{customdata[1]:.1f} с",
    "telemetry.timeline.residue": "Средний residue: %{customdata[2]:.2f} дБ",
    "telemetry.timeline.threshold": "порог 50%",
    "telemetry.timeline.gate": "FST fusion gate (правая ось)",
    "telemetry.timeline.gate_hover": "Сегмент с %{x:.1f} с",
    "telemetry.timeline.fst_class": "FST Stage-1 class {index} (правая ось)",
    "telemetry.timeline.fst_axis": "FST по сегментам, 0–1",
    "telemetry.timeline.title": "Карта: где виден отпечаток",
    "telemetry.timeline.axis": "lofcz по окну, %",
    "telemetry.version_a": "Версия A",
    "telemetry.version_b": "Версия B",
    "telemetry.similarity.mismatch": (
        "Сетки beat-aligned сегментов A и B не совпадают; Δ matrix не строится"
    ),
    # ---- service messages -------------------------------------------------
    "error.restart_remote": (
        "Сервер поднят на {host}, а не на этой машине — перезапустите его из "
        "терминала, где он запущен."
    ),
    "error.no_audio": "Добавьте аудиофайл",
    "error.no_detector": "Выберите хотя бы один детектор",
    "error.unsupported_format": "Поддерживаются WAV, FLAC и MP3",
    "error.audio_missing": "Аудиофайл не найден: {path}",
    "error.no_layers": "Добавьте файлы слоёв",
    "error.no_reference": "Нужен проанализированный трек или файлы референсов",
    "error.no_run": "Сначала проанализируйте файл или выберите запуск",
    "error.run_audio_missing": "Аудиофайл запуска не найден: {path}",
    "error.same_version": "Выберите две разные версии",
    "error.window_positive": "Окно и шаг должны быть больше нуля",
    "error.files_missing": "Не найдены файлы: {files}",
    "error.no_audio_data": "{name} не содержит аудиоданных",
    "progress.features": "Извлечение аудиопризнаков",
    "progress.saving": "Сохранение результата",
    "progress.done": "Готово",
    "progress.layer": "Слой {index} из {total}: {name}",
    "progress.layers_done": "Слои обработаны",
    "progress.metrics": "Метрики {index} из {total}: {name}",
    "progress.metrics_done": "Метрики посчитаны",
    "progress.detector": "Запуск {detector}",
    "progress.detectors_done": "Детекторы завершены",
    # ---- empty-plot placeholders -----------------------------------------
    "empty.start": "Добавьте файл и запустите анализ",
    "empty.surface": "3D-поверхность появится после анализа",
    "empty.rms": "Весь трек появится после загрузки файла",
    "empty.spectrum": "Средний спектр появится после анализа",
    "empty.timeline": "Постройте карту после анализа",
    "empty.layers": "Добавьте слои и запустите измерение",
    "empty.run_lofcz": "Запустите lofcz",
    "empty.run_fst": "Запустите FST",
    "empty.lofcz_telemetry": "Нет lofcz telemetry — проанализируйте run заново",
    "empty.fakeprint": "Native fakeprint недоступен",
    "empty.fst_telemetry": "Нет FST telemetry — проанализируйте run заново",
    "empty.similarity": "Self-similarity недоступна",
    "empty.gate": "Fusion gate недоступен",
    "empty.lofcz_ab": "Для lofcz A/B нужна telemetry обеих версий",
    "empty.fst_ab": "Для FST A/B нужна telemetry обеих версий",
    "empty.pick_two": "Выберите две версии",
    "empty.pick_ab_telemetry": "Выберите A и B с сохранённой telemetry",
    "empty.pick_lofcz": "Выберите A и B с lofcz telemetry",
    "empty.pick_fst": "Выберите A и B с FST telemetry",
    "empty.difference": "Карта B − A появится после сравнения",
    "empty.heatmap_duration": "Heatmap недоступна: длительности отличаются более чем на 5%",
    # ---- controls ---------------------------------------------------------
    "app.high_detail": "Повысить детализацию 3D",
    "app.plot.fulltrack": "Весь трек",
    "app.timeline.window": "Окно, с",
    "app.timeline.hop": "Шаг, с",
    "app.timeline.build": "Построить карту",
    "app.layers.files": "Слои (WAV, FLAC, MP3)",
    "app.layers.button": "Измерить слои",
    "app.artifacts.references": "Референсы (необязательно)",
    "app.artifacts.button": "Посчитать метрики",
    "app.fst_npz": "FST · полный telemetry NPZ",
    "app.version_a.info": "Исходная или предыдущая обработка",
    "app.version_b.info": "Новая обработка того же материала",
    "app.compare.button": "Сравнить версии",
    "app.compare.pin": "Закрепить как A",
    "app.compare.unpin": "Снять закрепление",
    "app.compare.detector_label": "Изменение detector scores",
    "app.compare.spectrum_label": "Наложение среднего спектра",
    "app.compare.difference_label": "Спектральная разница B − A",
    "app.compare.metric_label": "Изменение метрик",
    "app.compare.native_heading": "#### Изменение нативных измерений детекторов",
    "app.history.title": "История анализов",
    "app.history.subtitle": "Сохранённые runs используются для ручного сравнения версий.",
    "app.status.done": "Статус: готово · run `{run_id}` сохранён.",
    # ---- table headers ----------------------------------------------------
    "table.metadata.parameter": "Параметр",
    "table.metadata.value": "Значение",
    "table.metadata.unit": "Единица",
    "table.layer.name": "Слой",
    "table.layer.residue": "Средний residue, дБ",
    "table.layer.duration": "Длительность, с",
    "table.layer.priority": "Приоритет",
    "table.artifact.file": "Файл",
    "table.artifact.attack": "Атака, дБ",
    "table.artifact.rolloff": "Rolloff 95%, кГц",
    "table.artifact.cliff": "Обрыв ВЧ, дБ/окт",
    "table.artifact.noise_floor": "Шумовой пол, dBFS",
    "table.artifact.flatness": "Плоскость пола",
    "table.artifact.corr_low": "Корр. низ",
    "table.artifact.corr_high": "Корр. верх",
    "table.artifact.cutoff": "Край ВЧ, кГц",
    "table.artifact.tonal": "Сильнейший пик, дБ",
    "table.sunofix.before": "До",
    "table.sunofix.after": "После",
    "table.sunofix.delta": "Δ после−до",
    "table.peaks.frequency": "Частота, Hz",
    "table.peaks.fakeprint": "Fakeprint",
    "table.detector": "Детектор",
    "table.delta": "Δ B−A",
    "table.metric": "Метрика",
    "table.unit": "Единица",
    "table.history.date": "Дата UTC",
    "table.history.note": "Заметка",
    "table.history.run_id": "Run ID",
    # ---- comparison messages ----------------------------------------------
    "compare.initial": "Выберите две разные сохранённые версии.",
    "compare.reset": "Сравнение сброшено после нового анализа. Выберите две версии заново.",
    "compare.pinned": "Версия A закреплена: `{filename}`.",
    "compare.unpinned": "Закрепление A снято; выбраны два последних run.",
    "compare.result": "Версия B − Версия A: `{version_b}` − `{version_a}`.",
    "compare.duration_mismatch": (
        "Сравниваются `{version_a}` и `{version_b}`. Длительности отличаются "
        "более чем на 5%, поэтому временная heatmap скрыта; scalar и detector "
        "deltas доступны."
    ),
    "error.analyze_first": "Сначала запустите анализ трека",
    "error.pick_both": "Выберите Версию A и Версию B",
    "error.pick_a": "Выберите Версию A",
    # ---- tab documentation -------------------------------------------------
    "lead.detector_data": (
        "Собственные preprocessing и выходы моделей, без изменений. Каждый "
        "значок объясняет график под собой."
    ),
    "lead.timeline": (
        "Где по треку виден отпечаток. Клик по кривой перематывает плеер."
    ),
    "lead.layers": (
        "Измерение отдельных дорожек, из которых собран микс: видно, какая "
        "несёт отпечаток."
    ),
    "lead.artifacts": (
        "Считается из сигнала, без участия детекторов — поэтому добавьте "
        "референсы и читайте свой трек рядом с ними."
    ),
    "lead.comparison": "Две обработки одного исходника, разница как `B − A`.",
    "lead.midi": (
        "Перевод аудио в ноты через muscriptor. Работает локально, на вашей "
        "видеокарте."
    ),
    "lead.sunofix": (
        "Починка артефактов генерации, наведённая измерениями вкладки "
        "**Артефакты**, а не слухом. Сначала измерение — ремонт проставляется "
        "сам и называет число, которое его включило."
    ),
    # ---- SunoFix -----------------------------------------------------------
    "disc.sunofix.level.title": "Что происходит с уровнем",
    "disc.sunofix.level.body": (
        "Уровень источника сохраняется. Громкость только снижается, и только "
        "если true peak уходит выше -1 dBTP.\n\n"
        "Ни нормализации, ни лимитера здесь нет: A/B, где одна сторона громче, "
        "ничего не доказывает — громче читается как лучше, что бы с треком ни "
        "сделали. На выходе WAV-заготовка под мастеринг, а не мастер."
    ),
    "disc.sunofix.masking.title": "Ремонт, который нужно доказывать отдельно",
    "disc.sunofix.masking.body": (
        "**Восстановление воздуха** и **шумовой пол** синтезируют то, чего в "
        "файле не было. Оба убирают сигнал, который детектор читает легче "
        "всего: стену лоупаса и пол, слишком чистый для записи.\n\n"
        "Упавший score поэтому не доказывает, что стало лучше. Прогоняйте "
        "такой модуль отдельно и сверяйте score со слепым прослушиванием. "
        "Правка, которая только обманывает детектор, — это провал, а не фича."
    ),
    "sunofix.source.label": "1. Что чинить",
    "sunofix.source.run": "Проанализированный трек",
    "sunofix.source.upload": "Файл",
    "sunofix.source.none": "Пока ничего не выбрано.",
    "sunofix.upload.label": "Аудиофайл",
    "sunofix.measure": "▷  Измерить и предложить",
    "sunofix.repair.heading": "### 2. Ремонт — галочки ставят измерения",
    "sunofix.repair.pending": "Сначала измерьте — до этого спорить не с чем.",
    "sunofix.taste.heading": "### 3. Музыкальный проход — только вкус",
    "sunofix.preset.label": "Пресет",
    "sunofix.preset.repair_only": "Только ремонт",
    "sunofix.preset.soft_glue": "Мягкая склейка",
    "sunofix.preset.open_top": "Открыть верх",
    "sunofix.preset.de_harsh": "Убрать резкость",
    "sunofix.preset.add_body": "Добавить тело",
    "sunofix.preset.desc.repair_only": (
        "Только ремонт и мягкий клинап. Никакого цвета."
    ),
    "sunofix.preset.desc.soft_glue": (
        "Мягкий проход для трека, который уже звучит близко."
    ),
    "sunofix.preset.desc.open_top": (
        "Открывает верх. Единственный проход с нулевым tone: затемнять здесь "
        "значит отменять собственную работу."
    ),
    "sunofix.preset.desc.de_harsh": (
        "Убирает резкость, сохраняя музыкальность."
    ),
    "sunofix.preset.desc.add_body": "Больше тела, теплоты и плотности.",
    "sunofix.finetune": "Тонкая настройка",
    "sunofix.warmth.heading": (
        "**Warmth** — гармоническая плотность. На громком мастере деликатно."
    ),
    "sunofix.warmth.enabled": "Warmth включён",
    "sunofix.warmth.character": "Характер",
    "sunofix.warmth.character.tape": "Лента",
    "sunofix.warmth.character.tube": "Лампа",
    "sunofix.warmth.character.console": "Консоль",
    "sunofix.warmth.character.warm": "Тепло",
    "sunofix.warmth.drive": "Drive",
    "sunofix.warmth.mix": "Mix",
    "sunofix.warmth.tone": "Tone",
    "sunofix.warmth.tone.info": (
        "Наклон вокруг 1 кГц. Выключается вместе с warmth."
    ),
    "sunofix.cleanup.heading": "**Чистка ВЧ** — только тихий мусор в верхах.",
    "sunofix.cleanup.enabled": "Чистка включена",
    "sunofix.cleanup.strength": "Сила",
    "sunofix.cleanup.strength.soft": "Мягко",
    "sunofix.cleanup.strength.medium": "Средне",
    "sunofix.cleanup.strength.strong": "Сильно",
    "sunofix.cleanup.strength.tails_only": "Только хвосты",
    "sunofix.cleanup.strength.air_clean": "Только воздух",
    "sunofix.run": "▷  Запустить проход",
    "sunofix.status.idle": "Статус: измерьте файл, затем запустите проход.",
    "sunofix.status.measured": (
        "Измерен `{name}`. Рекомендовано ремонтов: {count}. Каждая галочка ниже "
        "называет число, которое её включило."
    ),
    "sunofix.status.nothing": (
        "Ничего не было включено, поэтому ничего не изменилось. Отметьте ремонт "
        "или включите музыкальный проход."
    ),
    "sunofix.status.done": "Записан `{name}`. Отработало: {modules}. {level}",
    "sunofix.status.level_kept": "Уровень источника сохранён.",
    "sunofix.status.level_pulled": (
        "True peak вышел за потолок, поэтому выход снижен на {gain} дБ."
    ),
    "sunofix.delta.label": "Что проход измеримо сделал (после − до)",
    "sunofix.preview.label": "Результат",
    "sunofix.file.label": "Починенный WAV",
    "sunofix.badge.masking": "проверить отдельно",
    "sunofix.module.de_artifact": "Де-артефакт",
    "sunofix.module.fix_transients": "Транзиенты",
    "sunofix.module.restore_air": "Восстановление воздуха",
    "sunofix.module.restore_floor": "Шумовой пол",
    "sunofix.module.fix_stereo": "Стереокартина",
    "sunofix.module.hf_cleanup": "Чистка ВЧ",
    "sunofix.module.warmth": "Warmth",
    "sunofix.module.tone_tilt": "Tone",
    "sunofix.module.level_policy": "Уровень",
    "sunofix.why.de_artifact": (
        "{prominence} дБ тональной выпуклости на {frequencies} кГц — устойчивые "
        "пики того типа, что оставляет генератор."
    ),
    "sunofix.why.de_artifact.none": (
        "В верхней середине ничего не выпирает; вырезать нечего."
    ),
    "sunofix.why.fix_transients": (
        "Атаки нарастают всего на {attack} дБ — это читается как размазывание."
    ),
    "sunofix.why.fix_transients.none": (
        "Атаки нарастают на {attack} дБ — в диапазоне живого материала."
    ),
    "sunofix.why.restore_air": (
        "Верх обрывается на {cutoff} кГц и падает на {slope} дБ на октаву: это "
        "стена, а не спад."
    ),
    "sunofix.why.restore_air.none": (
        "Верх спадает сам по себе; стены, над которой нужно строить, нет."
    ),
    "sunofix.why.restore_floor": (
        "Пол на {floor} dBFS при плоскости {flatness} — чище и ровнее, чем "
        "бывает у записи."
    ),
    "sunofix.why.restore_floor.none": (
        "Пол уже выглядит как у чего-то записанного."
    ),
    "sunofix.why.fix_stereo": (
        "Корреляция верха {correlation}: вне диапазона, где картина читается "
        "как картина."
    ),
    "sunofix.why.fix_stereo.none": (
        "Корреляция верха {correlation} — обычная стереокартина, не трогаем."
    ),
    # ---- moved method notes --------------------------------------------------
    "disc.spectrum.reading.title": "Как читать спектрограмму",
    "disc.spectrum.reading.measured": (
        "Уровень по частотным полосам во времени, напрямую из аудио."
    ),
    "disc.spectrum.reading.reading": (
        "Используйте её как измерение аудио, а не как самостоятельный "
        "AI-классификатор. Сначала сопоставьте два detector score."
    ),
    "disc.spectrum.reading.limits": (
        "Спектрограмма показывает, что с сигналом сделал кодек или генератор; "
        "сама по себе она ничего не говорит о происхождении музыки."
    ),
    "disc.timeline.method.title": "Что такое значение окна и чем оно не является",
    "disc.timeline.method.body": (
        "Общий score не говорит, что чинить. Здесь fakeprint считается "
        "скользящим окном, поэтому видно, какие участки тянут оценку вверх."
        "\n\n"
        "Модель обучалась на усреднении по всему треку, поэтому оконные "
        "значения — **относительная карта внутри одного трека**, а не "
        "калиброванная вероятность на секунду. Сравнивайте окна с другими "
        "окнами того же трека; сравнение с глобальным score другого трека "
        "бессмысленно. Чем короче окно, тем шумнее оценка."
    ),
    "disc.layers.what_to_load.title": "Что грузить и что вернётся",
    "disc.layers.what_to_load.body": (
        "Загрузите отдельные дорожки **до сведения** — те, из которых собран "
        "трек в студии. Каждая измеряется отдельно, и видно, какая несёт "
        "отпечаток: например барабаны 97%, а живая гитара 15%.\n\n"
        "Это диагностический прогон. Он **не сохраняется** в историю и не "
        "создаёт версии: чтобы зафиксировать слой как версию, проанализируйте "
        "его обычным путём слева.\n\n"
        "Используется только lofcz. FST требует различимых долей, которых у "
        "большинства стемов нет, а на полном миксе он и так доступен в основном "
        "анализе."
    ),
    "disc.layers.separation.title": "Не разделяйте для этого готовый микс",
    "disc.layers.separation.body": (
        "Инструмент разделения добавляет собственные артефакты и сам поднимает "
        "score, так что измерять вы будете разделитель, а не материал. Берите "
        "те дорожки, которые действительно записаны или сгенерированы."
    ),
    "disc.artifacts.metrics.title": "Что измеряет каждая колонка",
    "disc.artifacts.metrics.body": """
      <ul>
        <li><strong>Атака</strong> — типичный самый резкий подъём громкости за
        20 мс. Размазанные транзиенты его снижают.</li>
        <li><strong>Rolloff 95%</strong> — где заканчивается основная энергия
        спектра.</li>
        <li><strong>Обрыв ВЧ</strong> — самый крутой спад выше 4 кГц. Сильно
        отрицательное значение означает жёсткую стену кодека или генератора;
        живой материал спадает плавно.</li>
        <li><strong>Шумовой пол и его плоскость</strong> — очень низкий и очень
        плоский пол означает стерильный цифровой материал без комнаты и шума
        тракта.</li>
        <li><strong>Корреляция низа и верха</strong> — схлопнутая или
        неестественно широкая стереокартина.</li>
      </ul>
    """,
    "disc.artifacts.compare.title": "Сравнивайте подобное с подобным",
    "disc.artifacts.compare.body": (
        "**MP3 сам по себе даёт обрыв ВЧ** независимо от происхождения музыки, "
        "поэтому MP3 против WAV покажет кодек, а не генератор. По той же "
        "причине не сравнивайте отдельный стем с полным миксом.\n\n"
        "Сами по себе эти числа не значат почти ничего. Добавьте референсы — "
        "свои живые записи или коммерческие треки — и читайте свой трек рядом с "
        "ними. Метод измерения для всех файлов одинаковый."
    ),
    "disc.comparison.method.title": "Что делает сравнение полезным",
    "disc.comparison.method.body": (
        "Выбирайте, например, исходный stem как **Версию A** и тот же stem "
        "после обработки как **Версию B**. Разница строится как `B − A`.\n\n"
        "Сравнение разных песен отражает главным образом различия музыкального "
        "материала и обычно не даёт полезного вывода."
    ),
    "disc.midi.stems.title": "Подавайте стемы, а не миксы",
    "disc.midi.stems.body": (
        "Полифоническая транскрипция плотного микса не решена, и разница между "
        "басовым стемом и полным треком, из которого он взят, — это разница "
        "между результатом, который стоит править, и тем, который стоит "
        "удалить.\n\n"
        "Ровно для этого кнопка на вкладке **Слои**: измерьте стемы, кликните "
        "нужную строку, отправьте её сразу сюда."
    ),
    "disc.midi.reproducibility.title": "Что записывается с каждым файлом",
    "disc.midi.reproducibility.body": (
        "Декодирование жадное — без сэмплирования и температуры, — поэтому одно "
        "и то же аудио с теми же настройками даёт тот же MIDI.\n\n"
        "Каждый прогон пишет рядом с `.mid` файл JSON с чекпоинтом, параметрами "
        "декодирования и версией muscriptor, чтобы старая транскрипция осталась "
        "интерпретируемой после обновления. Файлы кладутся в `output/midi/`, а "
        "не в кэш, который чистится раз в сутки."
    ),
    "disc.midi.setup.title": "Настройка",
    # ---- the app's one long-form licence statement ---------------------------
    "disc.licence.weights.title": "Лицензия на веса транскрипции",
    "disc.licence.weights.body": (
        "**Код** muscriptor под MIT, и эта обёртка тоже. **Веса модели — "
        "CC BY-NC 4.0, только некоммерческое использование**, и карточка модели "
        "добавляет условие сверху: выход нельзя использовать для незаконной "
        "деятельности, явно включая транскрипцию музыки, прав на которую у вас "
        "нет.\n\n"
        "Если вы выкладываете то, что построено на этих транскрипциях, эту "
        "границу оценивать вам. У каждого инструмента в этой мастерской свои "
        "условия; они перечислены в README."
    ),
    # ---- MIDI guides ---------------------------------------------------------
    # Авторская разметка, не пользовательский ввод: эти тела содержат списки и
    # ссылки и вставляются без экранирования в disclosure_html.
    "guide.midi.basics.title": "Как открыть MIDI в FL Studio",
    "guide.midi.basics.body": """
      <p>Два пути. Перетащить <code>.mid</code> из браузера на плейлист — самый
      быстрый; <em>File &rarr; Import &rarr; MIDI file</em> даёт опции импорта,
      включая отдельный канал на дорожку, а это то, что нужно, когда muscriptor
      нашёл несколько инструментов.</p>
      <ol>
        <li><strong>Сначала выставьте темп проекта.</strong> В транскрипции
        записан определённый темп; если проект с ним не согласен, всё ляжет мимо
        сетки и будет выглядеть ошибкой транскрипции, ей не являясь.</li>
        <li><strong>Не квантуйте сразу.</strong> Послушайте сырые ноты против
        аудио. Квантайз плохой транскрипции прячет ошибки вместо того, чтобы их
        показать.</li>
        <li><strong>Первым делом почистите пиано-ролл.</strong> Обычный мусор —
        короткие призрачные ноты и октавные дубли. Минута удаления экономит час
        размышлений, почему партия звучит не так.</li>
        <li><strong>Сохраните оригинал.</strong> Каждая транскрипция ложится в
        <code>output/midi/</code>, рядом JSON с чекпоинтом и параметрами, так что
        отредактированная версия никогда не станет единственной копией.</li>
      </ol>
      <p>Справочно:
      <a href="https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/fformats_other_mid.htm"
      target="_blank" rel="noopener">MIDI-файлы в мануале FL Studio</a> ·
      <a href="https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/pianoroll.htm"
      target="_blank" rel="noopener">пиано-ролл</a> ·
      <a href="https://www.image-line.com/fl-studio-learning/" target="_blank"
      rel="noopener">видеоуроки самой Image-Line</a>.</p>
    """,
    "guide.midi.drums.title": "Барабаны: MIDI в FPC и откуда брать брейки",
    "guide.midi.drums.body": """
      <p>Барабанный MIDI окупается сразу: замена сгенерированной установки на
      живые сэмплы — ровно та подмена, которая снижает detector score по
      правильной причине.</p>
      <p><strong>FPC</strong> — пэд-сэмплер FL Studio и естественный адресат.
      Загрузите пустой FPC, набросайте на пэды свои сэмплы, откройте
      транскрибированный MIDI в его пиано-ролле и сведите клавиши пэдов с
      пришедшими нотами. Клавиша запуска каждого пэда задаётся в Play
      Key/Octave, так что маппинг правится на пэде, а не переносом всех нот.</p>
      <p>Чего ждать от транскрипции: хэты выходят плотными и часто
      переопределяются, кик и снейр обычно уверенные, призрачные снейры —
      первое, что стоит проредить. Транскрибируйте барабанный стем отдельно, а не
      полный микс: именно бас, залезающий в полосу кика, порождает фантомные
      удары.</p>
      <p>Источники самих сэмплов:
      <a href="https://www.musicradar.com/tag/sampleradar" target="_blank"
      rel="noopener">MusicRadar SampleRadar</a> — бесплатные паки, в том числе
      много брейкбит-материала (условия смотрите у каждого пака) ·
      <a href="https://splice.com/sounds/genres/drum-and-bass/packs"
      target="_blank" rel="noopener">паки drum &amp; bass на Splice</a> по
      подписке — там живёт большинство актуальных ваншотов и брейков.</p>
      <p>Справочно:
      <a href="https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/plugins/FPC.htm"
      target="_blank" rel="noopener">FPC в мануале FL Studio</a>.</p>
    """,
    "guide.midi.acoustic.title": "Гитара, струнные, оркестр",
    "guide.midi.acoustic.body": """
      <p>Мелодическим партиям нужен сэмплер с живыми записями внутри: пресет
      синтезатора скрипичную линию не продаст. Два бесплатных пути, покрывающих
      почти всё:</p>
      <ul>
        <li><a href="https://splice.com/instrument" target="_blank"
        rel="noopener">Splice INSTRUMENT</a> — бывшая библиотека Spitfire LABS,
        теперь под Splice. VST3/AU, бесплатные пресеты со струнными, роялями и
        прочим, платные паки сверху.</li>
        <li><a href="https://www.plogue.com/products/sforzando.html"
        target="_blank" rel="noopener">Plogue sforzando</a> — бесплатный
        SFZ-плеер. Простой и некрасивый, но открывает огромный пласт бесплатных
        SFZ-библиотек для оркестровых и народных инструментов, баян включая.</li>
      </ul>
      <p>Что транскрипция даст и чего не даст: высоту и тайминг — да.
      Артикуляцию — нет: легато, стаккато, штрихи и глиссандо в MIDI не
      попадают и вписываются руками, обычно через keyswitch или линию
      экспрессии. Транскрибированная струнная партия звучит механически, пока это
      не сделано; это работа, а не баг.</p>
      <p>Гитара отдельно: она транскрибируется как ноты без информации о ладах и
      струнах, поэтому аккордовые построения выходят в той октаве, которую выбрала
      модель. Обычно быстрее отнестись к результату как к аккордовой сетке и
      переголосовать её, чем воевать с полученными нотами.</p>
    """,
    "guide.midi.bass.title": "Бас и синты",
    "guide.midi.bass.body": """
      <p>Бас — самое ненадёжное место транскрипции, и стоит знать почему, прежде
      чем винить модель: основной тон суб-баса ниже примерно 40 Гц часто уезжает
      на октаву, а у сильно перегруженных и reese-басов столько гармоник, что
      модель слышит гармонику как ноту.</p>
      <p>Практический порядок: транскрибировать басовый стем отдельно, первым
      делом сверить октаву с аудио и быть готовым править октаву целыми фразами,
      а не отдельными нотами.</p>
      <p>Для воспроизведения годится любой субтрактивный или wavetable-синт. У
      <a href="https://vital.audio/" target="_blank" rel="noopener">Vital</a>
      есть бесплатный тариф с полным синтом и урезанной библиотекой пресетов, а
      родные Sytrus и 3xOsc уже стоят и на чистый саб способны вполне.</p>
      <p>Важнее выбора синта другое: транскрибированная басовая линия сохраняет
      длительности оригинала, а для щипкового или гейтованного баса они обычно
      слишком длинные. Укоротить ноты под грув даёт для ощущения больше, чем
      любой пресет.</p>
    """,
}

CATALOGUE: Final[dict[str, dict[str, str]]] = {"en": _EN, "ru": _RU}


class Translator:
    """Looks up one locale, falling back to the default for untranslated keys.

    A missing key raises rather than rendering a placeholder: an untranslated
    label is a bug that should surface in the test suite, not something a user
    discovers in the interface.
    """

    __slots__ = ("locale", "_strings", "_fallback")

    def __init__(self, locale: str = DEFAULT_LOCALE) -> None:
        self.locale = locale if locale in CATALOGUE else DEFAULT_LOCALE
        self._strings = CATALOGUE[self.locale]
        self._fallback = CATALOGUE[DEFAULT_LOCALE]

    def __call__(self, key: str, **params: object) -> str:
        template = self._strings.get(key, self._fallback.get(key))
        if template is None:
            raise KeyError(f"Untranslated key: {key!r}")
        return template.format(**params) if params else template

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Translator({self.locale!r})"


def get_translator(locale: str = DEFAULT_LOCALE) -> Translator:
    return Translator(locale)
