"""Integration tests using the real PNG fixtures in ``tests/assets``."""

import runpy
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from imgscaleandexport.cli import main
from imgscaleandexport.core import process_image

ASSETS = Path(__file__).parent / "assets"
PHOTO = "Test-Photo-001_300px.png"  # size suffix should be stripped
CLIPART = "Test-Clipart-003.png"  # plain trailing number must be kept


@pytest.fixture(params=[PHOTO, CLIPART])
def asset(request, tmp_path) -> Path:
    """A writable copy of each asset so the originals are never touched."""
    dest = tmp_path / "in" / request.param
    dest.parent.mkdir()
    shutil.copy(ASSETS / request.param, dest)
    return dest


@pytest.fixture
def photo(tmp_path) -> Path:
    dest = tmp_path / PHOTO
    shutil.copy(ASSETS / PHOTO, dest)
    return dest


def _same_pixels(a: Path, b: Path) -> bool:
    with Image.open(a) as ia, Image.open(b) as ib:
        return ia.size == ib.size and ImageChops.difference(
            ia.convert("RGB"), ib.convert("RGB")
        ).getbbox() is None


def test_assets_exist_and_are_png():
    for name in (PHOTO, CLIPART):
        with Image.open(ASSETS / name) as im:
            assert im.format == "PNG"


def test_naming_with_real_files(tmp_path):
    for name, base in ((PHOTO, "Test-Photo-001"), (CLIPART, "Test-Clipart-003")):
        src = tmp_path / name
        shutil.copy(ASSETS / name, src)
        process_image(src, "H", [100])
        assert (tmp_path / f"{base}_H100px.png").exists()


def test_downscale_and_upscale_dimensions(asset):
    results = process_image(asset, "W", [150, 600])
    assert [r.status for r in results] == ["written", "written"]
    with Image.open(results[0].path) as small, Image.open(results[1].path) as big:
        assert small.size == (150, 150)
        assert big.size == (600, 600)


def test_height_mode_dimensions(asset):
    results = process_image(asset, "H", [75])
    with Image.open(results[0].path) as im:
        assert im.size == (75, 75)
    assert "_H75px" in results[0].path.name


def test_same_size_is_written_and_matches_source(asset):
    results = process_image(asset, "W", [300])
    assert results[0].status == "written"
    assert _same_pixels(asset, results[0].path)


def test_jpg_conversion_from_real_images(asset):
    results = process_image(asset, "W", [120], to_jpg=True, quality=80)
    assert [r.path.suffix for r in results] == [".png", ".jpg"]
    with Image.open(results[1].path) as jpg:
        assert jpg.format == "JPEG"
        assert jpg.mode == "RGB"
        assert jpg.size == (120, 120)


def test_higher_jpg_quality_gives_bigger_file(photo, tmp_path):
    low = process_image(photo, "W", [200], to_jpg=True, quality=10,
                        output_dir=tmp_path / "lo")[1].path
    high = process_image(photo, "W", [200], to_jpg=True, quality=95,
                         output_dir=tmp_path / "hi")[1].path
    assert high.stat().st_size > low.stat().st_size


def test_auto_filters_match_explicit_filters(photo, tmp_path):
    auto = process_image(photo, "W", [100, 600], output_dir=tmp_path / "auto")
    lanczos = process_image(photo, "W", [100], output_dir=tmp_path / "l",
                            filter_override=Image.Resampling.LANCZOS)
    bicubic = process_image(photo, "W", [600], output_dir=tmp_path / "b",
                            filter_override=Image.Resampling.BICUBIC)
    assert _same_pixels(auto[0].path, lanczos[0].path)  # downscale -> LANCZOS
    assert _same_pixels(auto[1].path, bicubic[0].path)  # upscale -> BICUBIC


def test_filter_override_changes_output(photo, tmp_path):
    nearest = process_image(photo, "W", [100], output_dir=tmp_path / "n",
                            filter_override=Image.Resampling.NEAREST)
    lanczos = process_image(photo, "W", [100], output_dir=tmp_path / "l")
    assert not _same_pixels(nearest[0].path, lanczos[0].path)


def test_source_left_untouched(asset):
    before = asset.read_bytes()
    process_image(asset, "W", [300, 100], to_jpg=True, overwrite=True)
    assert asset.read_bytes() == before


def test_overwrite_with_real_image(photo):
    first = process_image(photo, "W", [50])[0].path
    first.write_bytes(b"stale")
    assert process_image(photo, "W", [50])[0].status == "skipped"
    assert first.read_bytes() == b"stale"
    assert process_image(photo, "W", [50], overwrite=True)[0].status == "written"
    assert _same_pixels(first, first)  # decodes as a valid image again


def test_cli_end_to_end_with_assets(photo, tmp_path, capsys):
    out = tmp_path / "exports"
    code = main([str(photo), "-width", "200,400", "-jpg", "-o", str(out),
                 "-filter", "bilinear"])
    assert code == 0
    names = sorted(p.name for p in out.iterdir())
    assert names == [
        "Test-Photo-001_W200px.jpg", "Test-Photo-001_W200px.png",
        "Test-Photo-001_W400px.jpg", "Test-Photo-001_W400px.png",
    ]
    assert capsys.readouterr().out.count("wrote") == 4


def test_cli_rejects_non_png_asset(tmp_path, capsys):
    fake = tmp_path / "photo.jpg"
    shutil.copy(ASSETS / PHOTO, fake)  # PNG data, wrong extension
    assert main([str(fake), "-H", "50"]) == 1
    assert "Unsupported" in capsys.readouterr().err


def test_module_entry_point(photo, monkeypatch):
    monkeypatch.setattr("sys.argv", ["imgscaleandexport", str(photo), "-H", "40"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("imgscaleandexport", run_name="__main__")
    assert exc.value.code == 0
    assert (photo.parent / "Test-Photo-001_H40px.png").exists()
