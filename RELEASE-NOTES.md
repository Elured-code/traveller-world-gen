# Release Notes — v1.1.0

**Branch:** `feature/updates` → `main`
**Sessions:** 23–30
**Tests:** 614 (up from 523 in v1.0)

---

## New Features

### World Physical Detail

A new module `traveller_world_physical.py` implements the WBH physical world generation rules, producing a `WorldPhysical` record for every non-belt world that has physical detail requested.

**Fields generated:**
- Composition (silicate/ferric/icy/rocky) and density (g/cm³)
- Diameter (km), mass (M⊕), surface gravity (G), escape velocity (km/s)
- Axial tilt, including the full WBH p.77 extreme-tilt sub-table (6-band 1D table producing 20°–179° results)
- Rotation period (day length in hours)
- **Tidal lock status** (WBH pp. 105–107): 11-outcome table covering no-effect, tidal braking (×1.5–×5), prograde/retrograde spin, 3:2 resonance, and 1:1 lock; includes broken-lock check and axial tilt reroll for locked worlds

Physical detail is exposed in all output formats:
- **JSON** — `physical` object in world output
- **Text** — `World body` section in `summary()`
- **HTML** — `World body` inner-card in `to_html()`; Size stat box now shows actual rolled diameter and gravity rather than look-up table approximations
- **gen-ui** — new `Physical detail` checkbox (active only when `Full system` is checked); stellar card displays system age; `_build_physical_card()` renders the full physical card below trade codes

---

### Belt Physical Detail

A new module `traveller_belt_physical.py` implements WBH pp. 131–133 for asteroid belts, producing a `BeltPhysical` record for every belt orbit slot — whether a secondary world or the mainworld.

**Fields generated:**
- Belt span (inner and outer AU boundaries)
- Composition percentages: m-type (metallic), s-type (silicate), c-type (carbonaceous), and other
- Belt bulk (2D+2+DMs, minimum 1)
- Resource rating (2–12), with exploitation reduction for Industrial TL 8+ mainworlds
- Significant body counts: Size 1 planetoids and Size S planetoids (with optional outermost-orbit variance)

Belt physical detail is exposed in all output formats:
- **JSON** — `physical` object in `WorldDetail.to_dict()` for every belt slot
- **HTML** — `Belt body` block in the system mainworld panel
- **gen-ui** — `_build_physical_card()` dispatches on `BeltPhysical` to render span, composition, bulk, resource rating, and significant body counts

---

## Bug Fixes

### Gas Giant Mainworld Orbit Display (issue #22)

When the mainworld was a satellite of a gas giant, the orbit table showed the satellite's UWP profile (e.g. `A689521-B`) instead of the gas giant's profile (e.g. `GM7`). A secondary symptom caused the satellite to disappear entirely when the gas giant had no additional moons.

Fixed across three layers: `attach_detail()` now uses `orbit.gg_sah` for gas giant mainworld orbits and inserts the satellite as `moons[0]`; `_orbit_profile()` in gen-ui returns `gg_sah` first; `to_html()` in `TravellerSystem` uses `gg_sah` for CSS class and profile display in both detail-attached and no-detail paths.

### Belt Mainworld Display Crash in gen-ui (Session 30)

When generating a belt mainworld with physical detail enabled, `_build_stat_row()` attempted to access `physical.diameter_km` and `physical.gravity` — attributes present on `WorldPhysical` but not on `BeltPhysical`. The uncaught exception left only the header bar visible and silently discarded the scroll area. Fixed with an `isinstance(physical, BeltPhysical)` guard.

### Belt Span Formula Correction (issue #27, Session 30)

Belt span was computed using the AU range of the entire system (`max_au − min_au`) instead of the correct WBH p.131 "system orbit spread" — the per-slot orbital generation step `(max Orbit# − MAO) / n_orbits`. This produced wildly oversized spans (e.g. 0–11.97 AU for a belt at 0.35 AU). After correction, spans are physically plausible (e.g. 0.034–0.662 AU for the same belt). The fix applies to both secondary belts (`generate_system_detail()`) and mainworld belts (`attach_detail()`), with the spread computed per-star.

### Belt Bulk Formula Correction (Session 30)

Belt bulk was computed as 2×D2+DMs (range 2–4 before DMs), inconsistent with WBH p.132 which specifies 2D+2+DMs. Updated to `_roll(2, 2 + dm)` (range 4–14 before DMs).

---

## Test Coverage

| Scope | Tests added |
|---|---|
| `traveller_world_physical.py` — physical detail + tidal lock | +91 |
| `traveller_belt_physical.py` — belt span, composition, bulk, rating, bodies | +45 |
| Belt mainworld `attach_detail()` integration | +4 |
| **Total new tests** | **+91** |
| **Suite total** | **614** |

All 614 tests pass. Pylint 10.00/10 on all modified files.
