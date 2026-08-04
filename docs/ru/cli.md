# Командная строка

[← Документация](README.md) · [English](../cli.md)

Всё, что делает интерфейс, можно запустить напрямую. Все команды — из корня репозитория.

## lofcz

Один файл или целая папка; результат пишется в CSV:

```powershell
conda run -n ai-music-lofcz python ..\ai-music-detector\src\python\inference.py --model models\lofcz\ai_music_detector.onnx --input "path\to\stem.wav" --output artifacts\lofcz-result.csv
```

Режим карты по времени идёт через адаптер этого репозитория — см.
[Карту по времени](timeline.md#из-командной-строки).

## FST

Один файл; результат печатается и сохраняется в JSON:

```powershell
conda run -n ai-music-fst python adapters\fst_cli.py --upstream ..\FST-AI-Music-Detection --stage1 models\fst\Stage-1.ckpt --stage2 models\fst\Stage-2.ckpt --audio "path\to\stem.wav" --json-output artifacts\fst-result.json
```

FST сначала ищет beats и downbeats. Полный микс, барабаны и ритмические стемы подходят ему
лучше всего. На вокале, ambience или другом материале без определяемого пульса адаптер
завершится сообщением `FST preprocessing found no beat-aligned segments`, а не запишет ложный
`Real / NaN`.

`--backbone-batch` задаёт, сколько из 48 сегментов идут через backbone за раз. Умолчание 8 даёт
пик 4,8 ГБ видеопамяти; `0` отправляет все 48 одним проходом, как в апстриме, — 16 ГБ за то же
время. Использованное значение записывается в телеметрию запуска: оно способно сдвинуть сырой
логит на один ulp float16, а значит входит в то, чем получена оценка. См.
[чего это стоит по железу](../../README.ru.md#чего-это-стоит-по-железу).

## Smoke-тесты

```powershell
conda run -n ai-music-ui python -m pytest -q
conda run -n ai-music-ui python -m scripts.smoke_ui_pipeline artifacts\rhythm-smoke.wav
conda run -n ai-music-fst python -m pytest tests -v
conda run -n ai-music-fst python scripts\make_smoke_wav.py --kind rhythm --seconds 32 --output artifacts\rhythm-smoke.wav
conda run -n ai-music-fst python adapters\fst_cli.py --upstream ..\FST-AI-Music-Detection --stage1 models\fst\Stage-1.ckpt --stage2 models\fst\Stage-2.ckpt --audio artifacts\rhythm-smoke.wav --json-output artifacts\fst-smoke.json
conda run -n ai-music-lofcz python ..\ai-music-detector\src\python\inference.py --model models\lofcz\ai_music_detector.onnx --input artifacts\rhythm-smoke.wav --output artifacts\lofcz-smoke.csv
```

Синтетический файл нужен, чтобы доказать работоспособность тракта от начала до конца. **Его
score ничего не говорит о реальной точности модели** — это сгенерированный ритм, а не музыка.

## Обновление upstream

Обновляйте каждый репозиторий отдельно и только при чистом статусе:

```powershell
git -C ..\ai-music-detector status --short
git -C ..\ai-music-detector fetch origin
git -C ..\ai-music-detector pull --ff-only

git -C ..\FST-AI-Music-Detection status --short
git -C ..\FST-AI-Music-Detection fetch origin
git -C ..\FST-AI-Music-Detection pull --ff-only
```

После этого повторите smoke-тесты. Никогда не коммитьте файлы обёртки и веса в upstream-репозиторий.

Обновление upstream обесценивает сопоставимость: score, полученные до и после, не гарантированно
лежат на одной шкале. Записывайте новый коммит рядом с любым измерением, которое собираетесь
хранить, и перемеряйте референсный материал.

## Снимки зависимостей

`environments/ai-music-lofcz.txt` и `environments/ai-music-fst.txt` — замороженные снимки того,
что было реально установлено на момент проверки зафиксированных коммитов.
