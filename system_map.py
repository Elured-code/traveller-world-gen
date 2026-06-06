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
# pylint: disable=too-many-lines
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
class ColourPalette:  # pylint: disable=too-many-instance-attributes,missing-class-docstring
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

_PERSP_Y = math.sin(math.radians(15))  # 15° above orbital plane ≈ 0.259
_ROT_Z   = math.radians(30.0)          # 30° clockwise around z-axis (viewed from above)

# Stellar spectral-class colours (approximations of blackbody emission).
# Used for star glyphs, companion markers, and arc strokes.
_SPECTRAL_COLOUR: dict[str, str] = {
    "O": "#92B5FF",   # blue
    "B": "#AABFFF",   # blue-white
    "A": "#D8E3FF",   # white with blue tint
    "F": "#F8F8FF",   # near-white
    "G": "#FFE066",   # pale yellow (Sun-like)
    "K": "#FFAA44",   # orange
    "M": "#FF6644",   # red-orange
    "L": "#CC2200",   # deep red
    "T": "#884400",   # brown dwarf
    "Y": "#553300",   # cool brown dwarf
}
_WD_COLOUR = "#C8D8FF"          # white dwarf (hot, blue-white)
_STAR_FALLBACK = "#FFE066"      # fallback if spectral type unknown


def _star_colour(spectral_type: str, lum_class: str) -> str:
    """Return the display colour for a star given its spectral type and luminosity class."""
    if lum_class == "D":
        return _WD_COLOUR
    return _SPECTRAL_COLOUR.get(spectral_type.upper(), _STAR_FALLBACK)


def _star_r_px(diameter_solar: float, arc_zone_h: int) -> int:
    """Pixel radius for a star glyph, scaled logarithmically by solar diameter.

    The Sun (1.0 solar diam) maps to roughly arc_zone_h/55 px.
    Dwarfs are noticeably smaller; giants and supergiants are larger.
    """
    base = max(5, arc_zone_h // 55)
    return max(4, min(arc_zone_h // 18, int(base * max(0.01, diameter_solar) ** 0.35)))


_EHEX = "0123456789ABCDEFGHIJKLMNOPQRSTU"


def _ehex_val(c: str) -> int:
    return _EHEX.index(c.upper()) if c.upper() in _EHEX else 0


def _gg_radius_px(gg_sah: str, arc_zone_h: int = 400) -> int:
    """Pixel radius for a gas-giant glyph, scaled by GG category (S/M/L)."""
    base = max(2, arc_zone_h // 80)   # ~5px at default 400h
    category = gg_sah[1] if len(gg_sah) >= 2 else "M"
    if category == "S":
        return max(2, base // 2)
    if category == "L":
        return max(3, min(arc_zone_h // 44, int(base * 1.2)))
    return max(3, int(base * 0.8))  # M (medium, default)


def esc(s: str) -> str:
    """Escape special XML/HTML characters."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _fmt_period(period_yr: float) -> str:
    """Format an orbital period for display: hours, days, or years."""
    days = period_yr * 365.25
    if days < 1.0:
        return f"{days * 24:.1f}h"
    if days < 365.25:
        return f"{days:.1f}d"
    return f"{period_yr:.2f}y"


# ---------------------------------------------------------------------------
# Arc / marker geometry  (unified — handles eccentricity, perspective, inclination)
# ---------------------------------------------------------------------------

def _orbit_screen_pts(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    star_cx: float, cy: float, a_px: float, e: float, half_deg: float,
    persp_y: float, incl_rad: float, rot_z: float,
    shadow: bool = False, n_seg: int = 72,
) -> list[tuple[float, float]]:
    """Screen (x, y) for n_seg+1 points along an orbit arc.

    Applies inclination (tilt around x-axis), then z-rotation (CW from above),
    then orthographic projection from elevation φ = arcsin(persp_y).
    When shadow=True, the z contribution is dropped (footprint on the x-y plane).
    """
    b_px    = a_px * math.sqrt(max(0.0, 1.0 - e * e))
    cos_phi = math.sqrt(max(0.0, 1.0 - persp_y * persp_y))
    cos_rot, sin_rot = math.cos(rot_z), math.sin(rot_z)
    cos_i,   sin_i   = math.cos(incl_rad), math.sin(incl_rad)
    a_rad   = math.radians(half_deg)
    pts: list[tuple[float, float]] = []
    for k in range(n_seg + 1):
        alpha    = a_rad * (1.0 - 2.0 * k / n_seg)   # +half_deg → -half_deg
        xo, yo   = a_px * math.cos(alpha), b_px * math.sin(alpha)
        x3, y3, z3 = xo, yo * cos_i, yo * sin_i
        x4 = x3 * cos_rot + y3 * sin_rot              # CW z-rotation
        y4 = -x3 * sin_rot + y3 * cos_rot
        z_contrib = 0.0 if shadow else z3 * cos_phi
        pts.append((star_cx + x4, cy - y4 * persp_y - z_contrib))
    return pts


def _orbit_half_deg(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    a_px: float, e: float, available: float,
    persp_y: float = 1.0, incl_rad: float = 0.0, rot_z: float = 0.0,
) -> float:
    """Half-angle so the orbit arc's vertical extent fits within *available* pixels.

    The screen-y displacement is A·cos(α)+B·sin(α); maximum amplitude = √(A²+B²).
    For rot_z=0 this reduces to the previous b·|sin(φ+i)| formula.
    """
    if a_px <= 0:
        return 30.0
    b_px    = a_px * math.sqrt(max(0.0, 1.0 - e * e))
    cos_phi = math.sqrt(max(0.0, 1.0 - persp_y * persp_y))
    comp_a  = a_px * math.sin(rot_z) * persp_y
    comp_b  = b_px * (math.cos(incl_rad) * math.cos(rot_z) * persp_y
                      + math.sin(incl_rad) * cos_phi)
    ry      = math.sqrt(comp_a * comp_a + comp_b * comp_b)
    if ry <= 0:
        return 30.0
    if ry <= available:
        return 90.0
    return max(8.0, math.degrees(math.asin(min(1.0, available / ry))))


def _orbit_arc(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    star_cx: float, cy: float, a_px: float, e: float, half_deg: float,
    persp_y: float = 1.0, incl_rad: float = 0.0, rot_z: float = 0.0,
) -> str:
    """SVG path for an orbit arc with eccentricity, perspective, inclination, and z-rotation.

    When rot_z=0 uses an SVG arc command (exact).  When rot_z≠0 uses a 72-segment
    polyline computed via full 3-D rotation then orthographic projection.
    """
    if abs(rot_z) < 1e-6:
        b_px    = a_px * math.sqrt(max(0.0, 1.0 - e * e))
        cos_phi = math.sqrt(max(0.0, 1.0 - persp_y * persp_y))
        ry      = b_px * abs(persp_y * math.cos(incl_rad) + cos_phi * math.sin(incl_rad))
        a      = math.radians(half_deg)
        x1     = star_cx + a_px * math.cos(a)
        y1     = cy - ry  * math.sin(a)
        y2     = cy + ry  * math.sin(a)
        large  = 1 if half_deg > 90 else 0
        return (f"M {x1:.1f},{y1:.1f} "
                f"A {a_px:.1f},{ry:.1f} 0 {large} 1 {x1:.1f},{y2:.1f}")
    pts = _orbit_screen_pts(star_cx, cy, a_px, e, half_deg, persp_y, incl_rad, rot_z)
    return "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def _shadow_orbit_arc(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    star_cx: float, cy: float, a_px: float, e: float, half_deg: float,
    persp_y: float = 1.0, incl_rad: float = 0.0, rot_z: float = 0.0,
) -> str:
    """Shadow of an inclined orbit projected onto the reference plane (z=0).

    Uses _orbit_screen_pts with shadow=True so the z contribution is dropped.
    When rot_z=0 and incl_rad=0 this degenerates to the orbit arc itself.
    """
    if abs(rot_z) < 1e-6:
        b_px  = a_px * math.sqrt(max(0.0, 1.0 - e * e))
        ry    = b_px * abs(math.cos(incl_rad)) * persp_y
        a     = math.radians(half_deg)
        x1    = star_cx + a_px * math.cos(a)
        y1    = cy - ry * math.sin(a)
        y2    = cy + ry * math.sin(a)
        large = 1 if half_deg > 90 else 0
        return (f"M {x1:.1f},{y1:.1f} "
                f"A {a_px:.1f},{ry:.1f} 0 {large} 1 {x1:.1f},{y2:.1f}")
    pts = _orbit_screen_pts(star_cx, cy, a_px, e, half_deg, persp_y, incl_rad, rot_z,
                            shadow=True)
    return "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def _orbit_marker(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    star_cx: float, cy: float, a_px: float, e: float, half_deg: float,
    persp_y: float = 1.0, incl_rad: float = 0.0, rot_z: float = 0.0,
) -> tuple[float, float]:
    """Body-marker position: one-third of the way down the arc from the top endpoint."""
    b_px    = a_px * math.sqrt(max(0.0, 1.0 - e * e))
    cos_phi = math.sqrt(max(0.0, 1.0 - persp_y * persp_y))
    cos_rot, sin_rot = math.cos(rot_z), math.sin(rot_z)
    cos_i,   sin_i   = math.cos(incl_rad), math.sin(incl_rad)
    alpha   = math.radians(half_deg / 3)
    xo, yo  = a_px * math.cos(alpha), b_px * math.sin(alpha)
    x3, y3, z3 = xo, yo * cos_i, yo * sin_i
    x4 = x3 * cos_rot + y3 * sin_rot
    y4 = -x3 * sin_rot + y3 * cos_rot
    return (star_cx + x4, cy - y4 * persp_y - z3 * cos_phi)


def _iso_grid(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    cy: float, arc_zone_h: int, canvas_w: int,
    max_r: float, persp_y: float, palette: ColourPalette,
) -> list[str]:
    """SVG lines for an understated isometric floor grid on the orbital plane.

    Two families of parallel diagonals (slopes ±persp_y) are clipped to the
    arc zone.  The resulting diamond pattern gives a perspective floor illusion.
    """
    d = max(50, int(max_r / 8))
    t_half = arc_zone_h / (2.0 * persp_y)
    n = math.ceil((canvas_w + 2.0 * t_half) / d) + 2
    opa = "0.45" if palette.bg == PALETTE_DARK.bg else "0.32"
    result: list[str] = []
    for i in range(n):
        x0 = -t_half + i * d
        t_lo = max(-x0, -t_half)
        t_hi = min(canvas_w - x0, t_half)
        if t_hi <= t_lo + 0.5:
            continue
        gx1, gx2 = x0 + t_lo, x0 + t_hi
        result.append(
            f'<line x1="{gx1:.1f}" y1="{cy + persp_y * t_lo:.1f}" '
            f'x2="{gx2:.1f}" y2="{cy + persp_y * t_hi:.1f}" '
            f'stroke="{palette.axis}" stroke-width="0.8" opacity="{opa}"/>'
        )
        result.append(
            f'<line x1="{gx1:.1f}" y1="{cy - persp_y * t_lo:.1f}" '
            f'x2="{gx2:.1f}" y2="{cy - persp_y * t_hi:.1f}" '
            f'stroke="{palette.axis}" stroke-width="0.8" opacity="{opa}"/>'
        )
    return result


def _sphere_gradient_def(color: str) -> str:
    """SVG radialGradient giving a 3-D sphere shading effect for the given hex colour."""
    gid = f"sph_{color[1:].upper()}"
    r_c, g_c, b_c = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    light = (f"#{min(255, int(r_c + (255 - r_c) * 0.70)):02X}"
             f"{min(255, int(g_c + (255 - g_c) * 0.70)):02X}"
             f"{min(255, int(b_c + (255 - b_c) * 0.70)):02X}")
    dark  = (f"#{max(0, int(r_c * 0.45)):02X}"
             f"{max(0, int(g_c * 0.45)):02X}"
             f"{max(0, int(b_c * 0.45)):02X}")
    return (
        f'<radialGradient id="{gid}" cx="35%" cy="30%" r="65%" fx="35%" fy="30%">'
        f'<stop offset="0%" stop-color="{light}"/>'
        f'<stop offset="50%" stop-color="{color}"/>'
        f'<stop offset="100%" stop-color="{dark}"/>'
        f'</radialGradient>'
    )


def _sph(color: str) -> str:
    """SVG fill referencing the sphere gradient for ``color``."""
    return f"url(#sph_{color[1:].upper()})"


def _gg_ring_px(
    detail: object, sphere_r: float
) -> tuple[float, float] | None:
    """Return (inner_px, outer_px) ring radii if the body has ring moons, else None."""
    if detail is None:
        return None
    moons = getattr(detail, "moons", None) or []
    ring_moons = [m for m in moons if getattr(m, "is_ring", False)]
    if not ring_moons:
        return None
    m   = ring_moons[0]
    rcp = getattr(m, "ring_centre_pd", None)
    rsp = getattr(m, "ring_span_pd", None)
    if rcp is not None and rsp is not None:
        center_px = rcp * 2.0 * sphere_r
        half_span = max(rsp * sphere_r, 0.15 * sphere_r)
        return (max(sphere_r * 1.05, center_px - half_span),
                max(sphere_r * 1.30, center_px + half_span))
    return (sphere_r * 1.35, sphere_r * 2.10)


def _ring_halves(
    mx: float, my: float, rx_in: float, rx_out: float, persp_y: float
) -> tuple[str, str]:
    """SVG path strings for a perspective-foreshortened ring annulus.

    Returns (rear_half, front_half): draw rear_half before the sphere and
    front_half after so the sphere appears embedded in the ring plane.
    """
    ry_in  = rx_in  * persp_y
    ry_out = rx_out * persp_y
    rear = (
        f"M {mx - rx_out:.1f},{my:.1f} "
        f"A {rx_out:.1f},{ry_out:.1f} 0 0,0 {mx + rx_out:.1f},{my:.1f} "
        f"L {mx + rx_in:.1f},{my:.1f} "
        f"A {rx_in:.1f},{ry_in:.1f} 0 0,1 {mx - rx_in:.1f},{my:.1f} Z"
    )
    front = (
        f"M {mx - rx_out:.1f},{my:.1f} "
        f"A {rx_out:.1f},{ry_out:.1f} 0 0,1 {mx + rx_out:.1f},{my:.1f} "
        f"L {mx + rx_in:.1f},{my:.1f} "
        f"A {rx_in:.1f},{ry_in:.1f} 0 0,0 {mx - rx_in:.1f},{my:.1f} Z"
    )
    return rear, front


def _belt_band_path(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    cx: float, cy: float,
    r_in: float, r_out: float,
    hd_arc: float, persp_y: float,
    ir: float, rot_z: float,
) -> str:
    """SVG path for a filled annular band between r_in and r_out.

    Both edges use e=0 (circular belt boundaries), share inclination and z-rotation,
    so the filled region is a correct perspective projection of a flat disc.
    Forward along the outer edge then backward along the inner edge closes the band.
    """
    pts_out = _orbit_screen_pts(cx, cy, r_out, 0.0, hd_arc, persp_y, ir, rot_z)
    pts_in  = _orbit_screen_pts(cx, cy, r_in,  0.0, hd_arc, persp_y, ir, rot_z)
    parts = [f"M {pts_out[0][0]:.1f},{pts_out[0][1]:.1f}"]
    for x, y in pts_out[1:]:
        parts.append(f"L {x:.1f},{y:.1f}")
    for x, y in reversed(pts_in):
        parts.append(f"L {x:.1f},{y:.1f}")
    parts.append("Z")
    return " ".join(parts)


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
_ANOM_SFXS = {
    "random":          "*",
    "eccentric":       "~",
    "inclined":        "/",
    "retrograde":      "R",
    "trojan_leading":  "L4",
    "trojan_trailing": "L5",
}

# Table zone — fixed pixel geometry (independent of canvas width)
_TBL_HDR_OFF  = 17   # header text baseline, offset from sep_y
_TBL_ULN_OFF  = 22   # header underline y, offset from sep_y
_TBL_COL_HDR_OFF = 32  # column label baseline, offset from sep_y
_TBL_COL_ULN_OFF = 37  # column label underline y, offset from sep_y
_TBL_ROW0_OFF = 50   # first data row baseline, offset from sep_y
_TBL_ROW_H    = 17   # row pitch
_TBL_BOT_PAD  = 10   # space below last row
_TBL_FONT_LG  = 11   # primary text size
_TBL_FONT_SM  = 9    # secondary text size
_TBL_COL_PAD  = 12   # left padding inside each column

# Column proportions (fraction of usable column width).
# Columns scale with canvas / star-count so the table always fills the space.
_COL_FRACS = (0.000, 0.030, 0.105, 0.220, 0.305, 0.490, 0.725, 0.890)
_COL_NAMES = ("#", "Orbit#", "AU", "Type", "Profile", "Codes", "Zone  ♦", "Period")


def build_svg(  # pylint: disable=too-many-locals,too-many-statements,too-many-branches,too-many-nested-blocks
    system: Any,
    canvas_w: int = 1600,
    palette: ColourPalette = PALETTE_DARK,
    perspective: bool = False,
) -> tuple[str, int]:
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

    # Geometry constants (arc zone is 1.5:1 width:height; available is constant across zones)
    arc_zone_h = canvas_w * 2 // 3
    cx         = int(canvas_w * 0.045)
    arc_margin = max(14, int(arc_zone_h * 0.08))
    available  = arc_zone_h // 2 - arc_margin   # fixed arc half-height in pixels
    # star_r_px is now computed per-star inside the arc zone loop (_star_r_px)

    # Table zone metrics — primary column includes companion rows
    pri_desig = next(s.designation for s in all_stars if s.orbit_number == 0)
    pri_rows  = len(star_groups[pri_desig]) + len(sec_stars)
    max_rows  = max(pri_rows, max((len(g) for g in star_groups.values()), default=0))
    sep_y     = len(active_stars) * arc_zone_h + 1
    tbl_h      = _TBL_ROW0_OFF + max_rows * _TBL_ROW_H + _TBL_BOT_PAD
    canvas_h   = sep_y + tbl_h
    n_tbl_cols = len(star_desigs)
    col_w      = canvas_w // n_tbl_cols

    persp_y   = _PERSP_Y if perspective else 1.0
    rot_z     = _ROT_Z   if perspective else 0.0
    tick_half = 4 * persp_y

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
    s.append(
        f'<rect x="0" y="0" width="{canvas_w}" height="{canvas_h}" fill="{palette.bg}"/>'
    )
    sph_cols = (
        {palette.gg, palette.inh, palette.uninh}
        | {_star_colour(ss.spectral_type, ss.lum_class) for ss in all_stars}
    )
    grad_defs_str = "".join(_sphere_gradient_def(c) for c in sph_cols)
    s.append(
        '<defs>'
        '<filter id="shadow_blur" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur stdDeviation="3"/>'
        '</filter>'
        + grad_defs_str
        + '</defs>'
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
        target_r  = int(canvas_w * 0.75) - cx
        log_scale = max(30.0, min(canvas_w * 0.75, target_r / math.log1p(max_au)))
        max_r     = math.log1p(max_au) * log_scale

        # Build items for this arc zone
        items: list[dict] = []
        for o in group:
            r     = math.log1p(o.orbit_au) * log_scale
            o_e   = o.eccentricity
            o_i   = math.radians(o.inclination) if perspective else 0.0
            hd    = _orbit_half_deg(r, o_e, available, persp_y, o_i, rot_z)
            mx, my = _orbit_marker(cx, cy, r, o_e, hd, persp_y, o_i, rot_z)
            items.append({
                "kind": "orbit", "obj": o, "r": r, "e": o_e, "i_rad": o_i,
                "mx": mx, "my": my, "idx": orbit_idx[id(o)], "half_deg": hd,
            })
        if is_pri:
            for st in sec_stars:
                r     = math.log1p(st.orbit_au) * log_scale
                st_e  = getattr(st, "orbit_eccentricity", 0.0)
                st_i  = math.radians(getattr(st, "orbit_inclination", 0.0)) if perspective else 0.0
                hd    = _orbit_half_deg(r, st_e, available, persp_y, st_i, rot_z)
                mx, my = _orbit_marker(cx, cy, r, st_e, hd, persp_y, st_i, rot_z)
                items.append({"kind": "star", "obj": st, "r": r, "e": st_e, "i_rad": st_i,
                               "mx": mx, "my": my, "half_deg": hd})
        items.sort(key=lambda x: x["r"])

        # ── Per-zone clip rect (used to contain orbit arcs in perspective) ──────
        clip_id = f"zone_clip_{zi}"
        s.append(
            f'<clipPath id="{clip_id}">'
            f'<rect x="0" y="{y_top}" width="{canvas_w}" height="{arc_zone_h}"/>'
            f'</clipPath>'
        )

        # ── Iso grid (perspective mode) ───────────────────────────────────────
        if perspective:
            s.extend(_iso_grid(cy, arc_zone_h, canvas_w, max_r, persp_y, palette))

        # ── Orbit arcs ────────────────────────────────────────────────────────
        for item in items:
            r  = item["r"]
            hd = item["half_deg"]
            e  = item["e"]
            ir = item["i_rad"]
            if item["kind"] == "star":
                comp_col  = _star_colour(item["obj"].spectral_type,
                                         item["obj"].lum_class)
                comp_clip = f'clip-path="url(#{clip_id})"' if perspective else ""
                if perspective and abs(ir) > 1e-6:
                    shp = _shadow_orbit_arc(cx, cy, r, e, 180.0, persp_y, ir, rot_z)
                    s.append(
                        f'<path d="{shp}" fill="none" stroke="{palette.axis}" '
                        f'stroke-width="1.4" opacity="0.45" filter="url(#shadow_blur)"'
                        f' {comp_clip}/>'
                    )
                if perspective:
                    c_pts = _orbit_screen_pts(cx, cy, r, e, 180.0, persp_y, ir, rot_z)
                    c_mid = len(c_pts) // 2
                    c_near = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in c_pts[:c_mid + 1])
                    c_far  = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in c_pts[c_mid:])
                    s.append(
                        f'<path d="{c_far}" fill="none" stroke="{comp_col}" stroke-width="1.2"'
                        f' stroke-dasharray="8,6" opacity="0.16" {comp_clip}/>'
                    )
                    s.append(
                        f'<path d="{c_near}" fill="none" stroke="{comp_col}" stroke-width="1.2"'
                        f' stroke-dasharray="8,6" opacity="0.40" {comp_clip}/>'
                    )
                else:
                    s.append(
                        f'<path d="{_orbit_arc(cx, cy, r, e, hd, persp_y, ir, rot_z)}"'
                        f' fill="none" stroke="{comp_col}" stroke-width="1.2"'
                        f' stroke-dasharray="8,6" opacity="0.40" {comp_clip}/>'
                    )
                continue
            o         = item["obj"]
            wt        = o.world_type
            is_mw     = o.is_mainworld_candidate
            clip_attr = f'clip-path="url(#{clip_id})"' if perspective else ""
            # Belt with physical data → filled perspective band; skip stroke arc
            if wt == "belt":
                belt_phys = getattr(getattr(o, "detail", None), "physical", None)
                if belt_phys is not None and hasattr(belt_phys, "inner_au"):
                    r_in  = max(3.0, math.log1p(belt_phys.inner_au) * log_scale)
                    r_out = math.log1p(belt_phys.outer_au) * log_scale
                    if r_out > r_in:
                        band_d = _belt_band_path(
                            cx, cy, r_in, r_out,
                            180.0 if perspective else hd,
                            persp_y, ir, rot_z,
                        )
                        s.append(
                            f'<path d="{band_d}" fill="{palette.belt}"'
                            f' opacity="0.55" {clip_attr}/>'
                        )
                        continue
            arc_sw = "1.8"
            if wt == "empty":
                stroke, dash, opa = palette.axis, "none", "0.30"
            elif wt == "belt":
                stroke, dash, opa = palette.belt, "none", "0.55"
                arc_sw = f"{max(3.0, arc_zone_h * 0.015):.1f}"
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
            if perspective and abs(ir) > 1e-6 and wt not in ("empty", "belt"):
                shp = _shadow_orbit_arc(cx, cy, r, e, 180.0, persp_y, ir, rot_z)
                s.append(
                    f'<path d="{shp}" fill="none" stroke="{palette.axis}" '
                    f'stroke-width="1.4" opacity="0.45" filter="url(#shadow_blur)"'
                    f' {clip_attr}/>'
                )
                # ── Angle symbols at orbit/shadow crossings (α=0 and α=π) ──────
                cos_r  = math.cos(rot_z)
                sin_r  = math.sin(rot_z)
                cos_ph = math.sqrt(max(0.0, 1.0 - persp_y * persp_y))
                b_l    = r * math.sqrt(max(0.0, 1.0 - e * e))
                # shared tangent magnitudes (same at both crossings, opposite sign)
                otx = b_l * math.cos(ir) * sin_r
                oty = -b_l * (math.cos(ir) * cos_r * persp_y + math.sin(ir) * cos_ph)
                stx = otx
                sty = -b_l * math.cos(ir) * cos_r * persp_y
                ot_l = math.sqrt(otx * otx + oty * oty)
                st_l = math.sqrt(stx * stx + sty * sty)
                if ot_l > 1e-6 and st_l > 1e-6:
                    otnx, otny = otx / ot_l, oty / ot_l
                    stnx, stny = stx / st_l, sty / st_l
                    if otnx * stnx + otny * stny < 0.998:
                        ang_r  = 6.0
                        sweep  = 1 if stnx * otny - stny * otnx > 0 else 0
                        # α=0 crossing: right side (cx + r·cos_r, cy + r·sin_r·persp_y)
                        cx0 = cx + r * cos_r
                        cy0 = cy + r * sin_r * persp_y
                        s.append(
                            f'<path d="M {cx0 + stnx*ang_r:.1f},{cy0 + stny*ang_r:.1f}'
                            f' A {ang_r},{ang_r} 0 0 {sweep}'
                            f' {cx0 + otnx*ang_r:.1f},{cy0 + otny*ang_r:.1f}"'
                            f' fill="none" stroke="{palette.axis}"'
                            f' stroke-width="0.9" opacity="0.65"/>'
                        )
                        # α=π crossing: left side — tangents are negated, symbol inward
                        cx1 = cx - r * cos_r
                        cy1 = cy - r * sin_r * persp_y
                        if 0 <= cx1 <= canvas_w and y_top <= cy1 <= y_top + arc_zone_h:
                            s.append(
                                f'<path d="M {cx1 - stnx*ang_r:.1f},{cy1 - stny*ang_r:.1f}'
                                f' A {ang_r},{ang_r} 0 0 {sweep}'
                                f' {cx1 - otnx*ang_r:.1f},{cy1 - otny*ang_r:.1f}"'
                                f' fill="none" stroke="{palette.axis}"'
                                f' stroke-width="0.9" opacity="0.65"/>'
                            )
            if perspective:
                a_pts  = _orbit_screen_pts(cx, cy, r, e, 180.0, persp_y, ir, rot_z)
                mid_ix = len(a_pts) // 2
                near_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in a_pts[:mid_ix + 1])
                far_d  = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in a_pts[mid_ix:])
                far_opa = f"{max(0.08, float(opa) * 0.40):.2f}"
                s.append(
                    f'<path d="{far_d}" fill="none" stroke="{stroke}"'
                    f' stroke-width="{arc_sw}" {da} opacity="{far_opa}" {clip_attr}/>'
                )
                s.append(
                    f'<path d="{near_d}" fill="none" stroke="{stroke}"'
                    f' stroke-width="{arc_sw}" {da} opacity="{opa}" {clip_attr}/>'
                )
            else:
                s.append(
                    f'<path d="{_orbit_arc(cx, cy, r, e, hd, persp_y, ir, rot_z)}" '
                    f'fill="none" stroke="{stroke}" stroke-width="{arc_sw}" {da} '
                    f'opacity="{opa}" {clip_attr}/>'
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
                f'<line x1="{tx:.1f}" y1="{cy - tick_half:.1f}" '
                f'x2="{tx:.1f}" y2="{cy + tick_half:.1f}" '
                f'stroke="{palette.axis}" stroke-width="1" opacity="0.7"/>'
            )
            s.append(
                f'<text x="{tx:.1f}" y="{cy + tick_half + 9:.1f}" text-anchor="middle" '
                f'font-size="8" fill="{palette.dim}" opacity="0.65">{au_tick:g} AU</text>'
            )

        # ── Central star glyph + label (left of glyph) ───────────────────────
        star_color = _star_colour(star.spectral_type, star.lum_class)
        star_r     = _star_r_px(star.diameter, arc_zone_h)
        cls_str    = (f'{star.spectral_type}'
                      f'{star.subtype if star.subtype is not None else ""} {star.lum_class}')
        star_label = f'Star {star.designation}  {cls_str}'
        s.append(
            f'<circle cx="{cx}" cy="{cy}" r="{star_r}" '
            f'fill="{_sph(star_color)}"/>'
        )
        s.append(
            f'<text x="{cx - star_r - 4}" y="{cy + 4}" '
            f'text-anchor="end" font-size="9" fill="{star_color}" opacity="0.85">'
            f'{esc(star_label)}</text>'
        )

        # ── Markers + labels ──────────────────────────────────────────────────
        for item in items:
            mx, my = item["mx"], item["my"]
            kind   = item["kind"]

            if kind == "star":
                st     = item["obj"]
                st_col = _star_colour(st.spectral_type, st.lum_class)
                st_r   = _star_r_px(st.diameter, arc_zone_h)
                smy_c  = my  # z=0 shadow y; updated in perspective block below
                # Shadow on orbital plane (perspective mode) — flattened ellipse
                if perspective:
                    r_cs   = item["r"]
                    e_cs   = item["e"]
                    ir_cs  = item["i_rad"]
                    hd_cs  = item["half_deg"]
                    b_cs   = r_cs * math.sqrt(max(0.0, 1.0 - e_cs * e_cs))
                    cos_rm = math.cos(rot_z)
                    sin_rm = math.sin(rot_z)
                    cos_im = math.cos(ir_cs)
                    alp_m  = math.radians(hd_cs / 3)
                    xo_m   = r_cs * math.cos(alp_m)
                    yo_m   = b_cs * math.sin(alp_m)
                    x4_m   = xo_m * cos_rm + yo_m * cos_im * sin_rm
                    y4_m   = -xo_m * sin_rm + yo_m * cos_im * cos_rm
                    smx_c  = cx + x4_m
                    smy_c  = cy - y4_m * persp_y
                    ry_sh  = max(1.0, st_r * persp_y)
                    s.append(
                        f'<ellipse cx="{smx_c:.1f}" cy="{smy_c:.1f}" '
                        f'rx="{st_r}" ry="{ry_sh:.1f}"'
                        f' fill="{palette.axis}" opacity="0.28"'
                        f' filter="url(#shadow_blur)"/>'
                    )
                # Drop line from sphere edge to orbital plane
                if perspective and abs(smy_c - my) > st_r + 1.0:
                    dl_sy = my + math.copysign(st_r, smy_c - my)
                    s.append(
                        f'<line x1="{mx:.1f}" y1="{dl_sy:.1f}"'
                        f' x2="{mx:.1f}" y2="{smy_c:.1f}"'
                        f' stroke="{palette.axis}" stroke-width="0.8"'
                        f' stroke-dasharray="2,3" opacity="0.55"/>'
                    )
                # Companion star glyph — same circle logic as the primary star
                s.append(
                    f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{st_r}" '
                    f'fill="{_sph(st_col)}"/>'
                )
                s.append(
                    f'<text x="{mx:.1f}" y="{my - st_r - 4:.1f}" text-anchor="middle" '
                    f'font-size="8" fill="{st_col}" opacity="0.85">'
                    f'{esc(st.designation)}</text>'
                )
                continue

            o      = item["obj"]
            wt     = o.world_type
            is_mw  = o.is_mainworld_candidate
            detail = getattr(o, "detail", None)
            idx    = item["idx"]
            ic     = palette.mainworld if is_mw else palette.dim

            # ── World shadow (perspective mode only) ──────────────────────────
            _smy_z0 = my  # z=0 projected y; updated below for inclined perspective orbits
            if perspective and wt in ("gas_giant", "terrestrial"):
                r_it   = item["r"]
                e_it   = item["e"]
                ir_it  = item["i_rad"]
                hd_it  = item["half_deg"]
                b_sh   = r_it * math.sqrt(max(0.0, 1.0 - e_it * e_it))
                cos_rm = math.cos(rot_z)
                sin_rm = math.sin(rot_z)
                alp_m  = math.radians(hd_it / 3)
                xo_m   = r_it * math.cos(alp_m)
                yo_m   = b_sh  * math.sin(alp_m)
                cos_im = math.cos(ir_it)
                x4_m   = xo_m * cos_rm + yo_m * cos_im * sin_rm
                y4_m   = -xo_m * sin_rm + yo_m * cos_im * cos_rm
                smx    = cx + x4_m
                smy    = cy - y4_m * persp_y
                _smy_z0 = smy
                if wt == "gas_giant":
                    sr = _gg_radius_px(getattr(o, "gg_sah", ""), arc_zone_h)
                else:
                    sr = max(2, int(arc_zone_h * 0.0055))
                ry_sh = max(1.0, sr * persp_y)
                s.append(
                    f'<ellipse cx="{smx:.1f}" cy="{smy:.1f}" rx="{sr}" ry="{ry_sh:.1f}"'
                    f' fill="{palette.axis}" opacity="0.28"'
                    f' filter="url(#shadow_blur)"/>'
                )

            if wt == "belt":
                pass  # belt body visible via filled band path in arc loop; no separate marker
            elif wt == "gas_giant":
                gg_sah  = getattr(o, "gg_sah", "")
                rr      = _gg_radius_px(gg_sah, arc_zone_h)
                ring_px = _gg_ring_px(detail, rr)
                if is_mw:
                    s.append(
                        f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{rr + 2}" '
                        f'fill="none" stroke="{palette.mainworld}" stroke-width="1.5"/>'
                    )
                if perspective and abs(_smy_z0 - my) > rr + 1.0:
                    dl_sy = my + math.copysign(rr, _smy_z0 - my)
                    s.append(
                        f'<line x1="{mx:.1f}" y1="{dl_sy:.1f}"'
                        f' x2="{mx:.1f}" y2="{_smy_z0:.1f}"'
                        f' stroke="{palette.axis}" stroke-width="0.8"'
                        f' stroke-dasharray="2,3" opacity="0.55"/>'
                    )
                if ring_px is not None:
                    r_rear, r_front = _ring_halves(mx, my, ring_px[0], ring_px[1], persp_y)
                    s.append(f'<path d="{r_rear}" fill="{palette.gg}" opacity="0.40"/>')
                s.append(
                    f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{rr}" fill="{_sph(palette.gg)}"/>'
                )
                if ring_px is not None:
                    s.append(f'<path d="{r_front}" fill="{palette.gg}" opacity="0.65"/>')
            elif wt == "terrestrial":
                inhabited = detail.inhabited if detail else False
                fill      = palette.inh if inhabited else palette.uninh
                dot_r     = max(2, int(arc_zone_h * 0.0055))
                if is_mw:
                    s.append(
                        f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{dot_r + 2}" '
                        f'fill="none" stroke="{palette.mainworld}" stroke-width="1.5"/>'
                    )
                if perspective and abs(_smy_z0 - my) > dot_r + 1.0:
                    dl_sy = my + math.copysign(dot_r, _smy_z0 - my)
                    s.append(
                        f'<line x1="{mx:.1f}" y1="{dl_sy:.1f}"'
                        f' x2="{mx:.1f}" y2="{_smy_z0:.1f}"'
                        f' stroke="{palette.axis}" stroke-width="0.8"'
                        f' stroke-dasharray="2,3" opacity="0.55"/>'
                    )
                s.append(
                    f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{dot_r}" fill="{_sph(fill)}"/>'
                )
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
            leg_y     = y_top + 14   # anchored to top of zone
            leg_row_h = 13           # compact fixed pitch
            for k, (col, txt) in enumerate(legend_items):
                s.append(
                    f'<text x="{leg_x}" y="{leg_y + k * leg_row_h}" '
                    f'font-size="9" fill="{col}" opacity="0.92">{esc(txt)}</text>'
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
    s.append('<g font-family="\'Courier New\', Courier, monospace">')
    hdr_y      = sep_y + _TBL_HDR_OFF
    uln_y      = sep_y + _TBL_ULN_OFF
    col_hdr_y  = sep_y + _TBL_COL_HDR_OFF
    col_uln_y  = sep_y + _TBL_COL_ULN_OFF
    row0_y     = sep_y + _TBL_ROW0_OFF

    for ci, d in enumerate(star_desigs):
        star  = star_by_desig[d]
        group = star_groups[d]
        bx    = ci * col_w + _TBL_COL_PAD

        # Proportional column x-positions — expand to fill the available width.
        col_usable = col_w - 2 * _TBL_COL_PAD
        (c_idx, c_orbit, c_au, c_type,
         c_prof, c_codes, c_zone, c_period) = (
            bx + int(col_usable * f) for f in _COL_FRACS
        )

        # Vertical column separator (left edge of each non-first column)
        if ci > 0:
            sx = ci * col_w
            s.append(
                f'<line x1="{sx}" y1="{sep_y}" x2="{sx}" y2="{canvas_h}" '
                f'stroke="{palette.axis}" stroke-width="0.6" opacity="0.30"/>'
            )

        # Column header
        hdr_col = _star_colour(star.spectral_type, star.lum_class)
        cls     = (f'{star.spectral_type}'
                   f'{star.subtype if star.subtype is not None else ""}'
                   f' {star.lum_class}')
        if star.orbit_number > 0:
            period_hdr = ""
            if star.orbit_period_yr is not None:
                period_hdr = f"  {_fmt_period(star.orbit_period_yr)}"
            hdr = (f'Star {d}  {cls}  {star.mass:.2f} M☉  '
                   f'Orbit# {star.orbit_number:.2f} ({star.orbit_au:.2f} AU)'
                   f'{period_hdr}')
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

        # Column labels — positions already absolute (c_* vars)
        col_xs = (c_idx, c_orbit, c_au, c_type,
                  c_prof, c_codes, c_zone, c_period)
        for col_x, lbl in zip(col_xs, _COL_NAMES):
            s.append(
                f'<text x="{col_x}" y="{col_hdr_y}" '
                f'font-size="{_TBL_FONT_SM}" fill="{palette.dim}" opacity="0.70">'
                f'{esc(lbl)}</text>'
            )
        s.append(
            f'<line x1="{bx}" y1="{col_uln_y}" x2="{uln_x2}" y2="{col_uln_y}" '
            f'stroke="{palette.axis}" stroke-width="0.4" opacity="0.25"/>'
        )

        # Data rows — primary column merges companion star rows in orbit# order
        if star.orbit_number == 0:
            merged_rows: list[tuple[str, Any]] = (
                [("orbit", o) for o in group]
                + [("comp", st) for st in sec_stars]
            )
            merged_rows.sort(key=lambda x: x[1].orbit_number)
        else:
            merged_rows = [("orbit", o) for o in group]

        for ri, (row_kind, row_item) in enumerate(merged_rows):
            ry = row0_y + ri * _TBL_ROW_H

            if row_kind == "comp":
                st      = row_item
                comp_c  = _star_colour(st.spectral_type, st.lum_class)
                cls = (f'{st.spectral_type}'
                       f'{st.subtype if st.subtype is not None else ""} {st.lum_class}')
                s.append(
                    f'<text x="{c_idx}" y="{ry}" '
                    f'font-size="{_TBL_FONT_SM}" fill="{comp_c}">★</text>'
                )
                s.append(
                    f'<text x="{c_orbit}" y="{ry}" '
                    f'font-size="{_TBL_FONT_LG}" fill="{comp_c}">'
                    f'{st.orbit_number:.2f}</text>'
                )
                s.append(
                    f'<text x="{c_au}" y="{ry}" '
                    f'font-size="{_TBL_FONT_SM}" fill="{comp_c}" opacity="0.75">'
                    f'{st.orbit_au:.3f} AU</text>'
                )
                s.append(
                    f'<text x="{c_type}" y="{ry}" '
                    f'font-size="{_TBL_FONT_SM}" fill="{comp_c}">'
                    f'Star {esc(st.designation)}</text>'
                )
                s.append(
                    f'<text x="{c_prof}" y="{ry}" '
                    f'font-size="{_TBL_FONT_SM}" fill="{comp_c}" opacity="0.75">'
                    f'{esc(cls)}</text>'
                )
                if st.orbit_period_yr is not None:
                    s.append(
                        f'<text x="{c_period}" y="{ry}" '
                        f'font-size="{_TBL_FONT_SM}" fill="{comp_c}" opacity="0.75">'
                        f'{esc(_fmt_period(st.orbit_period_yr))}</text>'
                    )
                continue

            o      = row_item
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
            if o.anomaly_type:
                type_abbr = type_abbr + " " + _ANOM_SFXS.get(o.anomaly_type, "?")
            mw_tag    = "★MW " if is_mw else ""
            tz_col    = _TEMP_COLS.get(o.temperature_zone, palette.dim)

            s.append(
                f'<text x="{c_idx}" y="{ry}" '
                f'font-size="{_TBL_FONT_LG}" fill="{col1}">{idx}</text>'
            )
            s.append(
                f'<text x="{c_orbit}" y="{ry}" '
                f'font-size="{_TBL_FONT_LG}" fill="{palette.text}">'
                f'{o.orbit_number:.2f}</text>'
            )
            _au_txt = (
                f'{o.orbit_au:.3f} (e={o.eccentricity:.2f})'
                if o.eccentricity > 0
                else f'{o.orbit_au:.3f} AU'
            )
            s.append(
                f'<text x="{c_au}" y="{ry}" '
                f'font-size="{_TBL_FONT_SM}" fill="{palette.dim}">'
                f'{_au_txt}</text>'
            )
            s.append(
                f'<text x="{c_type}" y="{ry}" '
                f'font-size="{_TBL_FONT_SM}" fill="{palette.dim}">'
                f'{esc(mw_tag)}{type_abbr}</text>'
            )
            s.append(
                f'<text x="{c_prof}" y="{ry}" '
                f'font-size="{_TBL_FONT_LG}" fill="{col1}">'
                f'{esc(profile)}</text>'
            )
            if codes_str:
                s.append(
                    f'<text x="{c_codes}" y="{ry}" '
                    f'font-size="{_TBL_FONT_SM}" fill="{palette.dim}">'
                    f'{esc(codes_str)}</text>'
                )
            s.append(
                f'<text x="{c_zone}" y="{ry}" '
                f'font-size="{_TBL_FONT_SM}" fill="{tz_col}" opacity="0.85">'
                f'{esc(hz_tag)}{esc(o.temperature_zone)}{esc(moons_str)}</text>'
            )
            if wt != "empty" and o.orbit_period_yr is not None:
                s.append(
                    f'<text x="{c_period}" y="{ry}" '
                    f'font-size="{_TBL_FONT_SM}" fill="{palette.dim}">'
                    f'{esc(_fmt_period(o.orbit_period_yr))}</text>'
                )

    s.append('</g>')
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
    ap.add_argument("--perspective", action="store_true",
                    help="Render orbits as 60° perspective ellipses instead of top-down arcs")
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else secrets.randbelow(2**31)
    print(f"Seed: {seed}")

    system = generate_full_system(args.name, seed=seed,
                                  orbital_inclination=args.perspective)
    attach_detail(system)
    print(system.summary())

    palette = PALETTE_LIGHT if args.white_bg else PALETTE_DARK
    svg_str, canvas_h = build_svg(
        system, canvas_w=args.width, palette=palette, perspective=args.perspective
    )

    out_path = args.out or "/tmp/traveller_system_map.svg"
    save_output(svg_str, out_path)
    print(f"\nMap saved → {out_path}  (SVG, {args.width}×{canvas_h})")

    _open_file(out_path)


if __name__ == "__main__":
    main()
