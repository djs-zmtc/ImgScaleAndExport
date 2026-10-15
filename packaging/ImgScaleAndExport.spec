# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for ImgScaleAndExport (single-file console EXE).
# Build with: uv run pyinstaller --noconfirm --distpath dist --workpath build packaging/ImgScaleAndExport.spec
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

# SPECPATH is provided by PyInstaller: the directory containing this spec file.
ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    # Package metadata lets imgscaleandexport.meta read the version at runtime.
    datas=copy_metadata("imgscaleandexport"),
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    # GUI toolkits Pillow can optionally use; not needed for this CLI.
    excludes=["tkinter", "PIL.ImageTk", "PIL.ImageQt"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ImgScaleAndExport",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
