# ImgScaleAndExport

Proportionally resize a lossless (PNG) source image to one or more sizes, and optionally convert each result to JPG.
Useful for creating multiple sizes of a specific icon, logo or meme image. Currently accepts `PNG` as the source image
and generates resized `PNG` and (optionally) `JPG` images.

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
| `-H`, `-height`, `--height` | Comma-separated heights (px) — required, exclusive with width and standard |
| `-W`, `-width`, `--width` | Comma-separated widths (px) — required, exclusive with height and standard |
| `-S`, `-standard`, `--standard` | Preset shortcut: heights `240,360,480,720,1080,1440,2160` with 10% JPG target size |
| `-j`, `-jpg`, `--jpg` | Also write a JPG (transparency flattened onto white) |
| `-q`, `-quality`, `--quality` | Explicit JPG quality 1–95 (default: 90) |
| `-jpg-percent`, `--jpg-percent` | Target JPG file size as % of PNG size (auto quality 30–95, implies `-jpg`) |
| `-o`, `-output`, `--output-dir` | Destination folder (default: source folder) |
| `-f`, `-filter`, `--filter` | Force NEAREST, BOX, BILINEAR, HAMMING, BICUBIC or LANCZOS |
| `-overwrite`, `-clobber` | Overwrite existing outputs (never the source) |

Default filters: BICUBIC when enlarging, LANCZOS when shrinking.

Output names: `<basename>_<size>px<W|H>.<png|jpg>`. A trailing size suffix on the source name (`_600px`, `_HD1080`, `-200x200`) is removed; plain numbers like `-001` are kept.

Exit codes: `0` success (existing files skipped with a warning), `1` errors, `2` invalid arguments.

## Tests

```powershell
uv run pytest
```

## Build the EXE

```powershell
.\build-exe.ps1     # or build-exe.cmd  -> dist\ImgScaleAndExport.exe
```

## Release and Scoop install

1. Bump `version` in `pyproject.toml`, commit, then tag: `git tag v0.1.0; git push --tags`.
2. The `Release` GitHub Action tests, builds the EXE, zips it as `ImgScaleAndExport-v<version>-win64.zip` and publishes a GitHub Release. The ZIP's SHA256 is printed in the release notes.
3. For the first release, copy `ImgScaleAndExport.json` into the `bucket/` folder of the [ZMT-Creative/scoop-bucket](https://github.com/ZMT-Creative/scoop-bucket) repo and replace the placeholder `hash` with the SHA256 from the release notes. Later versions are bumped by the bucket's `checkver`/Excavator automation.

Install:

```powershell
scoop bucket add zmtc https://github.com/ZMT-Creative/scoop-bucket
scoop install zmtc/imgscaleandexport
```
