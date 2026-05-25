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
        ("templates", "templates"),
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
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TravellerWorldGen",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TravellerWorldGen",
)

app = BUNDLE(
    coll,
    name="TravellerWorldGen.app",
    icon=None,
    bundle_identifier="com.elured.traveller-world-gen",
    version="1.3.0",
)
