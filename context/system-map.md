# context/system-map.md — System Map SVG Generator

**Module:** `system_map.py`  
**Routing:** Consult this file + `context/data-structures.md` for any work on `system_map.py`.

---

## Purpose

Draws a Traveller star system as a standalone SVG file. The output consists of:

- **Arc zone(s)** — one zone per star that has orbit slots, has its own direct companion star(s), has `"Protostar"` in `special_notes`, or has `lum_class in ("NS", "PSR")` — stacked vertically. This ensures protostar, neutron star, and pulsar primaries always get an arc zone even when they have no orbit slots. Each zone is `canvas_w × (canvas_w * 2/3)` pixels. In top-down mode orbits are right-facing concentric arcs; in perspective mode (`--perspective`) they are full 360° ellipses (half_deg=180°) using a 72-segment polyline, rotated 30° CW around z (`_ROT_Z`), observed 15° above the orbital plane (`_PERSP_Y = sin(15°)`). Inclined orbits additionally draw a blurred shadow ellipse onto the reference plane. Each star's own zone also shows *that star's* own direct companion star(s) as dashed context arcs — e.g. a companion of secondary star B (such as "Ba") is drawn in B's zone, not the primary's (fixed issue #171; previously every non-primary star with `orbit_number > 0` was lumped into the primary's context list regardless of its actual parent).
- **Table zone** — one column per star, listing orbit slots in orbit-number order with UWP, world type, period, and anomaly notes.

The script can be run standalone:

```
# Procedural generation
python system_map.py [--seed N] [--name NAME] [--out FILE] [--width W] [--white-bg] [--perspective]

# TravellerMap fetch (canonical world/belt/GG counts honoured)
python system_map.py --sector "Spinward Marches" --name Regina [--seed N] [--out FILE] [--width W] [--white-bg] [--perspective]
python system_map.py --sector "Spinward Marches" --hex 1910   [--seed N] [--out FILE] [--width W] [--white-bg] [--perspective]
```

`--sector` triggers TravellerMap mode: canonical UWP/stellar data is fetched and
`generate_system_from_map()` is called so the map reflects the canonical PBG
world/belt/gas-giant counts rather than a fresh procedural roll.

It is also imported by `gen-ui/app.py` via `from system_map import build_svg`.
The gen-ui calls `build_svg(self._current_system, ...)` directly with the
already-reconciled system object, so it correctly reflects TravellerMap counts.

---

## Public API

| Name | Signature | Description |
|------|-----------|-------------|
| `build_system_map_svg` | `(system: TravellerSystem, name: str = "", canvas_w: int = 1600, white_bg: bool = False) -> str` | Returns the complete SVG string for a system. |

---

## Key internal geometry functions

### `_orbit_arc(star_cx, cy, a_px, e, half_deg, persp_y, incl_rad) -> str`

Returns an SVG path for a right-facing orbit arc **centred on the star at
`(star_cx, cy)`**. The arc spans `±half_deg` from the horizontal, sweeping
clockwise through the rightmost point.

- `a_px` — semi-major axis in pixels (x-radius of the SVG arc)
- `e` — eccentricity; compresses the y-radius via `b_px = a_px * sqrt(1 − e²)`,
  giving the arc an elliptical aspect for eccentric orbits
- `persp_y` — 1.0 top-down, `sin(15°) ≈ 0.259` for 15° above orbital plane perspective
- `incl_rad` — inclination in radians; all four geometry functions now use the full
  orthographic projection formula `ry = b · |sin(φ + i)|`, expanded as
  `b · |persp_y·cos(i) + cos_φ·sin(i)|` where `cos_φ = √(1 − persp_y²)`.
  This makes inclined orbits visually rise above the reference plane (the arc grows
  taller as inclination increases toward face-on) rather than just flattening.
  Top-down mode (persp_y=1) reduces correctly to `b·|cos(i)|`.
- `large` flag is 1 when `half_deg > 90`

> **Session 108:** Prior to Session 108 the inclination formula was
> `ry = b·persp_y·|cos(i)|` — depth foreshortening only, orbits just flattened.
> Replaced with `ry = b·|sin(φ+i)|` so inclined orbits correctly project above
> the reference plane.
>
> **Session 104:** Prior to Session 104 the arc used the ellipse focus
> (`star_cx + a_px * e`) as its centre, and used bare `cos()` for inclination —
> retrograde orbits (incl > 90°) produced negative `ry` and drew with a wildly
> wrong centre.

### `_orbit_screen_pts(star_cx, cy, a_px, e, half_deg, persp_y, incl_rad, rot_z, shadow, n_seg) -> list[tuple[float, float]]`

Generates `n_seg+1` screen-space (x, y) points for an orbit or shadow ellipse.
Applies inclination (tilt around x-axis), CW z-rotation, then orthographic
projection. `shadow=True` drops the z-contribution from screen_y, projecting
onto the orbital reference plane (z=0).

- Points sweep from `+half_deg` to `−half_deg` (so 180° → full closed ellipse).
- Used by `_orbit_arc` and `_shadow_orbit_arc` when `rot_z ≠ 0`.

### `_shadow_orbit_arc(star_cx, cy, a_px, e, half_deg, persp_y, incl_rad, rot_z) -> str`

Returns the SVG path for a shadow of an inclined orbit projected onto z=0.
Calls `_orbit_screen_pts` with `shadow=True`. When `rot_z=0` uses the fast SVG
arc path: `ry_shadow = b_px · cos(i) · persp_y`. In perspective mode called
with `half_deg=180°` (full ellipse) and a per-zone `clip-path`.

> **Session 108:** Added to draw blurred shadow ellipses for inclined orbits in
> perspective mode.

---

### `_orbit_marker(star_cx, cy, a_px, e, half_deg, persp_y, incl_rad, rot_z) -> tuple[float, float]`

Returns the `(x, y)` pixel coordinate where the world glyph and label are
placed. The marker is positioned **one third of the way down the arc from the
top endpoint**, using the same full 3-D rotation and projection as
`_orbit_screen_pts`. The z contribution (`z3 * cos_phi`) is included so the
marker sits on the orbit rather than on the reference plane.

The z=0 shadow position for the same marker angle is `(star_cx + x4, cy − y4·persp_y)`
— identical x, shadow y only. This is computed inline in the world-shadow block and
used as the drop-line endpoint.

> **History:** Prior to Session 77, the marker was placed at the top endpoint.
> Changed to one-third-down for better visual clarity.

### `_iso_grid(cy, arc_zone_h, canvas_w, max_r, persp_y, palette) -> list[str]`

Returns a list of SVG `<line>` elements for an understated isometric floor grid.
Two families of parallel diagonal lines (slopes ±`persp_y`) are analytically
clipped to the arc zone rectangle. Each pair of families creates diamond shapes:
width `d` px, height `persp_y × d` px, giving a foreshortened floor-tile illusion.

- `d` (grid spacing) = `max(50, int(max_r / 8))` pixels, so spacing scales with the orbital extent
- `opacity` is 0.45 for dark palette, 0.32 for light palette
- Only called when `perspective=True`; no-op in top-down mode

> **Session 105:** Added to give the perspective view a depth cue via an
> understated isometric floor grid. Lines use `palette.axis` and draw before
> orbit arcs so they sit behind all content.
> **Session 109:** Dark-mode opacity raised 0.22 → 0.45 for visibility.

---

### `_protostar_halo_def(color) -> str` · `_prh(color) -> str` (Session 198)

Wide diffuse radialGradient (4-stop, opacity 0.55→0.30→0.10→0.00) for the protostellar
envelope. Halo circle drawn at `star_r × 4` before the solid sphere. Protostar zone
uses AU floor of 5.0 (not 0.1).

### `_nebula_cloud_def() -> str` · `_nebula_cloud_svg(cx, cy, arc_zone_h) -> str` (Session 200)

Fixed radialGradient (`id="nebula_cloud"`) in H-alpha magenta/pink (`#C040A0 → #D06080`).
Three rotated overlapping ellipses (0°/60°/120°), each `arc_zone_h × 0.17` rx by
`arc_zone_h × 0.12` ry — drawn before the solid sphere. Visually distinct from the
protostar halo (irregular multi-lobe shape; cool pink vs warm star colour). Nebula zone
also uses 5.0 AU floor. `_NEBULA_GLYPH_R = 5` minimum pixel radius for the embedded star.
`active_stars` filter extended to include `"Nebula" in special_notes`.

### `_ns_corona_def(color) -> str` · `_nsc(color) -> str` (Session 198)

Tight hot-corona radialGradient (4-stop, opacity 0.90→0.60→0.20→0.00) for NS and PSR
glyphs. Corona circle drawn at `star_r × 3` before the solid sphere.

`_NS_COLOUR = "#88AAFF"` — returned by `_star_colour()` for `lum_class in ("NS", "PSR")`.
`_NS_GLYPH_R = 5` — minimum pixel radius enforced before drawing NS/PSR glyphs.

PSR additionally draws a horizontal beam `<line>` at `star_r × 8` (`stroke-linecap="round"`,
opacity 0.55) after the solid sphere. Both primary and companion NS/PSR stars get the same
treatment in their respective render blocks.

### `_sphere_gradient_def(color) -> str` · `_sph(color) -> str`

`_sphere_gradient_def` returns an SVG `<radialGradient>` element that simulates
3-D sphere shading for `color` (hex string): a lightened highlight at cx=35%
cy=30%, the base colour at 50%, a darkened edge (×0.45) at 100%.  The gradient
`id` is `sph_<UPPER-HEX>`.

`_sph(color)` returns `url(#sph_<UPPER-HEX>)` — the fill reference to use in
place of a flat hex colour.

Star glyphs use `_sph(star_color)`. Gradient `<defs>` are emitted once at the
top of the SVG from all star spectral-class colours. World glyphs no longer use
this gradient — they use the archetype system below.

> **Session 111:** Added; replaced all flat `fill=color` on circles.

---

### World archetype textures

Terrestrial and gas-giant world icons use a procedural texture system instead of
flat palette colours.

#### `_world_archetype(detail, temperature_zone) -> str`

Classifies a terrestrial world into one of 8 archetypes based on SAH codes and
temperature zone. When `detail` is `None` falls back to temperature zone only.

| Archetype | Primary trigger |
|-----------|----------------|
| `garden`  | atm 4–9, hydro ≥ 4, temperate/hot |
| `ocean`   | hydro ≥ 9 |
| `desert`  | atm 2–10, hydro ≤ 2 |
| `barren`  | atm 0–1 |
| `ice`     | frozen temp, or cold + hydro ≥ 7 |
| `tundra`  | cold temp, hydro 1–6 |
| `volcanic`| boiling temp, or atm B/C (corrosive/insidious) |
| `hostile` | atm D/E/F (exotic variants) |

#### `_archetype_gradient_defs() -> str` · `_archetype_fill(archetype) -> str`

`_archetype_gradient_defs()` returns all 8 SVG `<radialGradient>` elements
(ids `terr_garden`, `terr_ocean`, …) as one string. Each has 4 stops:
highlight → mid-light → midtone → shadow, with `cx=35% cy=30%` (same focal
point as the star sphere gradients).

`_archetype_fill(archetype)` returns `url(#terr_{archetype})`.

#### `_gg_density_g_cm3(gg_sah, gg_mass_earth) -> float | None` · `_gg_is_ice_giant(gg_sah, gg_mass_earth) -> bool`

`_gg_density_g_cm3` computes density in g/cm³ from the SAH diameter digit and
`gg_mass_earth` (Earth masses). Returns `None` when mass is unavailable.
Formula: `(mass_M⊕ / (diam_terran × 12800/12742)³) × 5.515`.

`_gg_is_ice_giant` returns `True` when the GG category is `S` (small) **and**
computed density exceeds 1.0 g/cm³. When mass is `None` returns `False`
(defaults to regular GS stripe).

#### `_gg_stripe_pattern_defs() -> str`

Returns four SVG `<pattern>` elements for gas giant horizontal cloud bands.
Each tile is `400 × 24px` with four 6px-tall coloured rows:

| Pattern id | Trigger | Palette |
|------------|---------|---------|
| `gg_stripe_S` | GS, density ≤ 1 g/cm³ | Blue/white (hydrogen gas giant) |
| `gg_stripe_M` | GM | Tan/beige (Saturn-like) |
| `gg_stripe_L` | GL | Orange/amber (Jupiter-like) |
| `gg_stripe_ice` | GS, density > 1 g/cm³ | Blue-green/teal (Uranus/Neptune-like) |

#### `_SPH_OVERLAY_DEF` (module constant)

Single reusable `<radialGradient id="sph_overlay">` applied as a second
transparent circle on top of gas-giant stripe fills to restore the lit-sphere
depth cue: white highlight (opacity 0.55) → transparent → black rim (opacity 0.50).

> **Session 143:** Added archetype texture system. All four items above are
> emitted in the `<defs>` block of every generated SVG.

---

### `_gg_ring_px(detail, sphere_r) -> tuple[float, float] | None`

Returns `(inner_px, outer_px)` ring radii for a gas giant that has at least one
`Moon.is_ring=True` satellite, else `None`. Reads `ring_centre_pd`
(centre in planetary diameters from body centre) and `ring_span_pd` (full span in
PD) to size the ring; `center_px = rcp × 2 × sphere_r`. Falls back to
`(sphere_r × 1.35, sphere_r × 2.10)` when the PD fields are `None`.

> **Session 111:** Added.

---

### `_ring_halves(mx, my, rx_in, rx_out, persp_y) -> tuple[str, str]`

Returns `(rear_path, front_path)` SVG annulus path strings for a perspective-
foreshortened ring system. `ry = rx × persp_y` for both inner and outer edges.

Render order: draw `rear_path` **before** the sphere (rear half of ring hidden by
sphere), draw sphere, draw `front_path` **after** (front half of ring on top).
`rear` opacity 0.40, `front` opacity 0.65.

> **Session 111:** Added.

---

### `_belt_band_path(cx, cy, r_in, r_out, hd_arc, persp_y, ir, rot_z) -> str`

Returns an SVG path for a filled annular band between `r_in` and `r_out` (both
circular, `e=0`). Calls `_orbit_screen_pts` for outer and inner edges, traces
outer edge forward then inner edge reversed, closes with `Z`. This is the correct
perspective projection of a flat disc on the orbital plane.

`r_in = max(3.0, log1p(inner_au) × log_scale)` (floor prevents degenerate zero
path). In top-down mode (`hd_arc < 180°`) the band is a symmetric annular arc.

When no `BeltPhysical` data is attached the fallback is a thin stroke arc.
Belt orbits are excluded from the inclination shadow-arc rendering.

> **Session 111:** Added; replaced the old belt `<rect>` marker and fat stroke approach.

---

### `_orbit_half_deg(a_px, e, available, persp_y, incl_rad, rot_z) -> float`

Computes the half-angle so the arc's vertical extent fits within `available`
pixels, accounting for z-rotation. Effective ry uses
`sqrt((a·sin_rot·persp_y)² + (b·(cos_i·cos_rot·persp_y + sin_i·cos_φ))²)`.
Returns 90° when `ry ≤ available`, otherwise `arcsin(available / ry)`, minimum 8°.
In perspective mode `build_svg` always uses `hd_arc=180°` (full ellipse), so this
function primarily governs top-down arc sizing.

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

| `world_type` | Glyph |
|---|---|
| `gas_giant` | Two circles: (1) stripe pattern fill (`url(#gg_stripe_S/M/L)`) from `gg_sah` category; (2) `url(#sph_overlay)` sphere-shading overlay. Optional foreshortened ring annulus (`_ring_halves`) in `palette.gg`. |
| `terrestrial` | Single circle with archetype radial gradient (`url(#terr_{archetype})`); archetype determined by `_world_archetype(detail, temperature_zone)`. |
| `belt` | Filled annular band (`_belt_band_path`) at `palette.belt` opacity 0.55; no separate marker. |
| `empty` | Small dot at marker position. |

Terrestrial worlds are no longer distinguished as inhabited/uninhabited by fill colour;
instead the archetype encodes physical world type (garden, ocean, desert, etc.).
The mainworld slot still receives an additional outer ring stroke in `palette.mainworld`.
Star glyphs continue to use `_sph(star_color)` (plain sphere gradient).

### Perspective mode depth cues

In perspective mode (`--perspective`):

- **Near/far orbit split:** each full-ellipse orbit arc with inclination ≥ 3°
  (`abs(ir) >= math.radians(3.0)`) is split at `n_seg//2` (α=0°, rightmost
  point) into a near half (upper screen, normal opacity) and a far half (lower
  screen, 40% of normal opacity, minimum 0.08). Orbits with inclination < 3°
  draw as a single full-opacity arc. Applied to world arcs and companion star
  dashed arcs.
- **Drop lines:** for inclined orbits (`abs(ir) > 1e-6`) where the z-displacement
  exceeds symbol-radius + 1 px, a dotted `<line>` connects the edge of the sphere
  to its z=0 projected position on the orbital plane.  The endpoint is
  `(mx, smy_z0)` where `smy_z0 = cy − y4·persp_y` (reusing the value already
  computed for the shadow ellipse).  Style: `stroke=palette.axis`,
  `stroke-width=1.4`, `stroke-dasharray="3,3"`, `opacity=0.75`.

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

**`build_svg(..., show_table: bool = True)`** (Session 153): the separator line + the whole
per-star table zone (`_table_zone_svg()`, extracted from `build_svg()` this session so it
can be conditionally skipped) is omitted when `show_table=False`, and `canvas_h` shrinks to
just `sep_y` (arc-zone height only, no added `tbl_h`) instead of `sep_y + tbl_h`. Every
existing caller (gen-ui's `SystemMapWindow`, the CLI, FastAPI's raw-SVG endpoints) keeps the
table by not passing this argument (`show_table` defaults `True`, so their output is
byte-for-byte unchanged). Only `TravellerSystem.to_poster_html()` passes `show_table=False`
— the poster shows this same per-star orbit data in its own "Full system card" page instead,
and (as of Session 152) had floating cards positioned right where this table used to render,
causing translucent card text to visually collide with the table's small monospace text.

**`children_by_parent: dict[str, list[Star]]`** (fixed issue #171): built once in `build_svg()`,
keyed by every star's own designation, mapping to that star's *direct* children — companions
(`role == "companion"`, parent = `designation[:-1]`) and, for the primary only, close/near/far
secondaries (they always orbit the primary directly — `generate_stellar_data()` never parents
them to anything else). Replaced the old flat `sec_stars` list
(`[s for s in stars if s.orbit_number > 0]`), which incorrectly lumped companions of secondary
stars in with the primary's own children — since `orbit_number`/`orbit_au` are relative to a
star's *own* parent, a companion of a secondary (e.g. "Ba", parent "B") was being plotted as if
it were that close to the primary. Both the arc-zone loop and `_table_zone_svg()` now use
`children_by_parent[<this star's designation>]` uniformly for every active star, not just the
primary — each star's zone/column draws only its own direct children as dashed context.

**Nested companion markers** (Session 165): when a `kind == "star"` context item itself has its
own children (`children_by_parent[<that item's own designation>]` non-empty — e.g. secondary "B",
shown as context inside the primary's zone, itself has companion "Ba"), those children are
**additionally** drawn nested next to that item's own marker, in the same zone, on top of its
already-correct placement in its own zone/column. Each `"star"`-kind item dict gained an optional
`"origin": (x, y)` key (both `kind == "star"` render blocks now read
`ocx, ocy = item.get("origin", (cx, cy))` instead of hardcoding the zone's `cx, cy`); nested items
set `origin` to their parent item's own `(mx, my)`. No new drawing logic was needed — the existing
`kind == "star"` treatment (dashed orbital arc + perspective shadow ellipse + drop line, reusing
`_orbit_arc`/`_shadow_orbit_arc`/`_orbit_screen_pts`/`_orbit_marker`, all of which already accept
an explicit origin) already matches world-orbit styling; only the origin/scale/inclination inputs
differ for a nested item:

- **Distance scale**: a local budget anchored on the parent glyph's own pixel radius
  (`nest_target = max(5 × _star_r_px(parent.diameter, arc_zone_h), 40)`), not the zone-wide AU
  axis — a companion's `orbit_au` relative to *its* parent is tiny next to typical planetary AU
  and would be invisible on the zone's main `log_scale`.
- **Inclination**: deliberately reuses the *parent* item's own `i_rad` (not the nested companion's
  own `orbit_inclination`) — drawn tilt matches whatever tilt the parent's own context arc uses.
- **Eccentricity**: uses the nested companion's own `orbit_eccentricity`, unmodified.
- **Draw order**: nested items are appended to `items` *after* `items.sort(key=lambda x: x["r"])`
  — a nested item's `r` lives on the unrelated local scale above, so sorting it in with top-level
  items by `r` would be meaningless and could draw a nested child before its own parent marker
  exists. Appending after the sort guarantees every nested marker paints after its parent.

One level of nesting only (a `"star"` item's own direct children) — WBH systems don't realistically
go deeper. Not primary-zone-specific in the code: it triggers wherever any `kind == "star"` item
has its own children, which today only arises for a secondary-with-a-companion shown inside the
primary's zone.

---

## What to read for related tasks

- Arc geometry / orbit placement → `_arc_path`, `_orbit_half_deg`, `_marker_xy` in `system_map.py`
- Orbit slot data (`OrbitSlot`, `star_zones`) → `context/data-structures.md`
- Calling `build_system_map_svg` from the GUI → `context/gen-ui.md`
- `TravellerSystem.to_poster_html()` (Session 148, `traveller_system_gen.py`) calls
  `build_svg()` directly and injects a `viewBox` (absent from the raw SVG output) so the map
  can be letterboxed into a fixed-size A3 poster box regardless of star count. See
  "A3 poster export" in `context/gen-ui.md`.
