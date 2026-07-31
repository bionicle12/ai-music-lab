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
    "app.step.upload": "### 1. Load an audio file",
    "app.step.metadata": "### 2. File information",
    "app.step.detectors": "### 3. Detectors",
    "app.audio.label": "Audio file",
    "app.note.label": "Version note",
    "app.note.placeholder": "For example: vocal after de-esser v2",
    "app.detectors.label": "Detectors",
    "app.detectors.lofcz": "lofcz · signal model",
    "app.detectors.fst": "FST · structural model",
    "app.analyze": "▷  Run analysis",
    "app.status.ready": "Status: ready to analyse.",
    "app.method_note": (
        "> Results are measurements of specific model versions, not proof of "
        "where the audio came from."
    ),
    "app.empty.detectors": "Individual lofcz and FST results will appear here after an analysis.",
    # ---- tabs ----------------------------------------------------------
    "tab.spectrum": "Spectrum",
    "tab.timeline": "Timeline map",
    "tab.layers": "Layers",
    "tab.artifacts": "Artifacts",
    "tab.overview": "Overview",
    "tab.detector_data": "Detector data",
    "tab.comparison": "Compare versions",
    "tab.technical": "Technical data",
    # ---- detector cards ------------------------------------------------
    "detector.kind": "AI music detector",
    "detector.probability": "AI probability",
    "detector.status": "Status",
    "detector.caveat": "Caveat",
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
    "unit.mono": "mono",
    "unit.percentage_points": "pp",
    # ---- help ----------------------------------------------------------
    "help.aria": "Explanation: {title}",
    "help.measured": "What is measured",
    "help.reading": "How to read it",
    "help.limits": "Limitations",
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
    "telemetry.timeline.title": "Map: where the fingerprint shows",
    "telemetry.timeline.axis": "lofcz per window, %",
    "telemetry.version_a": "Version A",
    "telemetry.version_b": "Version B",
    "telemetry.similarity.mismatch": (
        "The beat-aligned segment grids of A and B do not match; no Δ matrix is built"
    ),
    # ---- service messages -------------------------------------------------
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
    "empty.rms": "RMS appears after an analysis",
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
    "app.plot.rms_envelope": "RMS envelope",
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
    "app.overview.heading": "How to read the result",
    "app.overview.body": (
        "First compare the two detector scores. Then use the spectrogram as a "
        "measurement of the audio, not as an AI classifier in its own right."
    ),
    "app.run_overview": (
        "Run <code>{run_id}</code> is stored locally. Compare scores between "
        "models and keep their different training domains in mind."
    ),
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
    "doc.timeline": """
### Where exactly the fingerprint shows

A global score does not say what to fix. Here the fakeprint is computed with a
sliding window, so you can see which sections pull the score up.

The model was trained on an average over a whole track, so window values are a
**relative map inside one track**, not a calibrated probability per second. The
shorter the window, the noisier the estimate.

Clicking the curve seeks the player to that moment.
""",
    "doc.layers": """
### What to redo first

Load the individual tracks **before mixdown** — the ones the studio track was
built from. Each is measured separately, so you can see which one carries the
fingerprint: drums 97% and live guitar 15%, for example.

This is a diagnostic pass. It is **not saved** to the history and creates no
version: to record a layer as a version, analyse it the normal way on the left.

Only lofcz is used. FST needs detectable beats, which most stems do not have,
and on a full mix it is available in the main analysis anyway.

Do not split a finished mix with a separation tool for this: separation adds its
own artifacts and raises the score by itself.
""",
    "doc.artifacts": """
### What is audible, not what the model thinks

These metrics are computed straight from the signal and never consult a
detector. They stay meaningful when the models disagree or go out of domain, and
they point at edits you can actually hear.

On their own the numbers mean almost nothing — add references (your own live
recordings or commercial tracks) and read your track next to them. The
measurement method is identical for every file.

- **Attack** — the typical sharpest rise in loudness over 20 ms. Smeared
  transients lower it.
- **Rolloff 95%** — where the bulk of the spectral energy ends.
- **HF cliff** — the steepest decay above 4 kHz. A strongly negative value means
  a hard wall from a codec or generator; live material rolls off gently.
- **Noise floor and its flatness** — a very low and very flat floor means
  sterile digital material with no room and no signal-path noise.
- **Low and high correlation** — a collapsed or unnaturally wide stereo image.

⚠️ Compare like with like. **MP3 produces an HF cliff on its own**, regardless
of where the music came from, so MP3 against WAV shows the codec rather than the
generator. For the same reason, do not compare a single stem against a full mix.
""",
    "doc.detector_data": """
### The models' native measurements

These are the original preprocessing and model signals. Interpretation is placed
below them and does not alter the raw outputs.
""",
    "doc.comparison": """
### Comparing two processings of one source

Choose, for example, the original stem as **Version A** and the same stem after
processing as **Version B**. The difference is built as `B − A`. Comparing
different songs mostly reflects differences in the musical material and rarely
produces a useful conclusion.
""",
}

_RU: dict[str, str] = {
    # ---- shell ---------------------------------------------------------
    "app.title": "AI Music Lab",
    "app.eyebrow": "LOCAL FORENSIC AUDIO WORKSPACE",
    "app.tagline": "Локальный анализ одного трека или стема",
    "app.language": "Язык",
    "app.step.upload": "### 1. Загрузите аудиофайл",
    "app.step.metadata": "### 2. Информация о файле",
    "app.step.detectors": "### 3. Детекторы",
    "app.audio.label": "Аудиофайл",
    "app.note.label": "Заметка к версии",
    "app.note.placeholder": "Например: vocal после de-esser v2",
    "app.detectors.label": "Детекторы",
    "app.detectors.lofcz": "lofcz · сигнальная модель",
    "app.detectors.fst": "FST · структурная модель",
    "app.analyze": "▷  Запустить анализ",
    "app.status.ready": "Статус: готов к анализу.",
    "app.method_note": (
        "> Результаты — измерения конкретных версий моделей, а не "
        "доказательство происхождения аудио."
    ),
    "app.empty.detectors": "После анализа здесь появятся отдельные результаты lofcz и FST.",
    # ---- tabs ----------------------------------------------------------
    "tab.spectrum": "Спектр",
    "tab.timeline": "Карта по времени",
    "tab.layers": "Слои",
    "tab.artifacts": "Артефакты",
    "tab.overview": "Обзор",
    "tab.detector_data": "Данные детекторов",
    "tab.comparison": "Сравнение версий",
    "tab.technical": "Технические данные",
    # ---- detector cards ------------------------------------------------
    "detector.kind": "AI music detector",
    "detector.probability": "Вероятность AI",
    "detector.status": "Статус",
    "detector.caveat": "Оговорка",
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
    "unit.mono": "моно",
    "unit.percentage_points": "п.п.",
    # ---- help ----------------------------------------------------------
    "help.aria": "Пояснение: {title}",
    "help.measured": "Что измеряется",
    "help.reading": "Как читать",
    "help.limits": "Ограничения",
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
    "telemetry.timeline.title": "Карта: где виден отпечаток",
    "telemetry.timeline.axis": "lofcz по окну, %",
    "telemetry.version_a": "Версия A",
    "telemetry.version_b": "Версия B",
    "telemetry.similarity.mismatch": (
        "Сетки beat-aligned сегментов A и B не совпадают; Δ matrix не строится"
    ),
    # ---- service messages -------------------------------------------------
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
    "empty.rms": "RMS появится после анализа",
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
    "app.plot.rms_envelope": "RMS огибающая",
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
    "app.overview.heading": "Как читать результат",
    "app.overview.body": (
        "Сначала сопоставьте два detector score. Затем используйте "
        "спектрограмму как измерение аудио, а не как самостоятельный "
        "AI-классификатор."
    ),
    "app.run_overview": (
        "Run <code>{run_id}</code> сохранён локально. Сравнивайте scores между "
        "моделями и учитывайте их разные обучающие домены."
    ),
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
    "doc.timeline": """
### Где именно виден отпечаток

Общий score не говорит, что чинить. Здесь fakeprint считается скользящим окном,
поэтому видно, какие участки трека тянут оценку вверх.

Модель обучалась на усреднении по всему треку, поэтому оконные значения —
**относительная карта внутри одного трека**, а не калиброванная вероятность на
секунду. Чем короче окно, тем шумнее оценка.

Клик по кривой перематывает плеер на этот момент.
""",
    "doc.layers": """
### Что перебивать в первую очередь

Загрузите отдельные дорожки **до сведения** — те, из которых собран трек в
студии. Каждая измеряется отдельно, и видно, какая несёт отпечаток: например
барабаны 97%, а живая гитара 15%.

Это диагностический прогон, он **не сохраняется** в историю и не создаёт версии:
чтобы зафиксировать слой как версию, проанализируйте его обычным путём слева.

Используется только lofcz. FST требует различимых долей, которых у большинства
стемов нет, а на полном миксе он и так доступен в основном анализе.

Разделять готовый микс сторонними инструментами для этого не стоит: разделение
добавляет собственные артефакты и само поднимает score.
""",
    "doc.artifacts": """
### Что слышно, а не что думает модель

Эти метрики считаются напрямую из сигнала и не обращаются к детекторам. Они
остаются осмысленными, когда модели расходятся или выходят за свой домен, и
указывают на правки, которые реально слышны.

Сами по себе числа не значат почти ничего — добавьте референсы (свои живые
записи или коммерческие треки), и читайте свой трек рядом с ними. Метод
измерения для всех файлов одинаковый.

- **Атака** — типичный самый резкий подъём громкости за 20 мс. Размазанные
  транзиенты его снижают.
- **Rolloff 95%** — где заканчивается основная энергия спектра.
- **Обрыв ВЧ** — самый крутой спад выше 4 кГц. Сильно отрицательное значение
  означает жёсткую стену кодека или генератора; живой материал спадает плавно.
- **Шумовой пол и его плоскость** — очень низкий и очень плоский пол означает
  стерильный цифровой материал без комнаты и шума тракта.
- **Корреляция низа и верха** — collapsed или неестественно широкая
  стереокартина.

⚠️ Сравнивайте подобное с подобным. **MP3 сам по себе даёт обрыв ВЧ**
независимо от происхождения музыки, поэтому MP3 против WAV покажет разницу
кодека, а не генератора. Так же не сравнивайте отдельный стем с полным миксом.
""",
    "doc.detector_data": """
### Нативные измерения моделей

Здесь показаны исходные preprocessing/model signals. Интерпретация вынесена вниз
и не изменяет raw outputs.
""",
    "doc.comparison": """
### Сравнение двух обработок одного исходника

Выбирайте, например, исходный stem как **Версию A** и тот же stem после
обработки как **Версию B**. Разница строится как `B − A`. Сравнение разных песен
отражает главным образом различия музыкального материала и обычно не даёт
полезного вывода.
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
