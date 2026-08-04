# Vendored fonts

These files are committed on purpose. The app's premise is that nothing leaves
the machine, and a stylesheet link to `fonts.googleapis.com` would contradict
that on every launch — as well as breaking the interface on a machine with no
network, which is a normal way to run this tool.

They are also the reason the interface is legible in Russian: the previous
default rendered Cyrillic in whatever the system happened to supply.

Regenerate with:

```powershell
conda run -n ai-music-ui python scripts\vendor_fonts.py
```

That script reads Google's `css2` API, which already splits each family by
`unicode-range`, and saves the `latin`, `latin-ext`, `cyrillic` and
`cyrillic-ext` slices verbatim — no local `pyftsubset` step, and the ranges in
`fonts.css` are the ones upstream publishes rather than ones we guessed. Both
families are variable, so one file per slice covers every weight.

## Files

| File | Family | Subset | Bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
| `manrope-latin.woff2` | Manrope | latin | 24,836 | `a30ddcd349703aff7464c34bef3fffdff405ee50c113440d7c8693c02d210972` |
| `manrope-latin-ext.woff2` | Manrope | latin-ext | 15,120 | `3911b66d9f2e005a4b989223405d0e5032619c668597ba467cc76a23c8fffcfb` |
| `manrope-cyrillic.woff2` | Manrope | cyrillic | 14,500 | `c268b459a9329e59fecf39a17618efd44c71735532048d60b12aab76a8c14914` |
| `manrope-cyrillic-ext.woff2` | Manrope | cyrillic-ext | 2,552 | `de37de877dc17e4577341fa68bb5cb526b53d54cb29721e674208546a3c7849d` |
| `jetbrains-mono-latin.woff2` | JetBrains Mono | latin | 31,432 | `83c005d49d8a6a50474c73a5a36ac0468076e9c4a29da7bdb14995d80560a5be` |
| `jetbrains-mono-latin-ext.woff2` | JetBrains Mono | latin-ext | 11,624 | `db5ff4db83e580426280e9337a58dc57d3a83784a1b03ad80914651594441d52` |
| `jetbrains-mono-cyrillic.woff2` | JetBrains Mono | cyrillic | 8,872 | `e17cfd15fb96909d64095015f958207063a0c07191da3512df7d560a781aebdf` |
| `jetbrains-mono-cyrillic-ext.woff2` | JetBrains Mono | cyrillic-ext | 1,640 | `62213be8a78b42f1e29d1452d91e2f8b3e745572a9dd98d3941e39fa00b37d76` |

110 KB total, all weights, both scripts.

## Licences

Both families are under the SIL Open Font License 1.1, which permits
redistribution provided the licence travels with the files:

- Manrope — Mikhail Sharanda. `manrope-OFL.txt`
- JetBrains Mono — JetBrains s.r.o. `jetbrains-mono-OFL.txt`

The files are unmodified slices as published, so no Reserved Font Name question
arises: nothing here is a derivative that would need renaming.

## Serving

`fonts.css` is generated with absolute `/lab-assets/fonts/…` URLs and is
inlined into the page `<head>` by `music_lab_ui/app.py::font_face_head()`.

Absolute, not relative, because the interface is mounted twice — at `/` for
English and `/ru/` for Russian — and a relative `url()` resolves against the
document, so the Russian build would look for the files one directory down.

`/lab-assets` is mounted in `build_server()` **before** the Gradio mounts,
because the root mount swallows every unmatched path. It must not be called
`/static` or `/assets`: Gradio reserves both and serves its own bundled fonts
from `/static/fonts/`.
