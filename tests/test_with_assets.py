"""Integration tests using real image fixtures in ``tests/assets``."""

import runpy
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from imgscaleandexport.cli import main
from imgscaleandexport.core import compute_target_size, process_image

ASSETS = Path(__file__).parent / "assets"
PHOTO = "Test-Photo-001_300px.png"  # size suffix should be stripped
CLIPART = "Test-Clipart-003.png"  # plain trailing number must be kept
TIFF_PHOTO = "Test-Photo_240pxh.tiff"  # suffix _240pxh should be stripped -> Test-Photo
WEBP_PHOTO = "Test_Photo_002_480px.webp"  # trailing number _002 kept, _480px stripped -> Test_Photo_002


@pytest.fixture(params=[PHOTO, CLIPART])
def asset(request, tmp_path) -> Path:
    """A writable copy of each square PNG asset so the originals are never touched."""
    dest = tmp_path / "in" / request.param
    dest.parent.mkdir()
    shutil.copy(ASSETS / request.param, dest)
    return dest


@pytest.fixture
def photo(tmp_path) -> Path:
    dest = tmp_path / PHOTO
    shutil.copy(ASSETS / PHOTO, dest)
    return dest


@pytest.fixture
def tiff_asset(tmp_path) -> Path:
    dest = tmp_path / TIFF_PHOTO
    shutil.copy(ASSETS / TIFF_PHOTO, dest)
    return dest


@pytest.fixture
def webp_asset(tmp_path) -> Path:
    dest = tmp_path / WEBP_PHOTO
    shutil.copy(ASSETS / WEBP_PHOTO, dest)
    return dest


def _same_pixels(a: Path, b: Path) -> bool:
    with Image.open(a) as ia, Image.open(b) as ib:
        return ia.size == ib.size and ImageChops.difference(
            ia.convert("RGB"), ib.convert("RGB")
        ).getbbox() is None


def test_assets_exist_and_match_formats():
    expected = {
        PHOTO: "PNG",
        CLIPART: "PNG",
        TIFF_PHOTO: "TIFF",
        WEBP_PHOTO: "WEBP",
    }
    for name, fmt in expected.items():
        with Image.open(ASSETS / name) as im:
            assert im.format == fmt


def test_naming_with_real_files(tmp_path):
    cases = (
        (PHOTO, "Test-Photo-001"),
        (CLIPART, "Test-Clipart-003"),
        (TIFF_PHOTO, "Test-Photo"),
        (WEBP_PHOTO, "Test_Photo_002"),
    )
    for name, base in cases:
        src = tmp_path / name
        shutil.copy(ASSETS / name, src)
        process_image(src, "H", [100])
        assert (tmp_path / f"{base}_100pxH.png").exists()


def test_downscale_and_upscale_dimensions(asset):
    with Image.open(asset) as orig:
        expected_small = compute_target_size(orig.size, "W", 150)
        expected_big = compute_target_size(orig.size, "W", 600)
    results = process_image(asset, "W", [150, 600])
    assert [r.status for r in results] == ["written", "written"]
    with Image.open(results[0].path) as small, Image.open(results[1].path) as big:
        assert small.size == expected_small
        assert big.size == expected_big


def test_height_mode_dimensions(asset):
    with Image.open(asset) as orig:
        expected_size = compute_target_size(orig.size, "H", 75)
    results = process_image(asset, "H", [75])
    with Image.open(results[0].path) as im:
        assert im.size == expected_size
    assert "_75pxH" in results[0].path.name


def test_same_size_is_written_and_matches_source(asset):
    with Image.open(asset) as orig:
        orig_w = orig.width
    results = process_image(asset, "W", [orig_w])
    assert results[0].status == "written"
    assert _same_pixels(asset, results[0].path)


def test_jpg_conversion_from_real_images(asset):
    with Image.open(asset) as orig:
        expected_size = compute_target_size(orig.size, "W", 120)
    results = process_image(asset, "W", [120], to_jpg=True, quality=80)
    assert [r.path.suffix for r in results] == [".png", ".jpg"]
    with Image.open(results[1].path) as jpg:
        assert jpg.format == "JPEG"
        assert jpg.mode == "RGB"
        assert jpg.size == expected_size


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
        "Test-Photo-001_200pxW.jpg", "Test-Photo-001_200pxW.png",
        "Test-Photo-001_400pxW.jpg", "Test-Photo-001_400pxW.png",
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
    assert (photo.parent / "Test-Photo-001_40pxH.png").exists()


def test_jpg_percent_with_real_asset(photo, tmp_path):
    with Image.open(photo) as orig:
        expected_size = compute_target_size(orig.size, "W", 200)
    out = tmp_path / "pct_real"
    results = process_image(photo, "W", [200], output_dir=out, jpg_percent=15)
    assert len(results) == 2
    assert [r.status for r in results] == ["written", "written"]
    png_path = out / "Test-Photo-001_200pxW.png"
    jpg_path = out / "Test-Photo-001_200pxW.jpg"
    assert png_path.exists() and jpg_path.exists()
    assert jpg_path.stat().st_size > 0
    with Image.open(jpg_path) as im:
        assert im.format == "JPEG"
        assert im.size == expected_size


def test_standard_with_real_asset(photo, tmp_path, capsys):
    out = tmp_path / "std_real"
    code = main([str(photo), "--standard", "-output", str(out)])
    assert code == 0
    assert capsys.readouterr().out.count("wrote") == 14
    for h in (240, 360, 480, 720, 1080, 1440, 2160):
        png = out / f"Test-Photo-001_{h}pxH.png"
        jpg = out / f"Test-Photo-001_{h}pxH.jpg"
        assert png.exists() and jpg.exists()


def test_clipart_transparency_handling(tmp_path):
    src = tmp_path / CLIPART
    shutil.copy(ASSETS / CLIPART, src)
    out = tmp_path / "clipart_out"
    results = process_image(src, "W", [200], output_dir=out, to_jpg=True, to_webp=True)
    assert len(results) == 3
    with Image.open(out / "Test-Clipart-003_200pxW.png") as png_im:
        assert png_im.mode == "RGBA"
    with Image.open(out / "Test-Clipart-003_200pxW.webp") as webp_im:
        assert webp_im.mode == "RGBA"
    with Image.open(out / "Test-Clipart-003_200pxW.jpg") as jpg_im:
        assert jpg_im.mode == "RGB"


def test_tiff_asset_processing(tiff_asset, tmp_path):
    with Image.open(tiff_asset) as orig:
        orig_mode = orig.mode
        expected_size = compute_target_size(orig.size, "H", 120)
    out = tmp_path / "tiff_out"
    results = process_image(tiff_asset, "H", [120], output_dir=out, to_jpg=True, to_webp=True)
    assert len(results) == 3
    assert [r.status for r in results] == ["written", "written", "written"]

    png_path = out / "Test-Photo_120pxH.png"
    jpg_path = out / "Test-Photo_120pxH.jpg"
    webp_path = out / "Test-Photo_120pxH.webp"

    with Image.open(png_path) as png_im:
        assert png_im.format == "PNG"
        assert png_im.size == expected_size
        assert png_im.mode == orig_mode

    with Image.open(jpg_path) as jpg_im:
        assert jpg_im.format == "JPEG"
        assert jpg_im.size == expected_size
        assert jpg_im.mode == "RGB"

    with Image.open(webp_path) as webp_im:
        assert webp_im.format == "WEBP"
        assert webp_im.size == expected_size
        assert webp_im.mode == orig_mode


def test_webp_asset_processing(webp_asset, tmp_path):
    with Image.open(webp_asset) as orig:
        orig_mode = orig.mode
        expected_size = compute_target_size(orig.size, "W", 400)
    out = tmp_path / "webp_out"
    results = process_image(webp_asset, "W", [400], output_dir=out, to_jpg=True, to_webp=True)
    assert len(results) == 3
    assert [r.status for r in results] == ["written", "written", "written"]

    png_path = out / "Test_Photo_002_400pxW.png"
    jpg_path = out / "Test_Photo_002_400pxW.jpg"
    webp_path = out / "Test_Photo_002_400pxW.webp"

    with Image.open(png_path) as png_im:
        assert png_im.format == "PNG"
        assert png_im.size == expected_size
        assert png_im.mode == orig_mode

    with Image.open(jpg_path) as jpg_im:
        assert jpg_im.format == "JPEG"
        assert jpg_im.size == expected_size
        assert jpg_im.mode == "RGB"

    with Image.open(webp_path) as webp_im:
        assert webp_im.format == "WEBP"
        assert webp_im.size == expected_size
        assert webp_im.mode == orig_mode


def test_cli_end_to_end_with_tiff_asset(tiff_asset, tmp_path, capsys):
    out = tmp_path / "tiff_cli"
    code = main([str(tiff_asset), "-height", "120", "-jpg", "-webp", "-o", str(out)])
    assert code == 0
    assert (out / "Test-Photo_120pxH.png").exists()
    assert (out / "Test-Photo_120pxH.jpg").exists()
    assert (out / "Test-Photo_120pxH.webp").exists()
    assert capsys.readouterr().out.count("wrote") == 3


def test_cli_end_to_end_with_webp_asset(webp_asset, tmp_path, capsys):
    out = tmp_path / "webp_cli"
    code = main([str(webp_asset), "-width", "400", "-jpg", "-webp", "-o", str(out)])
    assert code == 0
    assert (out / "Test_Photo_002_400pxW.png").exists()
    assert (out / "Test_Photo_002_400pxW.jpg").exists()
    assert (out / "Test_Photo_002_400pxW.webp").exists()
    assert capsys.readouterr().out.count("wrote") == 3



