# Модели

[← Документация](README.md) · [English](../models.md)

Нужны три файла весов. Они лежат вне upstream-репозиториев, игнорируются Git и скачиваются из
официальных источников.

## Файлы и источники

| Файл | Источник |
| --- | --- |
| `models/lofcz/ai_music_detector.onnx` | [Hugging Face — lofcz/ai-music-detector](https://huggingface.co/lofcz/ai-music-detector) |
| `models/fst/Stage-1.ckpt` | [Google Drive](https://drive.google.com/file/d/1frT4Mn0l6rso407Sy3eWCKbZmgwuVceN/view) |
| `models/fst/Stage-2.ckpt` | [Google Drive](https://drive.google.com/file/d/1E_xPsosYWI4UjKT8XQCbZW4ILvsWnmda/view) |

Те же ссылки в машиночитаемом виде — в [`models/sources.json`](../../models/sources.json).

## Проверенные контрольные суммы

Проверьте скачанное, прежде чем доверять сделанным на нём измерениям.

| Файл | Размер (байт) | SHA-256 |
| --- | ---: | --- |
| `ai_music_detector.onnx` | 14 795 | `af7a75c6ed457bc5b6941c8bc76aa06a66d48de40db944b761ed2bebfc0fbbd3` |
| `Stage-1.ckpt` | 1 287 502 845 | `f9099df5c618a2f92bcd8f4ba48d1c6606f2e4610385b8eea4a03f1a7319629f` |
| `Stage-2.ckpt` | 47 513 137 | `ed133c261c5d367fc6adf53813a5c93b62a59de5bef546cf5899a5c157eba7a0` |

Под Windows:

```powershell
Get-FileHash models\fst\Stage-1.ckpt -Algorithm SHA256
```

## Пересоздание манифеста

`artifacts/model-manifest.json` фиксирует хэши файлов, реально лежащих на диске:

```powershell
conda run -n ai-music-fst python scripts\write_model_manifest.py --output artifacts\model-manifest.json models\lofcz\ai_music_detector.onnx models\fst\Stage-1.ckpt models\fst\Stage-2.ckpt
```

Пересоздавайте манифест после замены любого файла весов. Измерение воспроизводимо только если
известно, какие именно веса его дали.

## Дополнительные веса

FST дополнительно скачивает веса эмбеддингов MERT с Hugging Face при первом запуске. Они
попадают в стандартный кэш Hugging Face, а не в `models/`, поэтому первый анализ FST после
чистой установки заметно дольше последующих.

## Лицензирование

Веса моделей **не** покрываются лицензией MIT этого репозитория. Они сохраняют условия своих
публикаторов, а проект их не распространяет и не изменяет — только загружает файлы, которые вы
скачали сами. Перед коммерческим использованием результатов проверьте условия upstream.
