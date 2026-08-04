# Начало работы

[← Документация](README.md) · [English](../getting-started.md)

## Что нужно

| Требование | Зачем |
| --- | --- |
| Windows | Лаунчер и пути заточены под PowerShell, см. [примечание о платформе](#примечание-о-платформе) |
| Видеокарта NVIDIA + драйвер | FST работает на CUDA; 32-секундный файл занимает около 19 с на RTX 4090 |
| [Conda](https://docs.conda.io/projects/miniconda/) | Каждому детектору нужен свой набор зависимостей |
| Git | Оба детектора клонируются, а не включаются в репозиторий |

Docker не нужен. Глобальный FFmpeg тоже не нужен — все среды читают WAV, FLAC и MP3 через
backend `soundfile`. Windows Developer Mode необязателен: без него кэш Hugging Face работает
без symlink и занимает чуть больше места.

## 1. Клонировать обёртку и апстримы

Апстримы лежат **рядом** с этим репозиторием, а не внутри него. Адаптеры по умолчанию
рассчитывают именно на такую раскладку.

```powershell
git clone https://github.com/bionicle12/ai-music-lab.git
git clone https://github.com/lofcz/ai-music-detector.git
git clone https://github.com/Mippia/FST-AI-Music-Detection.git
git clone https://github.com/muscriptor/muscriptor.git
```

Должно получиться так:

```text
<родительская папка>/
├── ai-music-lab/            # этот репозиторий
├── ai-music-detector/       # upstream lofcz
├── FST-AI-Music-Detection/  # upstream FST
└── muscriptor/              # аудио → MIDI, необязательно
```

`muscriptor` нужен только для перевода в MIDI — пропустите его, если хватает детекции.

## 2. Создать среды

Conda-среды, потому что апстримы фиксируют несовместимые наборы зависимостей. Для самого
интерфейса нужна только среда UI.

```powershell
cd ai-music-lab

conda create -n ai-music-ui python=3.11 -y
conda run -n ai-music-ui python -m pip install -r environments\ai-music-ui.txt

conda create -n ai-music-lofcz python=3.11 -y
conda run -n ai-music-lofcz python -m pip install -r environments\ai-music-lofcz.txt

conda create -n ai-music-fst python=3.11 -y
conda run -n ai-music-fst python -m pip install -r environments\ai-music-fst.txt
```

Для перевода в MIDI — четвёртая среда. muscriptor ставится **editable из клона**, чтобы
последующий `git pull` обновлял тот код, который реально исполняется, — см.
[Аудио → MIDI](midi.md). Это ещё одна полная установка torch, примерно 2.5 ГБ на диске.

```powershell
conda create -n ai-music-muscriptor python=3.11 -y
conda run -n ai-music-muscriptor python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
conda run -n ai-music-muscriptor python -m pip install -e ..\muscriptor
```

Файлы `environments/*.txt` — это снимки реально установленного, а не написанный вручную минимум.

## 3. Скачать модели

Три файла весов кладутся в `models/`. В Git их нет — официальные источники и SHA-256 для
проверки в **[Моделях](models.md)**.

```text
models/lofcz/ai_music_detector.onnx
models/fst/Stage-1.ckpt
models/fst/Stage-2.ckpt
```

## 4. Запустить

```powershell
.\start_ui.ps1
```

Откройте `http://127.0.0.1:7860`. Лаунчер принудительно ставит UTF-8 для консоли и дочернего
Python-процесса — без этого Windows PowerShell 5.1 превращает не-ASCII текст интерфейса в
кракозябры.

## Язык

Интерфейс собирается отдельно под каждый язык и отдаётся по своему пути:

| Язык | Адрес |
| --- | --- |
| Английский (по умолчанию) | `http://127.0.0.1:7860/` |
| Русский | `http://127.0.0.1:7860/ru` |

Переключатель — под заголовком. Выбор сохраняется в `localStorage` браузера, поэтому
следующий заход на `/` сразу открывает нужный язык.

Две оговорки. `localStorage` привязан к origin целиком, поэтому `http://localhost:7860` и
`http://127.0.0.1:7860` хранят **разный** выбор, а смена порта начинает с нуля. В приватном
окне не запоминается ничего — каждый раз отдаётся язык по умолчанию.

Переключение перезагружает страницу, потому что каждый язык — отдельно собранный интерфейс.
Именно это позволяет перевести всё, включая подписи осей Plotly и сгенерированные карточки
детекторов. Уже сохранённые анализы не затрагиваются — откройте запуск из истории.

## Первый анализ

1. Загрузите WAV, FLAC или MP3 — микс, стем или отдельный слой.
2. При желании добавьте заметку к версии (`vocal stem после de-esser v2`).
3. Выберите `lofcz`, `FST` или оба.
4. Нажмите **Запустить анализ**.

Каждый запуск сохраняется в `data/runs/<run_id>/`, индекс — в `data/history.sqlite3`. Папка
`data/` игнорируется Git. Анализ одного файла не создаёт baseline и не сравнивает его с
предыдущими треками — сравнение всегда явное, см. [Сравнение A/B](comparison.md).

Если хочется сперва убедиться, что тракт работает, не подбирая реальное аудио, сгенерируйте
синтетический файл — см. [Командную строку](cli.md#smoke-тесты). Его score ничего не говорит о
точности модели.

## Типичные проблемы

**Язык постоянно сбрасывается на английский.** Выбор хранится в `localStorage`, а он привязан
к origin. Заход через другое написание хоста или другой порт — уже другой origin; в приватном
окне выбор не сохраняется никогда.

**`/ru` отдаёт 404.** Локальные пути нужно регистрировать до корневого mount — это делает
`build_server()`. Если монтируете интерфейс сами, сохраняйте тот же порядок.

**Не-ASCII текст выглядит как `????` или кракозябры.** Запускайте через `start_ui.ps1`, а не
модуль напрямую — настройка кодировки живёт именно в этом скрипте.

**`FST preprocessing found no beat-aligned segments`.** Это не сбой. FST нужны различимые доли
и сильные доли, а у вокала, ambience и пэдов их часто нет. Для такого материала используйте
lofcz. См. [Ограничения](limitations.md).

**FST медленный при первом запуске.** Он один раз докачивает веса MERT в кэш Hugging Face.

**Пересоздать только UI-среду:**

```powershell
conda create -n ai-music-ui python=3.11 -y
conda run -n ai-music-ui python -m pip install -r environments\ai-music-ui.txt
```

## Примечание о платформе

Проект собран и используется под Windows на одной машине с RTX 4090; кросс-платформенность не
планируется. В коде анализа нет ничего намеренно Windows-специфичного, но лаунчер,
документированные команды и пути рассчитаны на PowerShell и Conda, а другие платформы не
тестировались.

## Зафиксированное окружение

| Компонент | Версия |
| --- | --- |
| upstream lofcz | `6ba389e94a179ac90f3eb134b741ef37baa30434` |
| upstream FST | `b564f8be8b3db6b7810c2aab61f0b4f86f889579` |
| upstream muscriptor | `e2bd0fc5994f9acba7c1387ca5df67eb8d95df44` (`0.2.2`) |
| Python | `3.11` |
| PyTorch / TorchAudio | `2.8.0+cu128` в средах детекторов |
| Gradio | `6.20.0` |
| GPU | NVIDIA GeForce RTX 4090 |

TorchAudio намеренно зафиксирован на 2.8: upstream использует старый путь `torchaudio.load`, а начиная
с 2.9 он требует TorchCodec и отдельную full-shared сборку FFmpeg под Windows. Среда muscriptor
отдельная и этим не затронута, поэтому там стоит актуальный torch.

Два коммита детекторов — это именно *пины*: их score сравнимы между запусками, только пока не
менялся код, который их произвёл. muscriptor в этом смысле не пин — его коммит просто та версия,
против которой обёртка проверялась, и настройки умеют перематывать его вперёд.
