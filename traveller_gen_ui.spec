# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Traveller World Generator — gen-ui desktop app.

Run from the project root:
    .venv/bin/pyinstaller traveller_gen_ui.spec

Output:
    dist/TravellerWorldGen/   (one-dir bundle, all platforms)
    dist/TravellerWorldGen.app  (macOS app bundle wrapper)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

# Target architecture for macOS arch-split CI builds (arm64 / x86_64).
# Unset on all other platforms → None → native arch.
_target_arch = os.environ.get("TARGET_ARCH") or None

# Platform icon — committed to gen-ui/icons/
_icon = (
    "gen-ui/icons/icon.icns" if sys.platform == "darwin"
    else "gen-ui/icons/icon.ico" if sys.platform == "win32"
    else "gen-ui/icons/icon.png"
)

# ---------------------------------------------------------------------------
# QtWebEngine support
# ---------------------------------------------------------------------------
# When PySide6-Addons is installed separately from the base PySide6 package,
# PyInstaller's built-in hooks may not collect the WebEngine process binary
# and resource files. Collect them explicitly here.

_webengine_datas = []
for _subdir in ("Qt/resources", "Qt/translations/qtwebengine_locales"):
    _webengine_datas += collect_data_files("PySide6", subdir=_subdir)

# QtWebEngineProcess is a standalone executable required by QtWebEngine.
# On Windows: QtWebEngineProcess.exe; on Linux/macOS: QtWebEngineProcess.
import PySide6 as _pyside6
_pyside6_dir = os.path.dirname(_pyside6.__file__)
_webengine_process_name = (
    "QtWebEngineProcess.exe" if sys.platform == "win32" else "QtWebEngineProcess"
)
_webengine_process = os.path.join(_pyside6_dir, _webengine_process_name)
_webengine_binaries = [(_webengine_process, ".")] if os.path.isfile(_webengine_process) else []

# ---------------------------------------------------------------------------

a = Analysis(
    ["gen-ui/app.py"],
    pathex=["."],
    binaries=_webengine_binaries,
    datas=[
        ("src/traveller_gen/templates", "templates"),
        *_webengine_datas,
    ],
    hiddenimports=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "function_app",
        "conftest",
        "pytest",
        "pylint",
        "pyright",
        # Unused Qt modules — app only needs QtCore, QtWidgets, QtWebEngine*, QtSvgWidgets
        "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
        "PySide6.QtAxContainer", "PySide6.QtBluetooth", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtDesigner",
        "PySide6.QtHelp", "PySide6.QtLocation", "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets", "PySide6.QtNetwork", "PySide6.QtNfc",
        "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtPdf",
        "PySide6.QtPdfWidgets", "PySide6.QtPositioning", "PySide6.QtPrintSupport",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets", "PySide6.QtRemoteObjects", "PySide6.QtSensors",
        "PySide6.QtSerialBus", "PySide6.QtSerialPort", "PySide6.QtSpatialAudio",
        "PySide6.QtSql", "PySide6.QtStateMachine", "PySide6.QtTest",
        "PySide6.QtTextToSpeech", "PySide6.QtUiTools", "PySide6.QtWebChannel",
        "PySide6.QtWebSockets", "PySide6.QtXml",
    ],
    noarchive=False,
    optimize=2,
)

# Strip Qt translation files (~30–50 MB on macOS; no-op on other platforms).
a.datas = [
    (dst, src, kind)
    for dst, src, kind in a.datas
    if not dst.startswith("PySide6/Qt/translations")
    and not dst.startswith("PySide6/translations")
]

# Keep only the image format plugins the app uses; drop the rest (~10–15 MB on macOS).
a.binaries = [
    (dst, src, kind)
    for dst, src, kind in a.binaries
    if "imageformats" not in dst
    or any(p in dst for p in ("qsvg", "qjpeg", "qgif", "qicns", "qico"))
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TravellerWorldGen",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=_target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name="TravellerWorldGen",
)

app = BUNDLE(
    coll,
    name="TravellerWorldGen.app",
    icon="gen-ui/icons/icon.icns",
    bundle_identifier="com.elured.traveller-world-gen",
    version="1.5.37",
)
