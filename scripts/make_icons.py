#!/usr/bin/env python3
"""Generate platform icon files from fastapi/static/favicon.svg.

Requires: rsvg-convert (brew install librsvg), sips, iconutil (macOS built-in).
Run from the project root:
    python3 scripts/make_icons.py

Outputs:
    gen-ui/icons/icon.png    — 256×256 PNG (Linux)
    gen-ui/icons/icon.ico    — multi-res ICO 16/32/48/256 (Windows)
    gen-ui/icons/icon.icns   — multi-res ICNS (macOS)
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SVG    = os.path.join(_ROOT, "fastapi", "static", "favicon.svg")
_OUTDIR = os.path.join(_ROOT, "gen-ui", "icons")

_ICO_SIZES  = [16, 32, 48, 256]
_ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]

# ICNS OSType codes for each size
_ICNS_TYPES = {
    16:   b"icp4",
    32:   b"icp5",
    64:   b"icp6",
    128:  b"ic07",
    256:  b"ic08",
    512:  b"ic09",
    1024: b"ic10",
}


def _check(cmd: str) -> None:
    if not shutil.which(cmd):
        sys.exit(f"ERROR: '{cmd}' not found. Install librsvg (brew install librsvg).")


def _rsvg(src: str, dst: str, size: int) -> None:
    subprocess.run(
        ["rsvg-convert", "-w", str(size), "-h", str(size), src, "-o", dst],
        check=True,
    )


def _read_png(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _build_ico(png_map: dict) -> bytes:
    """Assemble a Windows ICO from a {size: png_bytes} dict."""
    sizes = sorted(png_map)
    count = len(sizes)
    header = struct.pack("<HHH", 0, 1, count)
    dir_size = count * 16
    data_offset = 6 + dir_size
    entries = b""
    images  = b""
    for s in sizes:
        png = png_map[s]
        w = h = s if s < 256 else 0   # 256 is encoded as 0 in ICO directory
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(png), data_offset + len(images))
        images  += png
    return header + entries + images


def _build_icns(png_map: dict) -> bytes:
    """Assemble a macOS ICNS from a {size: png_bytes} dict."""
    body = b""
    for size, png in sorted(png_map.items()):
        ostype = _ICNS_TYPES.get(size)
        if ostype is None:
            continue
        chunk_len = 8 + len(png)
        body += ostype + struct.pack(">I", chunk_len) + png
    total = 8 + len(body)
    return b"icns" + struct.pack(">I", total) + body


def main() -> None:
    _check("rsvg-convert")
    os.makedirs(_OUTDIR, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        # Render all required sizes
        all_sizes = sorted(set(_ICO_SIZES) | set(_ICNS_SIZES))
        png_paths: dict[int, str] = {}
        for s in all_sizes:
            dst = os.path.join(tmp, f"icon_{s}.png")
            print(f"  rendering {s}×{s}…")
            _rsvg(_SVG, dst, s)
            png_paths[s] = dst

        # Linux PNG — 256×256
        linux_png = os.path.join(_OUTDIR, "icon.png")
        shutil.copy(png_paths[256], linux_png)
        print(f"wrote {linux_png}")

        # Windows ICO
        ico_data = _build_ico({s: _read_png(png_paths[s]) for s in _ICO_SIZES})
        ico_path = os.path.join(_OUTDIR, "icon.ico")
        with open(ico_path, "wb") as f:
            f.write(ico_data)
        print(f"wrote {ico_path}")

        # macOS ICNS
        icns_data = _build_icns({s: _read_png(png_paths[s]) for s in _ICNS_SIZES})
        icns_path = os.path.join(_OUTDIR, "icon.icns")
        with open(icns_path, "wb") as f:
            f.write(icns_data)
        print(f"wrote {icns_path}")

    print("Done.")


if __name__ == "__main__":
    main()
