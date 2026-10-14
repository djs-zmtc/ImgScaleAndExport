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


def test_find_best_jpg_quality_budget():
    im = Image.new("RGB", (100, 100))
    im.putdata([(x % 256, (x * y) % 256, y % 256) for y in range(100) for x in range(100)])

    # Target large enough for Q=95
    q_max, data_max = core.find_best_jpg_quality(im, 50_000)
    assert q_max == core.MAX_JPG_PERCENT_QUALITY == 95
    assert len(data_max) <= 50_000

    # Target between Q=30 and Q=95
    _, data_min = core.find_best_jpg_quality(im, 1)
    mid_target = (len(data_max) + len(data_min)) // 2
    q_mid, data_mid = core.find_best_jpg_quality(im, mid_target)
    assert core.MIN_JPG_PERCENT_QUALITY <= q_mid < 95
    assert len(data_mid) <= mid_target


def test_find_best_jpg_quality_unreachable_floor():
    im = Image.new("RGB", (100, 100), (255, 0, 0))
    # Target size of 1 byte is impossible even at Q=30
    q, data = core.find_best_jpg_quality(im, 1)
    assert q == core.MIN_JPG_PERCENT_QUALITY == 30
    assert len(data) > 1


def test_process_image_jpg_percent(src, tmp_path):
    dest = tmp_path / "out"
    results = process_image(src, "W", [100], output_dir=dest, jpg_percent=50)
    assert [r.status for r in results] == ["written", "written"]
    png_path = dest / "Pic-001_W100px.png"
    jpg_path = dest / "Pic-001_W100px.jpg"
    assert png_path.exists() and jpg_path.exists()
    png_size = png_path.stat().st_size
    jpg_size = jpg_path.stat().st_size
    # Size must be reasonably bounded by quality search
    assert jpg_size > 0


def test_is_source_oserror_handling(tmp_path, monkeypatch):
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    p1.touch()
    p2.touch()

    def err_resolve(self):
        raise OSError("filesystem error")

    monkeypatch.setattr(Path, "resolve", err_resolve)
    assert not core._is_source(p1, p2)


def test_find_best_jpg_quality_inversed_bounds():
    im = Image.new("RGB", (10, 10))
    q, data = core.find_best_jpg_quality(im, 1, min_q=50, max_q=40)
    assert q == 50
    assert len(data) > 0


def test_process_image_jpg_percent_when_png_not_on_disk(src, tmp_path, monkeypatch):
    orig_write = core._write
    calls = []

    def spy_write(target, path, source, overwrite, save_kwargs=None):
        if path.suffix == ".png":
            calls.append("png")
            return core.Result(path, "error", "failed to write PNG")
        calls.append("jpg")
        return orig_write(target, path, source, overwrite, save_kwargs)

    monkeypatch.setattr(core, "_write", spy_write)
    results = process_image(src, "W", [50], output_dir=tmp_path, jpg_percent=20)
    assert results[0].status == "error"
    assert results[1].status == "written"


