import importlib
import importlib.metadata

from imgscaleandexport import meta


def test_meta_attributes():
    assert meta.TITLE == "Image Scale and Export"
    assert meta.PROG == "ImgScaleAndExport"
    assert meta.DIST_NAME == "imgscaleandexport"
    assert meta.VERSION != "unknown"
    assert meta.BANNER == f"{meta.TITLE} -- v{meta.VERSION}"


def test_meta_package_not_found(monkeypatch):
    def mock_version(name):
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", mock_version)
    reloaded = importlib.reload(meta)
    try:
        assert reloaded.VERSION == "unknown"
        assert reloaded.BANNER == f"{reloaded.TITLE} -- vunknown"
    finally:
        monkeypatch.undo()
        importlib.reload(meta)
