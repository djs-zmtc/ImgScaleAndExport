import pytest
from PIL import Image

from imgscaleandexport.cli import (
    main,
    parse_filter,
    parse_percent,
    parse_quality,
    parse_size_list,
    parse_webp_quality,
)

import argparse


@pytest.fixture
def src(tmp_path):
    path = tmp_path / "Pic.png"
    Image.new("RGB", (400, 200), "blue").save(path)
    return path


def test_parse_size_list():
    assert parse_size_list("1080, 720") == [1080, 720]
    for bad in ("abc", "0", "-5", "10,,20", "1.5"):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_size_list(bad)


def test_parse_filter_and_quality():
    assert parse_filter("lanczos") == "LANCZOS"
    with pytest.raises(argparse.ArgumentTypeError):
        parse_filter("bogus")
    assert parse_quality("80") == 80
    for bad in ("x", "0", "96"):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_quality(bad)


def test_parse_percent():
    assert parse_percent("10") == 10.0
    assert parse_percent("12.5") == 12.5
    for bad in ("x", "0", "-1", "nan", "inf", "-inf"):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_percent(bad)


def test_parse_webp_quality():
    assert parse_webp_quality("80") == 80
    assert parse_webp_quality("100") == 100
    assert parse_webp_quality("1") == 1
    for bad in ("x", "0", "101", "-5"):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_webp_quality(bad)


@pytest.mark.parametrize("flag", ["-height", "--height", "-H"])
def test_height_flag_styles(src, flag, capsys):
    assert main([str(src), flag, "100"]) == 0
    assert (src.parent / "Pic_100pxH.png").exists()
    assert "wrote" in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["-width", "--width", "-W"])
def test_width_flag_styles(src, flag):
    assert main([str(src), flag, "100,50"]) == 0
    assert (src.parent / "Pic_100pxW.png").exists()
    assert (src.parent / "Pic_50pxW.png").exists()


def test_size_required_and_mutually_exclusive(src):
    with pytest.raises(SystemExit) as e:
        main([str(src)])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        main([str(src), "-height", "10", "-width", "10"])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        main([str(src), "-standard", "-height", "10"])
    assert e.value.code == 2


def test_source_required():
    with pytest.raises(SystemExit):
        main(["-height", "10"])


def test_jpg_output_filter_overwrite(src, tmp_path, capsys):
    out = tmp_path / "o"
    argv = [str(src), "-W", "100", "-jpg", "-output", str(out), "-filter", "box"]
    assert main(argv) == 0
    assert (out / "Pic_100pxW.jpg").exists()
    capsys.readouterr()
    assert main(argv) == 0  # skipped, not an error
    assert "skipped" in capsys.readouterr().err
    assert main([*argv, "-clobber"]) == 0
    assert "wrote" in capsys.readouterr().out
    assert main([*argv, "-overwrite"]) == 0


def test_error_exit_codes(tmp_path, capsys):
    assert main([str(tmp_path / "missing.png"), "-H", "10"]) == 1
    assert "error" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        main([str(tmp_path / "a.png"), "-H", "10", "-filter", "nope"])
    assert e.value.code == 2


def test_write_failure_returns_1(src, monkeypatch, capsys):
    def boom(self, *a, **k):
        raise OSError("nope")

    monkeypatch.setattr(Image.Image, "save", boom)
    assert main([str(src), "-H", "10"]) == 1
    assert "error" in capsys.readouterr().err


def test_keyboard_interrupt_returns_130(src, monkeypatch, capsys):
    def interrupt(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr("imgscaleandexport.cli.process_image", interrupt)
    assert main([str(src), "-H", "10"]) == 130
    assert "aborted by user" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["-jpg-percent", "--jpg-percent"])
def test_jpg_percent_flag_implies_jpg(src, tmp_path, flag, capsys):
    out = tmp_path / "pct_out"
    code = main([str(src), "-W", "100", flag, "50", "-output", str(out)])
    assert code == 0
    assert (out / "Pic_100pxW.jpg").exists()
    assert (out / "Pic_100pxW.png").exists()
    assert capsys.readouterr().out.count("wrote") == 2


def test_jpg_percent_and_quality_mutually_exclusive(src):
    with pytest.raises(SystemExit) as e:
        main([str(src), "-W", "100", "-jpg-quality", "85", "-jpg-percent", "10"])
    assert e.value.code == 2


@pytest.mark.parametrize("flag", ["-jpg-quality", "--jpg-quality"])
def test_jpg_quality_flag_implies_jpg(src, tmp_path, flag, capsys):
    out = tmp_path / f"jpg_q_out_{flag.strip('-')}"
    code = main([str(src), "-W", "100", flag, "85", "-output", str(out)])
    assert code == 0
    assert (out / "Pic_100pxW.jpg").exists()
    assert (out / "Pic_100pxW.png").exists()
    assert "Pic_100pxW.jpg (Q=85)" in capsys.readouterr().out


def test_cli_jpg_stdout_reports_quality(src, tmp_path, capsys):
    out = tmp_path / "q_report"
    code = main([str(src), "-W", "100", "-jpg", "-jpg-quality", "85", "-output", str(out)])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Pic_100pxW.png" in captured
    assert "Pic_100pxW.jpg (Q=85)" in captured


@pytest.mark.parametrize("flag", ["-q", "-quality", "--quality"])
def test_removed_quality_flags_rejected(src, flag):
    with pytest.raises(SystemExit) as e:
        main([str(src), "-W", "100", flag, "85"])
    assert e.value.code == 2


@pytest.mark.parametrize("flag", ["-webp", "--webp"])
def test_webp_flag(src, tmp_path, flag, capsys):
    out = tmp_path / f"webp_out_{flag.strip('-')}"
    code = main([str(src), "-W", "100", flag, "-output", str(out)])
    assert code == 0
    assert (out / "Pic_100pxW.webp").exists()
    assert (out / "Pic_100pxW.png").exists()
    assert "Pic_100pxW.webp (Q=80)" in capsys.readouterr().out


def test_webp_quality_flag_implies_webp(src, tmp_path, capsys):
    out = tmp_path / "webp_q_out"
    code = main([str(src), "-W", "100", "-webp-quality", "75", "-output", str(out)])
    assert code == 0
    assert (out / "Pic_100pxW.webp").exists()
    assert "Pic_100pxW.webp (Q=75)" in capsys.readouterr().out


def test_jpg_and_webp_together(src, tmp_path, capsys):
    out = tmp_path / "both_out"
    code = main([str(src), "-W", "100", "-jpg", "-webp", "-output", str(out)])
    assert code == 0
    assert (out / "Pic_100pxW.png").exists()
    assert (out / "Pic_100pxW.jpg").exists()
    assert (out / "Pic_100pxW.webp").exists()
    captured = capsys.readouterr().out
    assert "Pic_100pxW.jpg (Q=90)" in captured
    assert "Pic_100pxW.webp (Q=80)" in captured


@pytest.mark.parametrize("flag", ["-S", "-standard", "--standard"])
def test_standard_flag(src, tmp_path, flag, capsys):
    out = tmp_path / f"std_{flag.strip('-')}"
    code = main([str(src), flag, "-output", str(out)])
    assert code == 0
    captured = capsys.readouterr().out
    assert captured.count("wrote") == 14
    for h in (240, 360, 480, 720, 1080, 1440, 2160):
        assert (out / f"Pic_{h}pxH.png").exists()
        assert (out / f"Pic_{h}pxH.jpg").exists()


def test_standard_flag_custom_quality(src, tmp_path):
    out = tmp_path / "std_custom_q"
    code = main([str(src), "--standard", "-jpg-quality", "80", "-output", str(out)])
    assert code == 0
    assert (out / "Pic_720pxH.jpg").exists()


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_renders(flag, capsys):
    with pytest.raises(SystemExit) as e:
        main([flag])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "Usage: ImgScaleAndExport" in out
    assert "Positional Arguments:" in out
    assert "Options:" in out
    assert "target size 10% of PNG size" in out


def test_help_first_line_is_title_and_version(capsys):
    import tomllib
    from pathlib import Path

    from imgscaleandexport.meta import TITLE

    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    expected = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    with pytest.raises(SystemExit):
        main(["--help"])
    first_line = capsys.readouterr().out.splitlines()[0]
    assert first_line == f"{TITLE} -- v{expected}"


@pytest.mark.parametrize("flag", ["-v", "-version", "--version"])
def test_version_flag(flag, capsys):
    from imgscaleandexport.meta import BANNER

    with pytest.raises(SystemExit) as e:
        main([flag])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert out.strip() == BANNER


@pytest.mark.parametrize("flag", ["-v", "-version", "--version"])
def test_version_flag_with_arguments(src, flag, capsys):
    from imgscaleandexport.meta import BANNER

    with pytest.raises(SystemExit) as e:
        main([str(src), "-height", "100", flag])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert out.strip() == BANNER


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_cli_main_entry_point(src, monkeypatch):
    import runpy

    monkeypatch.setattr("sys.argv", ["ImgScaleAndExport", str(src), "-H", "50"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("imgscaleandexport.cli", run_name="__main__")
    assert exc.value.code == 0
    assert (src.parent / "Pic_50pxH.png").exists()




