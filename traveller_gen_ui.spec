# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Traveller World Generator — gen-ui desktop app.

Run from the project root:
    .venv/bin/pyinstaller traveller_gen_ui.spec

Output:
    dist/TravellerWorldGen.app   (macOS app bundle)
"""

a = Analysis(
    ["gen-ui/app.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("templates", "templates"),
    ],
    hiddenimports=[],
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
