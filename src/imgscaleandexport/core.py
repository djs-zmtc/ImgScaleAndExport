"""Core resize and conversion logic for ImgScaleAndExport."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .naming import build_output_name

logger = logging.getLogger(__name__)

#: Supported source formats accepted as input, keyed by file extension
#: (lower case, with dot) and mapped to the Pillow format name.
SUPPORTED_SOURCE_FORMATS: dict[str, str] = {
    ".bmp": "BMP",
    ".png": "PNG",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".webp": "WEBP",
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
#: Quality floor when searching by percentage target.
MIN_JPG_PERCENT_QUALITY = 30
#: Quality ceiling when searching by percentage target.
MAX_JPG_PERCENT_QUALITY = 95
#: Standard heights for the --standard shortcut.
STANDARD_HEIGHTS: list[int] = [240, 360, 480, 720, 1080, 1440, 2160]
#: Standard JPG target size percentage for the --standard shortcut.
STANDARD_JPG_PERCENT: float = 10.0
#: Default quality setting for lossy WebP output (recommended WebP quality).
DEFAULT_WEBP_QUALITY: int = 80



class ImgScaleError(Exception):
    """Raised for invalid input or unrecoverable processing errors."""


@dataclass(frozen=True)
class Result:
    """Outcome for a single output file."""

    path: Path
    status: str  # "written", "skipped", or "error"
    message: str = ""
    quality: int | None = None



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


def find_best_jpg_quality(
    image: Image.Image,
    target_bytes: int,
    min_q: int = MIN_JPG_PERCENT_QUALITY,
    max_q: int = MAX_JPG_PERCENT_QUALITY,
) -> tuple[int, bytes]:
    """Find the highest JPEG quality that keeps compressed size under target_bytes.

    Uses binary search over quality settings in memory without writing to disk.
    If the target size is unreachable even at ``min_q``, the ``min_q`` compressed
    bytes are returned.

    Args:
        image: RGB Image to compress.
        target_bytes: Maximum desired file size in bytes.
        min_q: Quality floor (default 30).
        max_q: Quality ceiling (default 95).

    Returns:
        A tuple of (selected_quality, jpeg_bytes).
    """
    low, high = min_q, max_q
    best_q = min_q
    best_data: bytes | None = None
    cache: dict[int, bytes] = {}

    while low <= high:
        mid = (low + high) // 2
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=mid, optimize=True)
        data = buf.getvalue()
        cache[mid] = data
        size = len(data)

        if size <= target_bytes:
            best_q = mid
            best_data = data
            low = mid + 1
        else:
            high = mid - 1

    if best_data is None:
        best_q = min_q
        if min_q in cache:
            best_data = cache[min_q]
        else:
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=min_q, optimize=True)
            best_data = buf.getvalue()

    return best_q, best_data


def _is_source(path: Path, source: Path) -> bool:
    """True if ``path`` refers to the same file as ``source``."""
    try:
        return path.resolve() == source.resolve() or (
            path.exists() and path.samefile(source)
        )
    except OSError:
        return False


def _write(
    target: Image.Image | bytes,
    path: Path,
    source: Path,
    overwrite: bool,
    save_kwargs: dict | None = None,
    quality: int | None = None,
) -> Result:
    """Save ``target`` to ``path`` honouring overwrite and source protection."""
    if _is_source(path, source):
        return Result(path, "skipped", "refusing to overwrite the source image")
    if path.exists() and not overwrite:
        return Result(path, "skipped", "already exists (use -overwrite)")
    try:
        if isinstance(target, bytes):
            path.write_bytes(target)
        else:
            target.save(path, **(save_kwargs or {}))
    except OSError as exc:
        return Result(path, "error", str(exc))
    return Result(path, "written", quality=quality)


def process_image(
    source: Path,
    axis: str,
    sizes: list[int],
    output_dir: Path | None = None,
    to_jpg: bool = False,
    to_webp: bool = False,
    filter_override: Image.Resampling | None = None,
    overwrite: bool = False,
    quality: int = 90,
    jpg_percent: float | None = None,
    webp_quality: int = DEFAULT_WEBP_QUALITY,
) -> list[Result]:
    """Resize ``source`` to each size and optionally also export JPGs or WebPs.

    Args:
        source: Source image path (must be a supported lossless/input format).
        axis: ``"W"`` to resize by width, ``"H"`` by height.
        sizes: Target pixel sizes along ``axis``.
        output_dir: Destination folder (defaults to the source's folder);
            created if missing.
        to_jpg: Also write a JPG for every resized PNG.
        to_webp: Also write a WebP for every resized image.
        filter_override: Resampling filter overriding the automatic choice.
        overwrite: Allow replacing existing output files (never the source).
        quality: JPG quality (1-95) when ``jpg_percent`` is not specified.
        jpg_percent: Target JPG size as a percentage of PNG size (auto-selects
            quality between 30 and 95; implies JPG export).
        webp_quality: WebP quality (1-100, default: 80).

    Returns:
        One :class:`Result` per file attempted.

    Raises:
        ImgScaleError: On invalid source, or unreadable image.
    """
    validate_source(source)
    dest = output_dir if output_dir is not None else source.parent
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ImgScaleError(
            f"Cannot create destination directory '{dest}': {exc}"
        ) from exc

    try:
        with Image.open(source) as opened:
            opened.load()
            original = opened.copy()
    except (OSError, Image.DecompressionBombError) as exc:
        raise ImgScaleError(f"Cannot read '{source}': {exc}") from exc

    if original.mode not in ("1", "L", "LA", "P", "RGB", "RGBA"):
        original = original.convert("RGBA" if "A" in original.mode else "RGB")

    src_dim = original.width if axis == "W" else original.height
    results: list[Result] = []

    for size in sizes:
        target = compute_target_size(original.size, axis, size)
        resample = select_filter(src_dim, size, filter_override)
        resized = original.resize(target, resample=resample)

        png_path = dest / build_output_name(source, axis, size, "png")
        results.append(_write(resized, png_path, source, overwrite, {"format": "PNG"}))

        if to_jpg or jpg_percent is not None:
            jpg_path = dest / build_output_name(source, axis, size, "jpg")
            rgb_image = flatten_to_rgb(resized)

            if jpg_percent is not None:
                if png_path.exists():
                    png_size = png_path.stat().st_size
                else:
                    buf = io.BytesIO()
                    resized.save(buf, format="PNG")
                    png_size = buf.tell()

                target_bytes = max(1, round(png_size * (jpg_percent / 100)))
                actual_q, jpg_bytes = find_best_jpg_quality(rgb_image, target_bytes)
                results.append(_write(jpg_bytes, jpg_path, source, overwrite, quality=actual_q))
            else:
                results.append(
                    _write(
                        rgb_image,
                        jpg_path,
                        source,
                        overwrite,
                        {"format": "JPEG", "quality": quality, "optimize": True},
                        quality=quality,
                    )
                )

        if to_webp:
            webp_path = dest / build_output_name(source, axis, size, "webp")
            results.append(
                _write(
                    resized,
                    webp_path,
                    source,
                    overwrite,
                    {"format": "WEBP", "quality": webp_quality},
                    quality=webp_quality,
                )
            )
    return results
