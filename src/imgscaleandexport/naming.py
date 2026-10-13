"""Output filename helpers for ImgScaleAndExport."""

from __future__ import annotations

import re
from pathlib import Path

# Size-suffix patterns stripped from the source basename. A trailing segment
# (introduced by "-" or "_") is only removed when it clearly describes a size:
#   * a letter prefix directly followed by digits, optionally "px"  (``_HD1080``)
#   * WIDTHxHEIGHT, optionally "px"                         (e.g. ``-200x200``)
#   * digits followed by "px"                               (e.g. ``_600px``)
# Plain trailing numbers such as ``-001`` are intentionally preserved.
SIZE_SUFFIX_RE = re.compile(
    r"[-_](?:[A-Za-z]+\d+(?:px)?|\d+x\d+(?:px)?|\d+px)$",
    re.IGNORECASE,
)


def strip_size_suffix(stem: str) -> str:
    """Remove a trailing size descriptor from a filename stem.

    Args:
        stem: Filename without its extension.

    Returns:
        The stem without its size suffix. If stripping would leave an empty
        string, the original stem is returned unchanged.
    """
    stripped = SIZE_SUFFIX_RE.sub("", stem)
    return stripped or stem


def build_output_name(source: Path, axis: str, size: int, extension: str) -> str:
    """Build an output filename such as ``Imagefile-001_H720px.png``.

    Args:
        source: Path of the source image.
        axis: ``"W"`` (resize by width) or ``"H"`` (resize by height).
        size: Target size in pixels.
        extension: Extension without the leading dot (e.g. ``"png"``).

    Returns:
        The output filename (no directory component).

    Raises:
        ValueError: If ``axis`` is not ``"W"`` or ``"H"``.
    """
    if axis not in ("W", "H"):
        raise ValueError(f"axis must be 'W' or 'H', got {axis!r}")
    base = strip_size_suffix(source.stem)
    return f"{base}_{axis}{size}px.{extension}"
