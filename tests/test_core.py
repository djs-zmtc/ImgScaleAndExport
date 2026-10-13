from pathlib import Path

import pytest
from PIL import Image

from imgscaleandexport import core
from imgscaleandexport.core import (
    ImgScaleError,
    compute_target_size,
    flatten_to_rgb,
    process_image,
    select_filter,
)


@pytest.fixture
def src(tmp_path) -> Path:
    path = tmp_path / "Pic-001_700px.png"
    Image.new("RGBA", (1000, 700), (255, 0, 0, 0)).save(path)
    return path


def test_compute_target_size():
    assert compute_target_size((1000, 700), "H", 350) == (500, 350)
    assert compute_target_size((1000, 700), "W", 500) == (500, 350)
    assert compute_target_size((1000, 1), "W", 10) == (10, 1)  # min 1px


def test_select_filter_auto_and_override():
    assert select_filter(700, 1080, None) == core.UPSCALE_FILTER
    assert select_filter(700, 480, None) == core.DOWNSCALE_FILTER
    assert select_filter(700, 700, None) == core.DOWNSCALE_FILTER
    assert select_filter(700, 1080, Image.Resampling.BOX) == Image.Resampling.BOX


def test_filter_selection_used(src, monkeypatch):
    used = []
    orig = Image.Image.resize

    def spy(self, size, resample=None, *args, **kw):
        if self.mode == "RGBA" and not args:  # top-level call from core only
            used.append(resample)
        return orig(self, size, resample, *args, **kw)

    monkeypatch.setattr(Image.Image, "resize", spy)
    process_image(src, "H", [1080, 480])
    assert used == [core.UPSCALE_FILTER, core.DOWNSCALE_FILTER]


def test_resize_png_only(src):
    results = process_image(src, "H", [350])
    out = src.parent / "Pic-001_H350px.png"
    assert [r.status for r in results] == ["written"]
    with Image.open(out) as im:
        assert im.size == (500, 350)


def test_jpg_and_output_dir_flatten_white(src, tmp_path):
    dest = tmp_path / "out" / "nested"
    process_image(src, "W", [100], output_dir=dest, to_jpg=True)
    assert (dest / "Pic-001_W100px.png").exists()
    with Image.open(dest / "Pic-001_W100px.jpg") as im:
        assert im.format == "JPEG"
        r, g, b = im.getpixel((5, 5))
        assert min(r, g, b) >= 250  # transparent -> white


def test_flatten_to_rgb_mode():
    assert flatten_to_rgb(Image.new("P", (2, 2))).mode == "RGB"


def test_no_overwrite_by_default_and_overwrite_flag(src):
    process_image(src, "W", [100])
    out = src.parent / "Pic-001_W100px.png"
    out.write_bytes(b"sentinel")
    res = process_image(src, "W", [100])
    assert res[0].status == "skipped" and out.read_bytes() == b"sentinel"
    res = process_image(src, "W", [100], overwrite=True)
    assert res[0].status == "written" and out.read_bytes() != b"sentinel"


def test_never_overwrites_source(tmp_path):
    # Source name without a size suffix, same size -> output would collide
    # only if name matched; force collision via a crafted name.
    path = tmp_path / "x_W100px.png"
    Image.new("RGB", (100, 50)).save(path)
    before = path.read_bytes()
    res = process_image(path, "W", [100], overwrite=True)
    assert res[0].status == "skipped"
    assert path.read_bytes() == before


def test_missing_and_unsupported_source(tmp_path):
    with pytest.raises(ImgScaleError):
        process_image(tmp_path / "nope.png", "W", [10])
    bad = tmp_path / "a.jpg"
    bad.write_bytes(b"x")
    with pytest.raises(ImgScaleError, match="Unsupported"):
        process_image(bad, "W", [10])


def test_corrupt_png(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a png")
    with pytest.raises(ImgScaleError, match="Cannot read"):
        process_image(bad, "W", [10])


def test_write_error_reported(src, monkeypatch):
    def boom(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(Image.Image, "save", boom)
    res = process_image(src, "W", [10])
    assert res[0].status == "error" and "disk full" in res[0].message
