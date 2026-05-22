# Research: System Map 60° Perspective Projection

**Status:** Research only — not implemented  
**Related module:** `system_map.py`  
**See also:** [`context/system-map.md`](system-map.md)

---

## Current state

The system map renders orbits as a top-down (orthographic) view. Orbits are SVG `<circle>` elements centred on the star; body positions are placed in flat 2D coordinates.

---

## What a 60° vertical tilt would require

A 60° angle from vertical foreshortens the y-axis by `cos(60°) = 0.5`. The following changes would be needed:

### 1. Orbit rings
Replace `<circle cx cy r>` with `<ellipse cx cy rx ry>` where:
- `rx = orbit_radius` (unchanged)
- `ry = orbit_radius * 0.5`

### 2. Body positions
All placed objects (star, planets, moons, binary companions):
- x-coordinate: unchanged
- y-coordinate: multiply by `0.5`

### 3. Paint / depth order
Objects with a larger *unscaled* y-value (farther "back" in the scene) must be drawn first so they render behind nearer objects. Currently irrelevant because everything is flat.

### 4. Binary star orbits
Companion star paths need the same ellipse treatment.

### 5. Labels
Text anchor positions need the same y × 0.5 adjustment.

### 6. ViewBox
The effective vertical extent shrinks; the viewBox height may need redistribution to preserve proportional whitespace.

---

## Trade-offs

| Pro | Con |
|-----|-----|
| Adds visual depth | Orbit spacing looks compressed — AU proportionality less obvious |
| More "space-map" aesthetic | Label placement becomes harder |
| | Depth sorting adds render-order complexity |
| | Purely cosmetic unless shading/gradient added to reinforce the 3D plane |

## Verdict

Worth doing for visual flair; not worth it if the map's primary job is legibility. If implemented, adding a subtle gradient fill to the orbit ellipses (lighter at the top, darker at the bottom) would significantly reinforce the perspective effect for low extra cost.
