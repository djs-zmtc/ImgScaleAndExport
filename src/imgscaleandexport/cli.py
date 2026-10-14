"""Command-line interface for ImgScaleAndExport."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import FILTERS, ImgScaleError, SUPPORTED_SOURCE_FORMATS, process_image


def parse_size_list(value: str) -> list[int]:
    """Parse a comma-separated list of positive integers (e.g. ``"1080,720"``).

    Raises:
        argparse.ArgumentTypeError: If any item is not a positive integer.
    """
    sizes: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item.isdigit() or int(item) < 1:
            raise argparse.ArgumentTypeError(
                f"invalid size {item!r}: sizes must be positive whole pixel values"
            )
        sizes.append(int(item))
    return sizes


def parse_filter(value: str) -> str:
    """Validate a filter name case-insensitively and return it upper-cased."""
    name = value.upper()
    if name not in FILTERS:
        raise argparse.ArgumentTypeError(
            f"invalid filter {value!r}; choose from {', '.join(FILTERS)}"
        )
    return name


def parse_quality(value: str) -> int:
    """Validate JPG quality (1-95)."""
    try:
        quality = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid quality {value!r}") from None
    if not 1 <= quality <= 95:
        raise argparse.ArgumentTypeError("quality must be between 1 and 95")
    return quality


def parse_percent(value: str) -> float:
    """Validate JPG size percentage (> 0)."""
    try:
        percent = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid percentage {value!r}") from None
    if percent <= 0:
        raise argparse.ArgumentTypeError("percentage must be greater than 0")
    return percent


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Both single-dash long flags (``-height``) and POSIX style (``--height``,
    ``-H``) are registered. Abbreviation is disabled so ``-height`` is never
    ambiguous with other flags.
    """
    formats = ", ".join(sorted(SUPPORTED_SOURCE_FORMATS))
    parser = argparse.ArgumentParser(
        prog="imgscaleandexport",
        description="Proportionally resize a lossless source image and "
        "optionally convert it to JPG.",
        allow_abbrev=False,
    )
    parser.add_argument("source", type=Path, help=f"source image ({formats})")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-H", "-height", "--height", dest="height", type=parse_size_list,
        metavar="SIZES", help="comma-separated target heights in pixels",
    )
    group.add_argument(
        "-W", "-width", "--width", dest="width", type=parse_size_list,
        metavar="SIZES", help="comma-separated target widths in pixels",
    )

    parser.add_argument(
        "-j", "-jpg", "--jpg", dest="jpg", action="store_true",
        help="also convert each resized image to JPG (white background)",
    )

    jpg_quality_group = parser.add_mutually_exclusive_group()
    jpg_quality_group.add_argument(
        "-q", "-quality", "--quality", dest="quality", type=parse_quality,
        default=None, metavar="N", help="JPG quality 1-95 (default: 90)",
    )
    jpg_quality_group.add_argument(
        "-jpg-percent", "--jpg-percent", "-jpgpercent", "--jpgpercent",
        dest="jpg_percent", type=parse_percent, default=None, metavar="PCT",
        help="target JPG file size as a percentage of PNG size (auto-selects quality 30-95; implies -jpg)",
    )

    parser.add_argument(
        "-o", "-output", "--output-dir", dest="output", type=Path, default=None,
        metavar="DIR", help="destination folder (default: source image folder)",
    )
    parser.add_argument(
        "-f", "-filter", "--filter", dest="filter", type=parse_filter,
        default=None, metavar="NAME",
        help=f"force a resampling filter ({', '.join(FILTERS)}); "
        "default: BICUBIC to upscale, LANCZOS to downscale",
    )
    parser.add_argument(
        "-overwrite", "--overwrite", "-clobber", "--clobber", dest="overwrite",
        action="store_true",
        help="overwrite existing output files (never the source image)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns:
        0 on success (including skipped existing files), 1 on any error, and
        2 for invalid arguments (via argparse).
    """
    args = build_parser().parse_args(argv)
    axis, sizes = ("H", args.height) if args.height else ("W", args.width)
    resample = FILTERS[args.filter] if args.filter else None
    to_jpg = args.jpg or (args.jpg_percent is not None)
    quality = args.quality if args.quality is not None else 90

    try:
        results = process_image(
            args.source, axis, sizes,
            output_dir=args.output, to_jpg=to_jpg, filter_override=resample,
            overwrite=args.overwrite, quality=quality,
            jpg_percent=args.jpg_percent,
        )
    except ImgScaleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    failed = False
    for res in results:
        if res.status == "written":
            detail = f" (Q={res.quality})" if res.quality is not None else ""
            print(f"wrote {res.path}{detail}")
        elif res.status == "skipped":
            print(f"warning: skipped {res.path}: {res.message}", file=sys.stderr)
        else:
            failed = True
            print(f"error: {res.path}: {res.message}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
