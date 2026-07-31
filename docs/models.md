# Models

[← Documentation](README.md) · [Русский](ru/models.md)

Three checkpoint files are required. They live outside the upstream repositories, are ignored
by Git, and must be downloaded from their official sources.

## Files and sources

| File | Source |
| --- | --- |
| `models/lofcz/ai_music_detector.onnx` | [Hugging Face — lofcz/ai-music-detector](https://huggingface.co/lofcz/ai-music-detector) |
| `models/fst/Stage-1.ckpt` | [Google Drive](https://drive.google.com/file/d/1frT4Mn0l6rso407Sy3eWCKbZmgwuVceN/view) |
| `models/fst/Stage-2.ckpt` | [Google Drive](https://drive.google.com/file/d/1E_xPsosYWI4UjKT8XQCbZW4ILvsWnmda/view) |

The same URLs are kept machine-readable in [`models/sources.json`](../models/sources.json).

## Verified checksums

Verify what you downloaded before trusting any measurement made with it.

| File | Size (bytes) | SHA-256 |
| --- | ---: | --- |
| `ai_music_detector.onnx` | 14,795 | `af7a75c6ed457bc5b6941c8bc76aa06a66d48de40db944b761ed2bebfc0fbbd3` |
| `Stage-1.ckpt` | 1,287,502,845 | `f9099df5c618a2f92bcd8f4ba48d1c6606f2e4610385b8eea4a03f1a7319629f` |
| `Stage-2.ckpt` | 47,513,137 | `ed133c261c5d367fc6adf53813a5c93b62a59de5bef546cf5899a5c157eba7a0` |

On Windows:

```powershell
Get-FileHash models\fst\Stage-1.ckpt -Algorithm SHA256
```

## Regenerating the manifest

`artifacts/model-manifest.json` records the hashes of the files actually present on disk:

```powershell
conda run -n ai-music-fst python scripts\write_model_manifest.py --output artifacts\model-manifest.json models\lofcz\ai_music_detector.onnx models\fst\Stage-1.ckpt models\fst\Stage-2.ckpt
```

Regenerate it after replacing any checkpoint. A measurement is only reproducible if you know
which weights produced it.

## Additional weights

FST also pulls MERT embedding weights from Hugging Face on first run. They land in the standard
Hugging Face cache rather than in `models/`, so the first FST analysis after a fresh install
takes noticeably longer than later ones.

## Licensing

The model weights are **not** covered by this repository's MIT license. They keep the terms set
by their own publishers, and this project neither redistributes nor modifies them — it only
loads files you downloaded yourself. Check the upstream terms before using any output
commercially.
