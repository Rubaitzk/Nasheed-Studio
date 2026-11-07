# -*- mode: python ; coding: utf-8 -*-
"""
NCN Studio — PyInstaller build specification.

Produces a one-directory (onedir) distribution that can run on any
Windows 10/11 machine without Python or FFmpeg pre-installed.

Directory layout of the built distribution (dist/NCN Studio/):
  NCN Studio.exe       — application launcher
  assets/                  — bundled images and fonts
  tools/                   — ffmpeg.exe + ffprobe.exe
  user_templates/          — shipped design templates (read-only seed)
  Qt6*.dll                 — Qt runtime
  plugins/                 — Qt platform/multimedia/style plug-ins
  ...                      — Python runtime + PySide6 wheels
"""

import sys
from pathlib import Path
import os

# ---------------------------------------------------------------------------
# Root of the SOURCE tree (where app.py lives).
# This is always the directory that contains this .spec file.
# ---------------------------------------------------------------------------
ROOT = Path(SPECPATH).resolve()          # noqa: F821  (SPECPATH is PyInstaller magic)
PYSIDE6_DIR = Path(sys.executable).parent.parent / "lib" / "site-packages" / "PySide6"

# Resolve PySide6 directory robustly for any venv layout
if not PYSIDE6_DIR.is_dir():
    import importlib.util
    spec_pyside = importlib.util.find_spec("PySide6")
    if spec_pyside and spec_pyside.submodule_search_locations:
        PYSIDE6_DIR = Path(list(spec_pyside.submodule_search_locations)[0])

PLUGINS_DIR = PYSIDE6_DIR / "plugins"

# ---------------------------------------------------------------------------
# Data files to bundle
# (source, destination-in-distribution)
# ---------------------------------------------------------------------------
datas = [
    # FFmpeg / FFprobe binaries  ← goes into tools/ inside the bundle
    (str(ROOT / "tools" / "ffmpeg.exe"),   "tools"),
    (str(ROOT / "tools" / "ffprobe.exe"),  "tools"),
    # Application assets (fonts, reference images, sample backgrounds/logos)
    (str(ROOT / "assets"),                 "assets"),
    # Shipped seed templates  (user_templates/ alongside the EXE)
    (str(ROOT / "user_templates"),         "user_templates"),
]

# Qt plug-ins that PyInstaller's hook sometimes misses -----------------------

# Platform window back-end (mandatory on Windows)
_qt_platforms = PLUGINS_DIR / "platforms"
if _qt_platforms.is_dir():
    datas.append((str(_qt_platforms), "PySide6/plugins/platforms"))

# Multimedia back-ends (needed for QMediaPlayer preview)
_qt_multimedia = PLUGINS_DIR / "multimedia"
if _qt_multimedia.is_dir():
    datas.append((str(_qt_multimedia), "PySide6/plugins/multimedia"))

# Image format decoders (JPEG, PNG, SVG, TIFF, GIF, WebP)
_qt_imageformats = PLUGINS_DIR / "imageformats"
if _qt_imageformats.is_dir():
    datas.append((str(_qt_imageformats), "PySide6/plugins/imageformats"))

# SVG icon engine (needed for QSvgRenderer used in icons.py)
_qt_iconengines = PLUGINS_DIR / "iconengines"
if _qt_iconengines.is_dir():
    datas.append((str(_qt_iconengines), "PySide6/plugins/iconengines"))

# Widget style (Windows native look)
_qt_styles = PLUGINS_DIR / "styles"
if _qt_styles.is_dir():
    datas.append((str(_qt_styles), "PySide6/plugins/styles"))

# TLS back-end (needed for any HTTPS network calls; harmless if unused)
_qt_tls = PLUGINS_DIR / "tls"
if _qt_tls.is_dir():
    datas.append((str(_qt_tls), "PySide6/plugins/tls"))

# Vector image formats (SVG cursor support)
_qt_vectorimages = PLUGINS_DIR / "vectorimageformats"
if _qt_vectorimages.is_dir():
    datas.append((str(_qt_vectorimages), "PySide6/plugins/vectorimageformats"))

# ---------------------------------------------------------------------------
# Hidden imports that PyInstaller static analysis can miss
# ---------------------------------------------------------------------------
hidden_imports = [
    # PySide6 modules used at runtime
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtWidgets",
    "PySide6.QtGui",
    "PySide6.QtCore",
    # Pillow sub-modules (PIL's import system is dynamic)
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "PIL.ImageOps",
    "PIL.ImageFilter",
    "PIL.ImageChops",
    "PIL.ImageColor",
    # Windows registry (font discovery)
    "winreg",
    # Standard library modules that can be missed in windowed mode
    "json",
    "pathlib",
    "subprocess",
    "tempfile",
    "uuid",
    "shutil",
    "io",
    "math",
    "re",
    "functools",
    "collections",
]

# ---------------------------------------------------------------------------
# PyInstaller Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim large unused Qt sub-systems to keep distribution smaller
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtDesigner",
        "PySide6.QtLocation",
        "PySide6.QtNfc",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtRemoteObjects",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngine",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        # Test / dev tooling
        "pytest",
        "IPython",
        "matplotlib",
        "notebook",
        "sphinx",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)                        # noqa: F821

exe = EXE(                               # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,               # onedir mode: binaries go into COLLECT
    name="NCN Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                           # UPX can trigger AV false positives; disabled
    console=False,                       # GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "app_icon.ico")
    if (ROOT / "assets" / "app_icon.ico").is_file()
    else None,
)

coll = COLLECT(                          # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="NCN Studio",
)
