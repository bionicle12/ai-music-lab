# Установка через ИИ-агента

[← Документация](README.md) · [English](../agent-setup.md)

Установка механическая, но муторная: три репозитория рядом друг с другом, три Conda-среды,
три файла весов в строго определённых местах. Если вы пользуетесь кодовым агентом (Claude
Code, Codex, Cursor, …), промпты ниже отдают ему всю работу целиком.

Всё это можно сделать и руками — см. [Начало работы](getting-started.md). Промпты — удобство,
а не обязательное условие.

## Чего агент за вас не сделает

**Два чекпоинта FST лежат на Google Drive и требуют человека.** Google Drive закрывает
скриптовую загрузку больших файлов страницей подтверждения, поэтому агент не сможет надёжно
скачать `Stage-1.ckpt` (1,2 ГБ) и `Stage-2.ckpt`. Эти два файла скачайте сами — проверить
их хэши агент потом сможет. Модель lofcz лежит на Hugging Face с прямой ссылкой и скачивается
автоматически.

Ещё стоит понимать до того, как отдавать управление: агент будет создавать Conda-среды и
клонировать два внешних репозитория. Прочитайте промпт перед запуском и сохраните в нём
правило «никогда не менять upstream-репозитории» — именно оно обеспечивает воспроизводимость
ваших измерений.

## Промпт 1 — установка с нуля

Вставьте агенту, работающему внутри папки `ai-music-lab`.

```text
Разверни этот проект (ai-music-lab), чтобы запускался интерфейс. Работай под
Windows с PowerShell и Conda. Выполняй шаги строго по порядку и останавливайся с
отчётом, если какой-то шаг не прошёл.

ЖЁСТКИЕ ПРАВИЛА
- Никогда не изменяй, не коммить и не переформатируй ничего внутри двух
  upstream-репозиториев детекторов. Это read-only зависимости. Проект — обёртка,
  и он рассчитывает, что они остаются нетронутыми.
- Не обновляй зафиксированные версии зависимостей. Файлы environments/*.txt —
  замороженные снимки, соответствующие зафиксированным коммитам upstream.
- Не выдумывай ссылки для скачивания. Используй только те, что в
  models/sources.json.

ШАГ 1 — склонируй два детектора РЯДОМ с этим репозиторием, а не внутрь него.
Целевая раскладка:
    <родительская папка>/
    ├── ai-music-lab/            (этот репозиторий)
    ├── ai-music-detector/       (upstream lofcz)
    └── FST-AI-Music-Detection/  (upstream FST)
Команды из родительской папки:
    git clone https://github.com/lofcz/ai-music-detector.git
    git clone https://github.com/Mippia/FST-AI-Music-Detection.git

ШАГ 2 — зафиксируй оба upstream на коммитах, с которыми обёртка проверена:
    git -C ..\ai-music-detector checkout 6ba389e94a179ac90f3eb134b741ef37baa30434
    git -C ..\FST-AI-Music-Detection checkout b564f8be8b3db6b7810c2aab61f0b4f86f889579
Detached HEAD здесь — ожидаемое и правильное состояние.

ШАГ 3 — создай три Conda-среды, все на Python 3.11. Они раздельные, потому что
детекторы фиксируют несовместимые наборы зависимостей:
    conda create -n ai-music-ui python=3.11 -y
    conda run -n ai-music-ui python -m pip install -r environments\ai-music-ui.txt
    conda create -n ai-music-lofcz python=3.11 -y
    conda run -n ai-music-lofcz python -m pip install -r environments\ai-music-lofcz.txt
    conda create -n ai-music-fst python=3.11 -y
    conda run -n ai-music-fst python -m pip install -r environments\ai-music-fst.txt

ШАГ 4 — скачай модель lofcz. Ссылка в models/sources.json. Сохрани в
    models\lofcz\ai_music_detector.onnx
Проверь через Get-FileHash -Algorithm SHA256. Ожидается:
    af7a75c6ed457bc5b6941c8bc76aa06a66d48de40db944b761ed2bebfc0fbbd3
Если хэш не совпал — остановись и сообщи. Не продолжай с файлом, который не
удалось проверить.

ШАГ 5 — два чекпоинта FST скачать автоматически НЕЛЬЗЯ (Google Drive блокирует
скриптовый доступ). Выведи эти инструкции и жди меня:
    Stage-1.ckpt -> models\fst\Stage-1.ckpt
      https://drive.google.com/file/d/1frT4Mn0l6rso407Sy3eWCKbZmgwuVceN/view
      ожидаемый SHA-256 f9099df5c618a2f92bcd8f4ba48d1c6606f2e4610385b8eea4a03f1a7319629f
    Stage-2.ckpt -> models\fst\Stage-2.ckpt
      https://drive.google.com/file/d/1E_xPsosYWI4UjKT8XQCbZW4ILvsWnmda/view
      ожидаемый SHA-256 ed133c261c5d367fc6adf53813a5c93b62a59de5bef546cf5899a5c157eba7a0
После моего подтверждения, что файлы на месте, проверь оба хэша.

ШАГ 6 — проверь установку:
    conda run -n ai-music-ui python -m pytest -q
    conda run -n ai-music-fst python scripts\make_smoke_wav.py --kind rhythm --seconds 32 --output artifacts\rhythm-smoke.wav
    conda run -n ai-music-lofcz python ..\ai-music-detector\src\python\inference.py --model models\lofcz\ai_music_detector.onnx --input artifacts\rhythm-smoke.wav --output artifacts\lofcz-smoke.csv
    conda run -n ai-music-fst python adapters\fst_cli.py --upstream ..\FST-AI-Music-Detection --stage1 models\fst\Stage-1.ckpt --stage2 models\fst\Stage-2.ckpt --audio artifacts\rhythm-smoke.wav --json-output artifacts\fst-smoke.json
Smoke-файл синтетический. Его score доказывает, что тракт работает, и ничего не
говорит о точности модели — не интерпретируй его.

ШАГ 7 — запиши artifacts\model-manifest.json:
    conda run -n ai-music-fst python scripts\write_model_manifest.py --output artifacts\model-manifest.json models\lofcz\ai_music_detector.onnx models\fst\Stage-1.ckpt models\fst\Stage-2.ckpt

Затем отчитайся: какие шаги прошли, были ли расхождения хэшей и какой именно
командой запускается интерфейс.
```

## Промпт 2 — диагностика сломанной установки

Когда всё работало, а потом перестало.

```text
Продиагностируй эту установку ai-music-lab, ничего не меняя, пока не отчитаешься
о находках. Проверь по порядку:

1. Существуют ли ..\ai-music-detector и ..\FST-AI-Music-Detection как соседи
   этой папки?
2. Чистый ли каждый из них и на зафиксированном ли коммите?
     git -C ..\ai-music-detector rev-parse HEAD    -> 6ba389e94a179ac90f3eb134b741ef37baa30434
     git -C ..\FST-AI-Music-Detection rev-parse HEAD -> b564f8be8b3db6b7810c2aab61f0b4f86f889579
   Сообщи о любой локальной модификации: изменённый upstream обесценивает
   сопоставимость с уже сохранёнными запусками.
3. Существуют ли все три Conda-среды и на Python 3.11 ли каждая?
     conda env list
4. На месте ли все три файла моделей и совпадают ли их SHA-256 с docs\models.md?
5. Проходят ли тесты?  conda run -n ai-music-ui python -m pytest -q
6. Остался ли torchaudio на 2.8.x в средах ai-music-lofcz и ai-music-fst? Версия
   2.9 и выше требует TorchCodec и отдельную full-shared сборку FFmpeg под
   Windows и сломает детекторы.

Сообщи, что не так и что предлагаешь починить, и жди моего одобрения, прежде чем
что-либо менять.
```

## Промпт 3 — обновление upstream-детекторов

Только когда действительно нужен более свежий код детекторов — и с пониманием, что это ломает
сопоставимость с уже сохранёнными запусками.

```text
Обнови два upstream-репозитория детекторов для ai-music-lab.

Сначала: убедись, что оба репозитория чистые. Если у какого-то есть локальные
изменения — остановись и покажи мне diff: проект никогда не меняет upstream,
поэтому локальные правки означают, что раньше что-то пошло не так.

    git -C ..\ai-music-detector status --short
    git -C ..\ai-music-detector fetch origin
    git -C ..\ai-music-detector pull --ff-only

    git -C ..\FST-AI-Music-Detection status --short
    git -C ..\FST-AI-Music-Detection fetch origin
    git -C ..\FST-AI-Music-Detection pull --ff-only

Затем повтори smoke-тесты из docs\cli.md и сообщи новые хэши коммитов.

В конце напомни в итоге, что score, полученные до и после обновления, не
гарантированно лежат на одной шкале, поэтому мне стоит перемерить референсный
материал и записать новый коммит рядом с любым измерением, которое я храню.
```

## Среды в нестандартном месте

Адаптеры ищут среды детекторов рядом с работающим интерпретатором — то есть в стандартной
папке `envs` у Conda. Если у вас они лежат в другом месте, не переносите ничего, а укажите
проекту путь:

```powershell
$env:AI_MUSIC_LOFCZ_PYTHON = "D:\envs\ai-music-lofcz\python.exe"
$env:AI_MUSIC_FST_PYTHON   = "D:\envs\ai-music-fst\python.exe"
```

`AI_MUSIC_UI_HOST` и `AI_MUSIC_UI_PORT` уводят интерфейс с `127.0.0.1:7860`. Смена порта даёт
браузеру новый origin, поэтому запомненный язык сбрасывается.

## Как проверить результат самому

Что бы агент ни отчитался, значение имеют эти четыре проверки:

```powershell
git -C ..\ai-music-detector rev-parse HEAD
git -C ..\FST-AI-Music-Detection rev-parse HEAD
Get-FileHash models\fst\Stage-1.ckpt -Algorithm SHA256
conda run -n ai-music-ui python -m pytest -q
```

Если коммиты совпадают, хэши совпадают и тесты проходят — установка исправна.
