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

## Transcription weights (muscriptor)

Not in the table above, and deliberately handled differently. They are **gated**: Hugging Face
serves them only to an account that has accepted CC BY-NC 4.0, so there is no anonymous URL to
publish, and the app downloads them from the settings panel rather than by hand.

| Variant | Parameters | Download | Repository |
| --- | ---: | ---: | --- |
| `small` | 103M | ~0.4 GB | [MuScriptor/muscriptor-small](https://huggingface.co/MuScriptor/muscriptor-small) |
| `medium` | 307M | ~1.2 GB | [MuScriptor/muscriptor-medium](https://huggingface.co/MuScriptor/muscriptor-medium) |
| `large` | 1.4B | ~5.6 GB | [MuScriptor/muscriptor-large](https://huggingface.co/MuScriptor/muscriptor-large) |

There is no SHA-256 table here because there is nothing to hand-verify: `huggingface_hub`
validates what it downloads, and the adapter then re-resolves the cache with `HF_HUB_OFFLINE=1`
so a green checkbox means the weights really load, not merely that a file appeared.

They land in `models/muscriptor-cache/` — the app points `HF_HOME` there so gigabytes of
checkpoints stay off the system drive. Setup and token handling: [Audio → MIDI](midi.md).

## Licensing

The model weights are **not** covered by this repository's MIT license. They keep the terms set
by their own publishers, and this project neither redistributes nor modifies them — it only
loads files you downloaded yourself. Check the upstream terms before using any output
commercially.

The muscriptor weights make that concrete: **CC BY-NC 4.0, non-commercial use only**, with a
further condition in the model card against using the output for illegal or unauthorised
activity, transcribing music you hold no rights to included.
