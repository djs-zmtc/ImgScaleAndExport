from pathlib import Path

import pytest

from imgscaleandexport.naming import build_output_name, strip_size_suffix


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("Imagefile-001_600px", "Imagefile-001"),
        ("Imagefile-002_HD1080", "Imagefile-002"),
        ("Imagefile-Golden-200x200", "Imagefile-Golden"),
        ("Imagefile-Golden_200x200px", "Imagefile-Golden"),
        ("Imagefile-001", "Imagefile-001"),
        ("Test-Clipart-003", "Test-Clipart-003"),  # word + plain number kept
        ("Test-Photo-001_300px", "Test-Photo-001"),
        ("Test-Video-001_720p", "Test-Video-001"),
        ("Photo_2024", "Photo_2024"),
        ("plain", "plain"),
        ("_600px", "_600px"),  # would be empty -> keep original
    ],
)
def test_strip_size_suffix(stem, expected):
    assert strip_size_suffix(stem) == expected


def test_build_output_name():
    assert build_output_name(Path("a/Img-001_600px.png"), "H", 720, "jpg") == (
        "Img-001_720pxH.jpg"
    )
    assert build_output_name(Path("Img.png"), "W", 64, "png") == "Img_64pxW.png"


def test_build_output_name_bad_axis():
    with pytest.raises(ValueError):
        build_output_name(Path("a.png"), "X", 1, "png")

