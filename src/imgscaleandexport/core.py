"""Core resize and conversion logic for ImgScaleAndExport."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .naming import build_output_name

logger = logging.getLogger(__name__)

#: Lossless source formats accepted as input, keyed by file extension
#: (lower case, with dot) and mapped to the Pillow format name. Add entries
#: here (e.g. ``".tif": "TIFF"``) to support more lossless formats later.
SUPPORTED_SOURCE_FORMATS: dict[str, str] = {
    ".png": "PNG",
}

#: Resampling filters selectable via ``-filter`` (case-insensitive names).
FILTERS: dict[str, Image.Resampling] = {
    "NEAREST": Image.Resampling.NEAREST,
    "BOX": Image.Resampling.BOX,
    "BILINEAR": Image.Resampling.BILINEAR,
    "HAMMING": Image.Resampling.HAMMING,
    "BICUBIC": Image.Resampling.BICUBIC,
    "LANCZOS": Image.Resampling.LANCZOS,
}

#: Filter used when enlarging an image (when no explicit filter is given).
UPSCALE_FILTER = Image.Resampling.BICUBIC
#: Filter used when shrinking (or keeping) an image size.
DOWNSCALE_FILTER = Image.Resampling.LANCZOS
#: Solid background used when flattening transparency for JPG output.
JPEG_BACKGROUND = (255, 255, 255)


class ImgScaleError(Exception):
    """Raised for invalid input or unrecoverable processing errors."""


@dataclass(frozen=True)
class Result:
    """Outcome for a single output file."""

    path: Path
    status: str  # "written", "skipped", or "error"
    message: str = ""


def validate_source(source: Path) -> None:
    """Ensure the source exists, is a file, and has a supported extension.

    Raises:
        ImgScaleError: If the source is missing or its format is unsupported.
    """
    if not source.is_file():
        raise ImgScaleError(f"Source image not found: {source}")
    if source.suffix.lower() not in SUPPORTED_SOURCE_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_SOURCE_FORMATS))
        raise ImgScaleError(
            f"Unsupported source format '{source.suffix}'. Supported: {supported}"
        )


def compute_target_size(
    current: tuple[int, int], axis: str, size: int
) -> tuple[int, int]:
    """Compute proportional (width, height) for the requested axis size.

    The other dimension is rounded to the nearest pixel (minimum 1).
    """
    width, height = current
    if axis == "W":
        return size, max(1, round(height * size / width))
    return max(1, round(width * size / height)), size


def select_filter(
    current_dim: int, target_dim: int, override: Image.Resampling | None
) -> Image.Resampling:
    """Choose a resampling filter.

    An explicit ``override`` always wins. Otherwise BICUBIC is used for
    enlarging and LANCZOS for shrinking (or equal size).
    """
    if override is not None:
        return override
    return UPSCALE_FILTER if target_dim > current_dim else DOWNSCALE_FILTER


def flatten_to_rgb(image: Image.Image) -> Image.Image:
    """Return an RGB copy of ``image`` composited onto solid white."""
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (*JPEG_BACKGROUND, 255))
    return Image.alpha_composite(background, rgba).convert("RGB")


def _is_source(path: Path, source: Path) -> bool:
    """True if ``path`` refers to the same file as ``source``."""
    try:
        return path.resolve() == source.resolve() or (
            path.exists() and path.samefile(source)
        )
    except OSError:
        return False


def _write(
    image: Image.Image,
    path: Path,
    source: Path,
    overwrite: bool,
    save_kwargs: dict,
) -> Result:
    """Save ``image`` to ``path`` honouring overwrite and source protection."""
    if _is_source(path, source):
        return Result(path, "skipped", "refusing to overwrite the source image")
    if path.exists() and not overwrite:
        return Result(path, "skipped", "already exists (use -overwrite)")
    try:
        image.save(path, **save_kwargs)
    except OSError as exc:
        return Result(path, "error", str(exc))
    return Result(path, "written")


def process_image(
    source: Path,
    axis: str,
    sizes: list[int],
    output_dir: Path | None = None,
    to_jpg: bool = False,
    filter_override: Image.Resampling | None = None,
    overwrite: bool = False,
    quality: int = 90,
) -> list[Result]:
    """Resize ``source`` to each size and optionally also export JPGs.

    Args:
        source: Source image path (must be a supported lossless format).
        axis: ``"W"`` to resize by width, ``"H"`` by height.
        sizes: Target pixel sizes along ``axis``.
        output_dir: Destination folder (defaults to the source's folder);
            created if missing.
        to_jpg: Also write a JPG for every resized PNG.
        filter_override: Resampling filter overriding the automatic choice.
        overwrite: Allow replacing existing output files (never the source).
        quality: JPG quality (1-95).

    Returns:
        One :class:`Result` per file attempted.

    Raises:
        ImgScaleError: On invalid source, or unreadable image.
    """
    validate_source(source)
    dest = output_dir if output_dir is not None else source.parent
    try:
        dest.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as opened:
            opened.load()
            original = opened.copy()
    except (OSError, Image.DecompressionBombError) as exc:
        raise ImgScaleError(f"Cannot read '{source}': {exc}") from exc

    src_dim = original.width if axis == "W" else original.height
    results: list[Result] = []

    for size in sizes:
        target = compute_target_size(original.size, axis, size)
        resample = select_filter(src_dim, size, filter_override)
        resized = original.resize(target, resample=resample)

        png_path = dest / build_output_name(source, axis, size, "png")
        results.append(_write(resized, png_path, source, overwrite, {"format": "PNG"}))

        if to_jpg:
            jpg_path = dest / build_output_name(source, axis, size, "jpg")
            results.append(
                _write(
                    flatten_to_rgb(resized),
                    jpg_path,
                    source,
                    overwrite,
                    {"format": "JPEG", "quality": quality},
                )
            )
    return results
