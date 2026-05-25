# Building the gen-ui Desktop App

Instructions for packaging `gen-ui/app.py` into a standalone binary using
[PyInstaller](https://pyinstaller.org). The resulting binary bundles Python,
PySide6/Qt, and all project modules — end users need nothing installed.

> **Important:** PyInstaller produces binaries for the platform it runs on. To
> ship for all three platforms you must run the build once on each OS.

---

## Prerequisites

Install PyInstaller into the project venv (all platforms):

```bash
.venv/bin/pip install pyinstaller
```

**Optional — UPX compression.** The spec has `upx=True`. If UPX is not
installed PyInstaller falls back to uncompressed output silently.

- macOS: `brew install upx`
- Windows: download from <https://upx.github.io> and add to `PATH`
- Linux: `apt install upx-ucl` / `dnf install upx` / `pacman -S upx`

---

## Building

Run from the **project root** on each target platform. The same spec file works
on all three:

```bash
.venv/bin/pyinstaller traveller_gen_ui.spec
```

On Windows, use the venv's `Scripts` folder:

```bat
.venv\Scripts\pyinstaller traveller_gen_ui.spec
```

---

## Output locations

| Platform | Output |
|----------|--------|
| macOS | `dist/TravellerWorldGen.app` — double-clickable app bundle |
| Windows | `dist/TravellerWorldGen/TravellerWorldGen.exe` — folder + executable |
| Linux | `dist/TravellerWorldGen/TravellerWorldGen` — folder + executable |

The `build/` directory contains intermediate files and can be deleted after
a successful build.

---

## Platform notes

### macOS

The `BUNDLE` block in the spec produces the `.app` bundle automatically.
Bundle identifier is `com.elured.traveller-world-gen`; version is taken from
the `version=` field in the spec.

**Gatekeeper / "damaged app" warning.** Binaries distributed without an Apple
Developer certificate will be quarantined. Recipients can bypass this once by
right-clicking the `.app` and choosing **Open**, or you can clear the quarantine
attribute before distributing:

```bash
xattr -cr dist/TravellerWorldGen.app
```

To properly sign and notarise (requires an Apple Developer account):

```bash
codesign --deep --force --sign "Developer ID Application: Your Name (TEAMID)" \
    dist/TravellerWorldGen.app
xcrun notarytool submit dist/TravellerWorldGen.app --wait \
    --apple-id you@example.com --team-id TEAMID --password APP_PASSWORD
xcrun stapler staple dist/TravellerWorldGen.app
```

### Windows

The `BUNDLE` block in the spec is a macOS-only step; PyInstaller ignores it on
Windows. The output is the `dist/TravellerWorldGen/` directory.

`console=False` in the spec suppresses the black terminal window. If you need
to see console output during development, set `console=True` temporarily.

**Adding an icon.** Prepare a `.ico` file and add `icon="path/to/icon.ico"` to
the `EXE(...)` block in the spec.

**Distributing.** Zip the entire `dist/TravellerWorldGen/` folder. The
executable must stay alongside its companion DLLs and the `_internal/`
subdirectory — the `.exe` alone will not run.

### Linux

The `BUNDLE` block is ignored on Linux. The output is the
`dist/TravellerWorldGen/` directory.

**PySide6 system libraries.** PySide6 bundles most Qt libraries, but some
distributions require `libxcb` platform plugins. If the app fails to start with
a missing XCB error, install:

```bash
# Debian/Ubuntu
sudo apt install libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0

# Fedora
sudo dnf install xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil
```

**Distributing.** Tar the `dist/TravellerWorldGen/` directory:

```bash
tar -czvf TravellerWorldGen-linux-x86_64.tar.gz -C dist TravellerWorldGen
```

**AppImage (optional).** For a single-file distribution, tools such as
[`appimagetool`](https://github.com/AppImage/AppImageKit) can wrap the output
directory into a portable `.AppImage`. This is not covered here; see the
AppImageKit documentation for details.

---

## Updating the spec

The spec file `traveller_gen_ui.spec` lives in the project root. Key fields:

| Field | Location | Purpose |
|-------|----------|---------|
| `datas` | `Analysis(...)` | Extra files to bundle (e.g. `templates/`) |
| `hiddenimports` | `Analysis(...)` | Modules PyInstaller misses at analysis time |
| `excludes` | `Analysis(...)` | Modules to strip (reduces size) |
| `version` | `BUNDLE(...)` | macOS bundle version string |
| `bundle_identifier` | `BUNDLE(...)` | macOS reverse-DNS bundle ID |
| `icon` | `EXE(...)` | Path to `.ico` (Windows) or `.icns` (macOS) |

If new project modules are not found at runtime, add them to `hiddenimports`.
If the `templates/` directory moves, update the `datas` list accordingly.

To regenerate the spec from scratch (e.g. after major structural changes):

```bash
.venv/bin/pyi-makespec --windowed --name TravellerWorldGen \
    --add-data "templates:templates" gen-ui/app.py
```

Then manually reapply the `excludes` list and the `BUNDLE` block from the
existing spec.
