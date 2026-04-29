"""
system_map.py
=============
Draws a Traveller star system as concentric right-facing orbit arcs.

The canvas has two zones stacked vertically:

  ARC ZONES — one per star that has orbit slots, stacked vertically.  Each
              zone is canvas_w × (canvas_w // 4) and uses its own Orbit#
              scale so the star's orbits fill the available width.  The
              primary star's zone also shows companion-star orbital arcs
              (dashed) as context.  Arc sweep angle per orbit is computed
              so every arc reaches the same top and bottom y-coordinate
              within its zone.

  TABLE ZONE — one column per star in the system; each column lists the
               orbit slots around that star in orbit-number order.  The zone
               grows downward as more worlds are added, so the total canvas
               height is dynamic.

Usage (from project root):
    python system_map.py [--seed N] [--name NAME] [--out FILE] [--width W] [--white-bg]

For systems with 3+ stars, increase --width (e.g. --width 2400) so each
per-star table column has enough horizontal room.

Default: random seed, name "Unnamed", /tmp/traveller_system_map.svg, dark background
"""
from __future__ import annotations
import argparse
import math
import os
import secrets
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from traveller_system_gen import generate_full_system  # pylint: disable=wrong-import-position
from traveller_world_detail import attach_detail  # pylint: disable=wrong-import-position

# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColourPalette:
    bg: str              # background
    gg: str              # gas giant
    inh: str             # inhabited terrestrial
    uninh: str           # uninhabited terrestrial
    belt: str            # asteroid belt
    star_pri: str        # primary star
    star_sec: str        # companion / secondary star
    mainworld: str       # mainworld ring
    text: str            # label primary text
    dim: str             # label secondary text
    axis: str            # axis / tick marks
    leader: str          # leader lines

PALETTE_DARK = ColourPalette(
    bg="#0d1117",
    gg="#4A90D9",
    inh="#4CAF50",
    uninh="#5A6880",
    belt="#C87941",
    star_pri="#FFE066",
    star_sec="#FFA040",
    mainworld="#FFE066",
    text="#C9D1D9",
    dim="#9BA3AD",
    axis="#3A4560",
    leader="#2A3550",
)

PALETTE_LIGHT = ColourPalette(
    bg="#FFFFFF",
    gg="#1E88E5",
    inh="#2E7D32",
    uninh="#616161",
    belt="#D84315",
    star_pri="#FFA000",
    star_sec="#E65100",
    mainworld="#FFA000",
    text="#212121",
    dim="#757575",
    axis="#BDBDBD",
    leader="#E0E0E0",
)

_EHEX = "0123456789ABCDEFGHIJKLMNOPQRSTU"


def _ehex_val(c: str) -> int:
    return _EHEX.index(c.upper()) if c.upper() in _EHEX else 0


def _gg_radius_px(gg_sah: str) -> int:
    diam = _ehex_val(gg_sah[2]) if len(gg_sah) >= 3 else 8
    return max(4, min(12, 3 + diam // 2))


def esc(s: str) -> str:
    """Escape special XML/HTML characters."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# Arc / marker geometry
# ---------------------------------------------------------------------------

def _arc_path(cx: float, cy: float, r: float, half_deg: float) -> str:
    """
    SVG path for a symmetric arc centred on (cx, cy) with radius r.
    The arc spans ±half_deg from the horizontal, sweeping clockwise
    through the rightmost point (cx + r, cy).
    half_deg=90 → full right-facing semicircle.
    """
    a  = math.radians(half_deg)
    x1 = cx + r * math.cos(a)
    y1 = cy - r * math.sin(a)   # upper endpoint
    x2 = cx + r * math.cos(a)
    y2 = cy + r * math.sin(a)   # lower endpoint (symmetric)
    # Clockwise short arc from upper to lower through rightmost point
    large = 1 if half_deg > 90 else 0
    return (f"M {x1:.1f},{y1:.1f} "
            f"A {r:.1f},{r:.1f} 0 {large} 1 {x2:.1f},{y2:.1f}")


def _marker_xy(cx: float, cy: float, r: float, half_deg: float) -> tuple[float, float]:
    """Marker sits at the top end of the arc (upper endpoint)."""
    a = math.radians(half_deg)
    return (cx + r * math.cos(a), cy - r * math.sin(a))


def _orbit_half_deg(r: float, available: float) -> float:
    """Half-angle so the arc's vertical extent equals *available* pixels."""
    if r <= 0:
        return 30.0
    if r <= available:
        return 90.0
    return max(8.0, math.degrees(math.asin(available / r)))


# ---------------------------------------------------------------------------
# SVG builder
# ---------------------------------------------------------------------------

_TEMP_COLS = {
    "Temperate": "#4CAF50",
    "Cold":      "#88AAFF",
    "Frozen":    "#AADDFF",
    "Hot":       "#FFAA44",
    "Boiling":   "#FF5533",
}

_TYPE_ABBR = {
    "gas_giant":   "GG",
    "terrestrial": "terr",
    "belt":        "belt",
    "empty":       "—",
}

# Table zone — fixed pixel geometry (independent of canvas width)
_TBL_HDR_OFF  = 17   # header text baseline, offset from sep_y
_TBL_ULN_OFF  = 22   # header underline y, offset from sep_y
_TBL_ROW0_OFF = 38   # first data row baseline, offset from sep_y
_TBL_ROW_H    = 17   # row pitch
_TBL_BOT_PAD  = 10   # space below last row
_TBL_FONT_LG  = 11   # primary text size
_TBL_FONT_SM  = 9    # secondary text size
_TBL_COL_PAD  = 12   # left padding inside each column

# Column offsets within a table column (px from column left + _TBL_COL_PAD)
_C_IDX   = 0
_C_ORBIT = 16
_C_AU    = 58
_C_TYPE  = 120
_C_PROF  = 168
_C_CODES = 268
_C_ZONE  = 398


def build_svg(system: Any, canvas_w: int = 1600, palette: ColourPalette = PALETTE_DARK) -> tuple[str, int]:  # pylint: disable=too-many-locals,too-many-statements,too-many-branches
    """Build and return (svg_string, canvas_height) for the given system."""
    mw        = system.mainworld
    # Sort orbit slots: all Star-A orbits first, then B, then C, etc.
    orbs      = sorted(system.system_orbits.orbits,
                       key=lambda o: (o.star_designation, o.orbit_number))
    sec_stars = [s for s in system.stellar_system.stars if s.orbit_number > 0]

    # Group orbits by star; find stars that actually have orbit slots.
    all_stars     = system.stellar_system.stars
    star_desigs   = [s.designation for s in all_stars]
    star_by_desig = {s.designation: s for s in all_stars}
    star_groups: dict[str, list] = {d: [] for d in star_desigs}
    for o in orbs:
        star_groups[o.star_designation].append(o)
    active_stars = [s for s in all_stars if star_groups[s.designation]]

    # Geometry constants (arc zone is fixed 4:1; available is constant across zones)
    arc_zone_h = canvas_w // 4
    cx         = int(canvas_w * 0.045)
    arc_margin = max(14, int(arc_zone_h * 0.08))
    available  = arc_zone_h // 2 - arc_margin   # fixed arc half-height in pixels
    star_r_px  = max(6, int(arc_zone_h * 0.022))

    # Table zone metrics
    max_rows   = max((len(g) for g in star_groups.values()), default=0)
    sep_y      = len(active_stars) * arc_zone_h + 1
    tbl_h      = _TBL_ROW0_OFF + max_rows * _TBL_ROW_H + _TBL_BOT_PAD
    canvas_h   = sep_y + tbl_h
    n_tbl_cols = len(star_desigs)
    col_w      = canvas_w // n_tbl_cols

    # Global sequential indices for orbit slots (A orbits first, then B, etc.)
    orbit_idx: dict[int, int] = {}
    for i, o in enumerate(orbs):
        orbit_idx[id(o)] = i + 1

    # System title — rendered once in the first arc zone
    n_stars   = len(system.stellar_system.stars)
    mw_uwp    = mw.uwp() if mw else "—"
    mw_name   = mw.name  if mw else "—"
    age       = (f'{system.stellar_system.age_gyr:.2f} Gyr'
                 if system.stellar_system.age_gyr else '?')
    sys_title = (f'{mw_name}  system   UWP {mw_uwp}   '
                 f'{n_stars}-star   age {age}')

    s: list[str] = []
    s.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{canvas_w}" height="{canvas_h}" '
        f'style="background:{palette.bg};font-family:\'Courier New\',monospace">'
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ARC ZONES — one per active star, stacked vertically
    # ══════════════════════════════════════════════════════════════════════════
    for zi, star in enumerate(active_stars):
        y_top  = zi * arc_zone_h
        cy     = y_top + arc_zone_h // 2
        group  = star_groups[star.designation]
        is_pri = star.orbit_number == 0

        # Per-star scale: cover this star's orbits; primary also includes
        # companion-star orbital radii so their arcs fit the zone.
        au_vals  = [o.orbit_au for o in group]
        if is_pri:
            au_vals += [st.orbit_au for st in sec_stars]
        max_au   = max(au_vals + [0.1])
        target_r = (canvas_w - cx) * 0.28
        log_scale = max(30.0, min(600.0, target_r / math.log1p(max_au)))
        max_r     = math.log1p(max_au) * log_scale

        # Build items for this arc zone
        items: list[dict] = []
        for o in group:
            r      = math.log1p(o.orbit_au) * log_scale
            hd     = _orbit_half_deg(r, available)
            mx, my = _marker_xy(cx, cy, r, hd)
            items.append({
                "kind": "orbit", "obj": o, "r": r,
                "mx": mx, "my": my, "idx": orbit_idx[id(o)], "half_deg": hd,
            })
        if is_pri:
            for st in sec_stars:
                r      = math.log1p(st.orbit_au) * log_scale
                hd     = _orbit_half_deg(r, available)
                mx, my = _marker_xy(cx, cy, r, hd)
                items.append({"kind": "star", "obj": st, "r": r,
                               "mx": mx, "my": my, "half_deg": hd})
        items.sort(key=lambda x: x["r"])

        # ── Orbit arcs ────────────────────────────────────────────────────────
        for item in items:
            r  = item["r"]
            hd = item["half_deg"]
            if item["kind"] == "star":
                s.append(
                    f'<path d="{_arc_path(cx, cy, r, hd)}" fill="none" '
                    f'stroke="{palette.star_sec}" stroke-width="1.2" '
                    f'stroke-dasharray="8,6" opacity="0.40"/>'
                )
                continue
            o     = item["obj"]
            wt    = o.world_type
            is_mw = o.is_mainworld_candidate
            if wt == "empty":
                stroke, dash, opa = palette.axis, "3,9", "0.30"
            elif wt == "belt":
                stroke, dash, opa = palette.belt, "2,5", "0.55"
            elif wt == "gas_giant":
                stroke, dash, opa = palette.gg, "none", "0.60"
            else:
                detail    = getattr(o, "detail", None)
                inhabited = detail.inhabited if detail else False
                stroke    = palette.inh if inhabited else palette.uninh
                dash, opa = "none", "0.60"
            if is_mw:
                stroke, opa = palette.mainworld, "0.75"
            da = f'stroke-dasharray="{dash}"' if dash != "none" else ""
            s.append(
                f'<path d="{_arc_path(cx, cy, r, hd)}" fill="none" '
                f'stroke="{stroke}" stroke-width="1.8" {da} opacity="{opa}"/>'
            )

        # ── Axis + ticks ──────────────────────────────────────────────────────
        s.append(
            f'<line x1="{cx}" y1="{cy}" x2="{cx + max_r + 8:.1f}" y2="{cy}" '
            f'stroke="{palette.axis}" stroke-width="0.6" opacity="0.35"/>'
        )
        for au_tick in [0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0]:
            if au_tick > max_au * 1.01:
                break
            tx = cx + math.log1p(au_tick) * log_scale
            s.append(
                f'<line x1="{tx:.1f}" y1="{cy - 4}" x2="{tx:.1f}" y2="{cy + 4}" '
                f'stroke="{palette.axis}" stroke-width="1" opacity="0.7"/>'
            )
            s.append(
                f'<text x="{tx:.1f}" y="{cy + 13}" text-anchor="middle" '
                f'font-size="8" fill="{palette.dim}" opacity="0.65">{au_tick:g} AU</text>'
            )

        # ── Central star glyph + label (left of glyph) ───────────────────────
        star_color = palette.star_pri if is_pri else palette.star_sec
        cls_str    = (f'{star.spectral_type}'
                      f'{star.subtype if star.subtype is not None else ""} {star.lum_class}')
        star_label = f'Star {star.designation}  {cls_str}'
        s.append(
            f'<circle cx="{cx}" cy="{cy}" r="{star_r_px}" '
            f'fill="{star_color}" opacity="0.95"/>'
        )
        s.append(
            f'<text x="{cx - star_r_px - 4}" y="{cy + 4}" '
            f'text-anchor="end" font-size="9" fill="{star_color}" opacity="0.85">'
            f'{esc(star_label)}</text>'
        )

        # ── Markers + labels ──────────────────────────────────────────────────
        for item in items:
            mx, my = item["mx"], item["my"]
            kind   = item["kind"]

            if kind == "star":
                st = item["obj"]
                s.append(
                    f'<text x="{mx:.1f}" y="{my + 4:.1f}" text-anchor="middle" '
                    f'font-size="12" fill="{palette.star_sec}">★</text>'
                )
                s.append(
                    f'<text x="{mx:.1f}" y="{my - 9:.1f}" text-anchor="middle" '
                    f'font-size="8" fill="{palette.star_sec}" opacity="0.85">'
                    f'{esc(st.designation)}</text>'
                )
                continue

            o      = item["obj"]
            wt     = o.world_type
            is_mw  = o.is_mainworld_candidate
            detail = getattr(o, "detail", None)
            idx    = item["idx"]
            ic     = palette.mainworld if is_mw else palette.dim

            if wt == "belt":
                bw = max(10, int(arc_zone_h * 0.028))
                bh = max(3,  int(arc_zone_h * 0.009))
                s.append(
                    f'<rect x="{mx - bw//2:.1f}" y="{my - bh//2:.1f}" '
                    f'width="{bw}" height="{bh}" rx="2" fill="{palette.belt}"/>'
                )
            elif wt == "gas_giant":
                gg_sah = getattr(o, "gg_sah", "")
                rr     = _gg_radius_px(gg_sah)
                if is_mw:
                    s.append(
                        f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{rr + 4}" '
                        f'fill="none" stroke="{palette.mainworld}" stroke-width="1.8"/>'
                    )
                s.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{rr}" fill="{palette.gg}"/>')
                s.append(
                    f'<ellipse cx="{mx:.1f}" cy="{my:.1f}" rx="{rr + 3}" ry="2" '
                    f'fill="none" stroke="{palette.gg}" stroke-width="1.5" opacity="0.55"/>'
                )
            elif wt == "terrestrial":
                inhabited = detail.inhabited if detail else False
                fill      = palette.inh if inhabited else palette.uninh
                dot_r     = max(3, int(arc_zone_h * 0.011))
                if is_mw:
                    s.append(
                        f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{dot_r + 4}" '
                        f'fill="none" stroke="{palette.mainworld}" stroke-width="2"/>'
                    )
                s.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{dot_r}" fill="{fill}"/>')
            else:  # empty
                s.append(
                    f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="2" '
                    f'fill="{palette.axis}" opacity="0.55"/>'
                )
            s.append(
                f'<text x="{mx:.1f}" y="{my - 8:.1f}" text-anchor="middle" '
                f'font-size="8" fill="{ic}" opacity="0.85">{idx}</text>'
            )

        # ── Title + legend (first arc zone only) ──────────────────────────────
        if zi == 0:
            s.append(
                f'<text x="{canvas_w // 2}" y="{y_top + int(arc_zone_h * 0.10)}" '
                f'text-anchor="middle" font-size="11" '
                f'fill="{palette.text}" opacity="0.8">{esc(sys_title)}</text>'
            )
            legend_items = [
                (palette.gg,        "● GG"),
                (palette.inh,       "● inh"),
                (palette.uninh,     "● uninh"),
                (palette.belt,      "▬ belt"),
                (palette.mainworld, "◯ MW"),
                (palette.star_sec,  "★ comp"),
            ]
            leg_x     = canvas_w - 88
            leg_y     = y_top + int(arc_zone_h * 0.10)
            leg_row_h = max(11, int(arc_zone_h * 0.092))
            for k, (col, txt) in enumerate(legend_items):
                s.append(
                    f'<text x="{leg_x}" y="{leg_y + k * leg_row_h}" '
                    f'font-size="9" fill="{col}" opacity="0.75">{esc(txt)}</text>'
                )

        # ── Thin divider between arc zones (not after the last one) ──────────
        if zi < len(active_stars) - 1:
            div_y = y_top + arc_zone_h
            s.append(
                f'<line x1="0" y1="{div_y}" x2="{canvas_w}" y2="{div_y}" '
                f'stroke="{palette.axis}" stroke-width="0.5" opacity="0.25"/>'
            )

    # ══════════════════════════════════════════════════════════════════════════
    # SEPARATOR
    # ══════════════════════════════════════════════════════════════════════════
    s.append(
        f'<line x1="0" y1="{sep_y}" x2="{canvas_w}" y2="{sep_y}" '
        f'stroke="{palette.axis}" stroke-width="0.8" opacity="0.45"/>'
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TABLE ZONE — one column per star, rows grow downward
    # ══════════════════════════════════════════════════════════════════════════
    hdr_y  = sep_y + _TBL_HDR_OFF
    uln_y  = sep_y + _TBL_ULN_OFF
    row0_y = sep_y + _TBL_ROW0_OFF

    for ci, d in enumerate(star_desigs):
        star  = star_by_desig[d]
        group = star_groups[d]
        bx    = ci * col_w + _TBL_COL_PAD

        # Vertical column separator (left edge of each non-first column)
        if ci > 0:
            sx = ci * col_w
            s.append(
                f'<line x1="{sx}" y1="{sep_y}" x2="{sx}" y2="{canvas_h}" '
                f'stroke="{palette.axis}" stroke-width="0.6" opacity="0.30"/>'
            )

        # Column header
        hdr_col = palette.star_pri if star.orbit_number == 0 else palette.star_sec
        cls     = (f'{star.spectral_type}'
                   f'{star.subtype if star.subtype is not None else ""}'
                   f' {star.lum_class}')
        if star.orbit_number > 0:
            hdr = (f'Star {d}  {cls}  {star.mass:.2f} M☉  '
                   f'Orbit# {star.orbit_number:.2f} ({star.orbit_au:.2f} AU)')
        else:
            hdr = f'Star {d}  {cls}  {star.mass:.2f} M☉  primary'
        s.append(
            f'<text x="{bx}" y="{hdr_y}" '
            f'font-size="{_TBL_FONT_LG}" fill="{hdr_col}">{esc(hdr)}</text>'
        )
        uln_x2 = (ci + 1) * col_w - _TBL_COL_PAD
        s.append(
            f'<line x1="{bx}" y1="{uln_y}" x2="{uln_x2}" y2="{uln_y}" '
            f'stroke="{palette.axis}" stroke-width="0.5" opacity="0.40"/>'
        )

        # Data rows
        for ri, o in enumerate(group):
            ry     = row0_y + ri * _TBL_ROW_H
            idx    = orbit_idx[id(o)]
            is_mw  = o.is_mainworld_candidate
            detail = getattr(o, "detail", None)
            wt     = o.world_type
            col1   = palette.mainworld if is_mw else palette.text

            if o.canonical_profile:
                profile = o.canonical_profile
            elif is_mw and mw:
                profile = mw.uwp()
            elif wt == "gas_giant":
                profile = getattr(o, "gg_sah", "")
            elif detail:
                profile = getattr(detail, "profile", "")
            else:
                profile = "—"

            if is_mw and mw:
                codes_str = "  ".join(mw.trade_codes) if mw.trade_codes else ""
            elif detail and detail.inhabited:
                codes_str = f"Gov {detail.government}  Law {detail.law_level}"
            else:
                codes_str = ""

            moons_str = ""
            if detail and detail.moons:
                mc        = len(detail.moons)
                moons_str = f"  {mc}♦"

            hz_tag    = "⌾ " if o.is_habitable_zone else ""
            type_abbr = _TYPE_ABBR.get(wt, wt)
            mw_tag    = "★MW " if is_mw else ""
            tz_col    = _TEMP_COLS.get(o.temperature_zone, palette.dim)

            s.append(
                f'<text x="{bx + _C_IDX}" y="{ry}" '
                f'font-size="{_TBL_FONT_LG}" fill="{col1}">{idx}</text>'
            )
            s.append(
                f'<text x="{bx + _C_ORBIT}" y="{ry}" '
                f'font-size="{_TBL_FONT_LG}" fill="{palette.text}">'
                f'{o.orbit_number:.2f}</text>'
            )
            s.append(
                f'<text x="{bx + _C_AU}" y="{ry}" '
                f'font-size="{_TBL_FONT_SM}" fill="{palette.dim}">'
                f'{o.orbit_au:.3f} AU</text>'
            )
            s.append(
                f'<text x="{bx + _C_TYPE}" y="{ry}" '
                f'font-size="{_TBL_FONT_SM}" fill="{palette.dim}">'
                f'{esc(mw_tag)}{type_abbr}</text>'
            )
            s.append(
                f'<text x="{bx + _C_PROF}" y="{ry}" '
                f'font-size="{_TBL_FONT_LG}" fill="{col1}">'
                f'{esc(profile)}</text>'
            )
            if codes_str:
                s.append(
                    f'<text x="{bx + _C_CODES}" y="{ry}" '
                    f'font-size="{_TBL_FONT_SM}" fill="{palette.dim}">'
                    f'{esc(codes_str)}</text>'
                )
            s.append(
                f'<text x="{bx + _C_ZONE}" y="{ry}" '
                f'font-size="{_TBL_FONT_SM}" fill="{tz_col}" opacity="0.85">'
                f'{esc(hz_tag)}{esc(o.temperature_zone)}{esc(moons_str)}</text>'
            )

    s.append('</svg>')
    return "\n".join(s), canvas_h


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_output(svg_str: str, path: str) -> None:
    """Write SVG to disk."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg_str)


def _open_file(path: str) -> None:
    """Open path in the OS default viewer (fire-and-forget)."""
    for cmd in (["open", path], ["xdg-open", path]):
        try:
            subprocess.Popen(cmd)  # pylint: disable=consider-using-with
            return
        except FileNotFoundError:
            continue


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:  # pylint: disable=missing-function-docstring
    ap = argparse.ArgumentParser(description="Draw a Traveller system map")
    ap.add_argument("--seed",  type=int, default=None)
    ap.add_argument("--name",            default="Unnamed")
    ap.add_argument("--out",   default=None,
                    help="Output path (default: /tmp/traveller_system_map.svg)")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--white-bg", action="store_true",
                    help="Use light background instead of dark (default: dark)")
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else secrets.randbelow(2**31)
    print(f"Seed: {seed}")

    system = generate_full_system(args.name, seed=seed)
    attach_detail(system)
    print(system.summary())

    palette = PALETTE_LIGHT if args.white_bg else PALETTE_DARK
    svg_str, canvas_h = build_svg(system, canvas_w=args.width, palette=palette)

    out_path = args.out or "/tmp/traveller_system_map.svg"
    save_output(svg_str, out_path)
    print(f"\nMap saved → {out_path}  (SVG, {args.width}×{canvas_h})")

    _open_file(out_path)


if __name__ == "__main__":
    main()
