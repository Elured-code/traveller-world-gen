# Understanding `system_map.py`

A guide for Python beginners. This file draws a star system as an SVG diagram —
concentric orbital arcs with world glyphs and an orbit table below.

---

## What this file does

Given a `TravellerSystem`, this file produces a complete SVG (Scalable Vector
Graphics) image. SVG is an XML-based format that web browsers and image viewers
can display and scale without losing quality.

The diagram has two zones stacked vertically:

- **Arc zone** — one zone per star that has orbiting worlds. Each orbit is an arc
  sweeping right from the star. Worlds appear as coloured dots or diamond shapes
  at a point along their arc.
- **Table zone** — a column per star listing each orbit slot with its world type,
  period, and any anomaly notation.

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | `math`, `argparse`, `dataclass`, `svg` generation helpers |
| `ColourPalette` | Frozen dataclass holding all colour hex codes |
| `PALETTE_DARK` / `PALETTE_LIGHT` | Dark and light colour palettes |
| Arc/marker helpers | `_arc_path()`, `_marker_xy()`, `_orbit_half_deg()` |
| SVG builder | `build_system_map_svg()` — assembles the complete SVG string |
| `main()` | Command-line entry point |

---

## Key Python concept: SVG as a string

SVG is just text that describes shapes. The file builds it by concatenating strings:

```python
svg_lines = []
svg_lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{colour}"/>')
svg = "\n".join(svg_lines)
```

No external drawing library is used — the file constructs the SVG syntax directly.
`f"..."` strings (f-strings) insert variable values into the text using `{...}`.
The `:.1f` format code rounds floats to one decimal place.

---

## Key Python concept: frozen dataclasses

```python
@dataclass(frozen=True)
class ColourPalette:
    bg: str      # background colour hex
    gg: str      # gas giant glyph colour
    inh: str     # inhabited terrestrial colour
    ...
```

`frozen=True` makes the dataclass **immutable** after construction — you cannot
change its fields. The two palette constants `PALETTE_DARK` and `PALETTE_LIGHT` are
created once at module load and never modified. This is a common pattern for
configuration objects.

---

## Arc geometry

### `_arc_path(cx, cy, r, half_deg)`

Returns an SVG path for a symmetric arc centred on `(cx, cy)` with radius `r`.
`half_deg` is the angle above (and below) horizontal:

- `half_deg = 30` → a short arc that spans 60° total
- `half_deg = 90` → a full right-facing semicircle

The arc always sweeps **clockwise** through the rightmost point `(cx + r, cy)`.

```python
a  = math.radians(half_deg)
x1 = cx + r * math.cos(a)    # upper endpoint
y1 = cy - r * math.sin(a)
x2 = cx + r * math.cos(a)    # lower endpoint (same x, opposite y)
y2 = cy + r * math.sin(a)
```

`math.cos` and `math.sin` take angles in **radians** (not degrees). `math.radians()`
converts degrees to radians. One full circle is 2π radians ≈ 6.28.

### `_marker_xy(cx, cy, r, half_deg)`

Returns the `(x, y)` position where the world glyph is drawn. The marker sits
**one third of the way down the arc** from the top endpoint:

```python
a = math.radians(half_deg / 3)
return (cx + r * math.cos(a), cy - r * math.sin(a))
```

This places the glyph between the top of the arc and the rightmost horizontal
point, which gives better visual separation between worlds on different orbits.

---

## World glyph types

| `world_type` | Shape | Colour |
|---|---|---|
| `gas_giant` | Filled circle (radius from `gg_sah` size digit) | `palette.gg` |
| `terrestrial` (inhabited) | Filled circle | `palette.inh` |
| `terrestrial` (uninhabited) | Filled circle | `palette.uninh` |
| `belt` | Small diamond | `palette.belt` |
| Mainworld | Extra ring around the glyph | `palette.mainworld` |

Temperature zones affect the arc **stroke colour** (see `_TEMP_COLS`), not the glyph.

---

## The public API

```python
svg_string = build_system_map_svg(
    system,          # TravellerSystem
    name="Regina",   # displayed in the title bar
    canvas_w=1600,   # total width in pixels
    white_bg=False,  # True for white background (print-friendly)
)
```

Returns a complete SVG string that can be written to a `.svg` file, embedded in HTML,
or displayed by the PySide6 GUI.

---

## Running directly

```bash
python system_map.py --seed 42 --name "Reega" --out /tmp/map.svg
python system_map.py --seed 42 --white-bg --width 2400
```

`main()` generates a full system with `generate_full_system()`, runs `attach_detail()`,
calls `build_system_map_svg()`, writes the SVG file, and opens it with the default
viewer.

---

## How this fits in the pipeline

```
TravellerSystem   (already generated and detail-attached)
        │
        ▼
build_system_map_svg(system, name, canvas_w, white_bg)
        │
        ▼
SVG string  →  written to file or displayed in GUI
```
