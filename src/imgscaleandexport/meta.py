"""Program title and version metadata for ImgScaleAndExport."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

#: Human-readable program title shown in ``--help`` output.
TITLE = "Image Scale and Export"

#: Program executable name shown in usage output.
PROG = "ImgScaleAndExport"

#: Distribution name as declared in ``pyproject.toml``.
DIST_NAME = "imgscaleandexport"

try:
    #: Version, single-sourced from ``pyproject.toml`` via package metadata.
    VERSION = version(DIST_NAME)
except PackageNotFoundError:  # e.g. running from an unpackaged checkout
    VERSION = "unknown"

#: Program banner string shown in version and help output, e.g. ``Image Scale and Export -- v0.2.0``.
BANNER = f"{TITLE} -- v{VERSION}"
