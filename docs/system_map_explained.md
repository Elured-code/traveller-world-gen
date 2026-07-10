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
| Imports | `math`, `argparse`, `dataclass`, and standard library only — no drawing library |
| `ColourPalette` | Frozen dataclass holding all colour hex codes |
| `PALETTE_DARK` / `PALETTE_LIGHT` | Dark and light colour palettes |
| Geometry helpers | `_orbit_screen_pts`, `_orbit_arc`, `_shadow_orbit_arc`, `_orbit_marker`, `_orbit_half_deg` |
| Visual helpers | `_sphere_gradient_def`, `_sph`, `_gg_ring_px`, `_ring_halves`, `_belt_band_path`, `_iso_grid` |
| `_table_zone_svg()` | Renders the table-zone SVG fragments (separator + per-star columns); called by `build_svg()` unless `show_table=False` |
| SVG builder | `build_svg()` — assembles the complete SVG string |
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

### `_orbit_screen_pts(star_cx, cy, a_px, e, half_deg, persp_y, incl_rad, rot_z, shadow, n_seg)`

The core geometry function. Returns a list of `n_seg + 1` screen `(x, y)` points
along an orbit ellipse, applying three transformations in order:

1. **Inclination** — tilt around the x-axis by `incl_rad` radians
2. **Z-rotation** — rotate 30° clockwise from above (`_ROT_Z`)
3. **Orthographic projection** — viewed 15° above the orbital plane (`_PERSP_Y = sin(15°)`)

When `shadow=True`, the z-contribution is dropped, projecting the orbit onto the
flat reference plane (z = 0). This gives the shadow arc that appears beneath an
inclined orbit in perspective mode.

`n_seg = 72` gives 73 points sweeping from `+half_deg` to `−half_deg`.  When
`half_deg = 180°` the result is a closed 360° ellipse.

### `_orbit_arc(star_cx, cy, a_px, e, half_deg, persp_y, incl_rad, rot_z)`

Returns an SVG path string for an orbit arc. When `rot_z = 0` uses an exact SVG
`A` arc command (fast). When `rot_z ≠ 0` builds a 72-segment polyline via
`_orbit_screen_pts`.

In **top-down mode** (`persp_y = 1.0`) orbits are right-facing concentric arcs
limited by the arc-zone height. In **perspective mode** (`persp_y ≈ 0.259`,
`half_deg = 180°`) they are full ellipses, and the arc loop emits two separate
`<path>` elements: a **near half** (upper screen, normal opacity) and a **far
half** (lower screen, 40% of normal opacity) to give the viewer a depth cue.

### `_orbit_marker(star_cx, cy, a_px, e, half_deg, persp_y, incl_rad, rot_z)`

Returns the `(x, y)` pixel position where the world glyph is drawn — one third
of the way down the arc from the top endpoint.  The same 3-D rotation and
projection used by `_orbit_screen_pts` is applied, including the z-elevation
contribution, so the marker sits correctly on the inclined orbit.

---

## World glyph types

Every filled circle uses a **radial gradient** (`_sphere_gradient_def`) so it
looks like a lit sphere — a bright highlight in the upper-left, the base colour
in the middle, and a darkened edge. This is built once per unique colour and
stored in the SVG `<defs>` block.

| `world_type` | Shape | Colour |
|---|---|---|
| `gas_giant` | Sphere; optional foreshortened ring annulus | `palette.gg` |
| `terrestrial` (inhabited) | Sphere | `palette.inh` |
| `terrestrial` (uninhabited) | Sphere | `palette.uninh` |
| `belt` | Filled annular band (correct perspective projection) | `palette.belt` |
| `empty` | Small dot | `palette.axis` |
| Mainworld | Extra ring stroke around the glyph | `palette.mainworld` |

In perspective mode, inclined bodies also draw a **drop line** — a short dotted
line from the bottom edge of the sphere down to its shadow point on the orbital
plane, making the three-dimensional position immediately readable.

Temperature zones affect the arc **stroke colour** (see `_TEMP_COLS`), not the glyph.

---

## The public API

```python
svg_string, canvas_h = build_svg(
    system,                 # TravellerSystem
    canvas_w=1600,          # total width in pixels
    palette=PALETTE_DARK,   # ColourPalette — use PALETTE_LIGHT for white background
    perspective=False,      # True for perspective (3-D looking) view
    show_table=True,        # False omits the table zone entirely (see below)
)
```

Returns a `(svg_string, canvas_height_px)` tuple. The SVG string is a complete
document that can be written to a `.svg` file, embedded in an HTML `<body>`, or
displayed in the PySide6 GUI via `QWebEngineView.setHtml(html)`.

> **Note:** The function was renamed `build_svg` (from `build_system_map_svg`)
> when the palette and perspective parameters were added. It never actually took
> a `name` parameter — the system/mainworld name shown in the title text comes
> from `system.mainworld.name`.

### `show_table=False` — omitting the table zone

The table zone (see below) is drawn by a separate helper,
`_table_zone_svg(canvas_w, canvas_h, sep_y, star_desigs, star_by_desig,
star_groups, children_by_parent, col_w, mw, orbit_idx, palette)`, extracted out of
`build_svg()` so it can be skipped entirely. When `show_table=False`:

- The separator line and the whole per-star table (headers, orbit rows, moon
  rows) are omitted.
- `canvas_h` shrinks to just the arc-zone height (`sep_y`) instead of
  `sep_y + tbl_h` — the returned SVG is shorter, not just visually blank at the
  bottom.

`TravellerSystem.to_poster_html()` (in `traveller_system_gen.py`) is the only
caller that passes `show_table=False` — its A3 poster page shows this same
per-star orbit data on its own "Full system card" page instead, and having the
map's own copy of it competing for space with the poster's other cards looked
cluttered. Every other caller (the CLI, gen-ui's `SystemMapWindow`, the FastAPI
raw-SVG endpoints) doesn't pass this argument, so it defaults `True` and their
output is completely unaffected.

---

## Companion star context markers (fixed issue #171; nesting added Session 165)

Each active star's arc zone draws its **own direct companion(s)** as dashed
"context" arcs — a small sphere on a dashed orbital path, using the same
shadow-ellipse/drop-line treatment as world orbits, just styled differently
(dashed stroke, no world glyph). This is built from `children_by_parent`, a
dict keyed by every star's own designation mapping to its direct children:
companions (`role == "companion"`, parent = `designation[:-1]`) and, for the
primary only, close/near/far secondaries (they always orbit the primary
directly).

**Bug fixed (issue #171):** before this, a single flat `sec_stars` list
(`[s for s in stars if s.orbit_number > 0]`) was used as "the primary's
context" — but that also caught companions of *secondary* stars (e.g. "Ba",
which orbits secondary "B", not the primary "A"). Since a star's
`orbit_number`/`orbit_au` are relative to its *own* parent, "Ba" (0.318 AU
from B) was being plotted as if it were 0.318 AU from A — landing almost on
top of A's own glyph instead of near B's. `children_by_parent` fixed this by
grouping each star's context children by their actual immediate parent, and
every active star's zone/column now uses `children_by_parent[<its own
designation>]`, not just the primary's.

**Nested markers (Session 165):** a companion of a *secondary* star is drawn
twice by design — once in its own zone (correct top-level placement) and once
more, nested next to its parent's own context marker wherever that parent
itself appears as dashed context (e.g. "Ba" nested beside "B"'s marker inside
the primary's zone). Each `"star"`-kind item dict gained an optional
`"origin": (x, y)` key (both `kind == "star"` render blocks read
`item.get("origin", (cx, cy))` instead of hardcoding the zone's own centre);
nested items set `origin` to their parent item's own `(mx, my)`. The nested
item's distance uses a small local scale anchored to the parent glyph's own
pixel radius (`nest_target = max(5 × parent's glyph radius, 40)`, not the
zone-wide AU axis — a companion's own `orbit_au` is tiny next to typical
planetary AU and would be invisible on the zone's main log scale), and its
drawn *inclination* deliberately matches the **parent's own** orbit
inclination, not the nested companion's own. Nested items are appended to
`items` only after the top-level `items.sort(key=lambda x: x["r"])` call,
since a nested item's `r` lives on this unrelated smaller scale — sorting it
in with top-level items would be meaningless and could draw a child before
its own parent exists. One level of nesting only.

---

## Running directly

```bash
python system_map.py --seed 42 --name "Reega" --out /tmp/map.svg
python system_map.py --seed 42 --white-bg --width 2400
python system_map.py --seed 42 --perspective
```

`main()` generates a full system with `generate_full_system()`, runs `attach_detail()`,
calls `build_svg()`, writes the SVG file, and opens it with the default viewer.
`--perspective` also enables `orbital_inclination=True` so inclined orbits are generated.

---

## Perspective mode

Pass `perspective=True` (or `--perspective` on the CLI) to render the system in a
pseudo-3D view:

- Orbits become full 360° ellipses, rotated 30° around the z-axis and observed
  from 15° above the orbital plane.
- Inclined orbits draw a blurred **shadow arc** on the reference plane and an
  **angle symbol** at the orbit crossings.
- **Depth cues:** for orbits inclined ≥ 3°, the far half (receding behind the
  plane) is drawn at 40% opacity; the near half keeps full opacity. Orbits
  inclined less than 3° draw uniformly — the split adds no visible information
  for nearly equatorial orbits.
- **Drop lines:** bodies above or below the plane get a dotted line connecting the
  bottom of their sphere to their shadow point, making the 3-D position obvious.
- An **isometric floor grid** is drawn behind all orbits to reinforce the depth
  perspective.

---

## How this fits in the pipeline

```
TravellerSystem   (generated + detail attached)
        │
        ▼
build_svg(system, name, canvas_w, palette, perspective)
        │
        ▼
(svg_string, canvas_h)
        │
        ├── write to .svg file (standalone CLI)
        └── wrap in HTML → QWebEngineView.setHtml() (gen-ui)
```
