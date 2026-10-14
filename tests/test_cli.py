import pytest
from PIL import Image

from imgscaleandexport.cli import (
    main,
    parse_filter,
    parse_percent,
    parse_quality,
    parse_size_list,
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
    for bad in ("x", "0", "-1"):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_percent(bad)


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
        main([str(src), "-W", "100", "-quality", "85", "-jpg-percent", "10"])
    assert e.value.code == 2


def test_cli_jpg_stdout_reports_quality(src, tmp_path, capsys):
    out = tmp_path / "q_report"
    code = main([str(src), "-W", "100", "-jpg", "-quality", "85", "-output", str(out)])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Pic_100pxW.png" in captured
    assert "Pic_100pxW.jpg (Q=85)" in captured


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
    code = main([str(src), "--standard", "-quality", "80", "-output", str(out)])
    assert code == 0
    assert (out / "Pic_720pxH.jpg").exists()



