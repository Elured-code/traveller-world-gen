# context/system-map.md — System Map SVG Generator

**Module:** `system_map.py`  
**Routing:** Consult this file + `context/data-structures.md` for any work on `system_map.py`.

---

## Purpose

Draws a Traveller star system as a standalone SVG file. The output consists of:

- **Arc zone(s)** — one zone per star that has orbit slots, stacked vertically. Each zone is `canvas_w × (canvas_w // 4)` pixels. Orbits are drawn as right-facing concentric arcs; the primary star's zone also shows companion-star orbital arcs as dashed context arcs.
- **Table zone** — one column per star, listing orbit slots in orbit-number order with UWP, world type, period, and anomaly notes.

The script can be run standalone:

```
python system_map.py [--seed N] [--name NAME] [--out FILE] [--width W] [--white-bg]
```

It is also imported by `gen-ui/app.py` via `from system_map import build_system_map_svg`.

---

## Public API

| Name | Signature | Description |
|------|-----------|-------------|
| `build_system_map_svg` | `(system: TravellerSystem, name: str = "", canvas_w: int = 1600, white_bg: bool = False) -> str` | Returns the complete SVG string for a system. |

---

## Key internal geometry functions

### `_arc_path(cx, cy, r, half_deg) -> str`

Returns an SVG path for a symmetric arc centred on `(cx, cy)` with radius `r`.
The arc spans `±half_deg` from the horizontal, sweeping clockwise through the
rightmost point `(cx + r, cy)`. `half_deg = 90` produces a full right-facing
semicircle.

- Upper endpoint: angle `+half_deg` above horizontal (top of arc)
- Lower endpoint: angle `−half_deg` below horizontal (bottom of arc, symmetric)
- `large` flag is 1 when `half_deg > 90`

### `_marker_xy(cx, cy, r, half_deg) -> tuple[float, float]`

Returns the `(x, y)` pixel coordinate where the world glyph (circle) and its
label are placed. The marker is positioned **one third of the way down the arc
from the top endpoint**:

```python
a = math.radians(half_deg / 3)
return (cx + r * math.cos(a), cy - r * math.sin(a))
```

The full arc spans `2 × half_deg` degrees total; one third of that sweep from
the top means the marker sits at angle `half_deg / 3` above horizontal (between
the top endpoint at `half_deg` and the rightmost point at 0°).

> **History:** Prior to Session 77, the marker was placed at the top endpoint
> (`math.radians(half_deg)`). Changed to one-third-down for better visual clarity.

### `_orbit_half_deg(r, available) -> float`

Computes the half-angle so the arc's vertical extent equals `available` pixels.
Returns 90° when `r ≤ available`, otherwise `arcsin(available / r)`, clamped
to minimum 8°.

---

## Colour palettes

Two palettes are defined as frozen dataclasses:

| Constant | Background |
|----------|------------|
| `PALETTE_DARK` | `#0d1117` (GitHub-dark) |
| `PALETTE_LIGHT` | `#FFFFFF` |

Selected by `--white-bg` flag or `white_bg` parameter to `build_system_map_svg`.

---

## World glyph types

| `world_type` | Abbreviation | Glyph |
|---|---|---|
| `gas_giant` | `GG` | filled circle, radius from `gg_sah[2]` eHex size digit |
| `terrestrial` | `terr` | filled circle, fixed radius |
| `belt` | `belt` | small diamond |
| `empty` | `—` | no glyph |

The mainworld slot receives an additional outer ring in `palette.mainworld` colour.

---

## Temperature zone colours (arc stroke)

| Zone | Colour |
|------|--------|
| Temperate | `#4CAF50` |
| Cold | `#88AAFF` |
| Frozen | `#AADDFF` |
| Hot | `#FFAA44` |
| Boiling | `#FF5533` |

---

## Table zone

Fixed pixel geometry constants (all offsets relative to the arc/table separator y):

| Constant | Value | Meaning |
|----------|-------|---------|
| `_TBL_ROW0_OFF` | 50 | First data row baseline |
| `_TBL_ROW_H` | 17 | Row pitch |
| `_TBL_FONT_LG` | 11 | Primary text size (px) |
| `_TBL_FONT_SM` | 9 | Secondary text size (px) |

---

## What to read for related tasks

- Arc geometry / orbit placement → `_arc_path`, `_orbit_half_deg`, `_marker_xy` in `system_map.py`
- Orbit slot data (`OrbitSlot`, `star_zones`) → `context/data-structures.md`
- Calling `build_system_map_svg` from the GUI → `context/gen-ui.md`
