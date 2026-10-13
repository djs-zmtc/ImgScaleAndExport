# ImgScaleAndExport

Proportionally resize a lossless (PNG) source image to one or more sizes, and optionally convert each result to JPG.

## Install / run

```powershell
uv sync
uv run imgscaleandexport Logo_600px.png -height 1080,720,480
uv run imgscaleandexport Logo.png -W 800,400 -jpg -o out -filter lanczos
```

## Options

| Option | Description |
|---|---|
| `source` | Source image (PNG only for now; see `SUPPORTED_SOURCE_FORMATS` in `core.py`) |
| `-H`, `-height`, `--height` | Comma-separated heights (px) — required, exclusive with width |
| `-W`, `-width`, `--width` | Comma-separated widths (px) — required, exclusive with height |
| `-j`, `-jpg`, `--jpg` | Also write a JPG (transparency flattened onto white) |
| `-q`, `-quality`, `--quality` | JPG quality 1–95 (default 90) |
| `-o`, `-output`, `--output-dir` | Destination folder (default: source folder) |
| `-f`, `-filter`, `--filter` | Force NEAREST, BOX, BILINEAR, HAMMING, BICUBIC or LANCZOS |
| `-overwrite`, `-clobber` | Overwrite existing outputs (never the source) |

Default filters: BICUBIC when enlarging, LANCZOS when shrinking.

Output names: `<basename>_<W|H><size>px.<png|jpg>`. A trailing size suffix on the source name (`_600px`, `_HD1080`, `-200x200`) is removed; plain numbers like `-001` are kept.

Exit codes: `0` success (existing files skipped with a warning), `1` errors, `2` invalid arguments.

## Tests

```powershell
uv run pytest
```
