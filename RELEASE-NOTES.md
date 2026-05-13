# Release Notes — v1.1.0

**Branch:** `feature/updates` → `main`
**Sessions:** 23–35
**Tests:** 890 (up from 523 in v1.0)

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
- **JSON** — `size_detail` object in world output
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

### Atmosphere Detail (WBH pp. 78–93)

Five phases of WBH atmosphere detail have been fully implemented, adding quantitative atmosphere data to every mainworld. All data is exposed in JSON, HTML, text summary, and the gen-ui atmosphere card.

**Phase 1 — Pressure, O₂, and scale height (WBH pp. 78–82)**

A new `AtmosphereDetail` dataclass and `generate_atmosphere_detail()` function compute:
- Surface pressure (bar), sampled from the WBH pressure span table with (2D−7)/100 variance
- Oxygen partial pressure, with DM+1 for systems older than 4 Gyr
- Atmospheric scale height (km), approximated as 8.5 / surface gravity
- WBH p.82 profile string: `{code}-{pressure_bar:.3f}-{ppo:.3f}`, e.g. `6-1.013-0.212` for Terra

**Phase 2 — Atmosphere taints (WBH pp. 82–85)**

Taint generation for tainted atmosphere codes (2, 4, 7, 9), with each taint carrying:
- Subtype (Radioactivity, Particulates, Low Oxygen, High CO₂, etc.)
- Severity (scale 1–9, labelled from "Minor irritant" to "Inevitably lethal")
- Persistence (scale 2–9, from "Constant" to "Rare, brief event")
- Cascade mechanic: Particulates result triggers a second taint roll

Taint suffix appended to profile string as `-T.S.P` per taint.

**Phase 3 — Exotic and corrosive/insidious subtypes (WBH pp. 85–87)**

Subtype rolls for Exotic (code 10/A), Corrosive (code 11/B), and Insidious (code 12/C) atmospheres, with:
- Orbit-position DMs on both subtype tables
- 14-entry Exotic subtype table; 14-entry Corrosive/Insidious subtype table
- Insidious hazards: up to 3 hazard rolls per world, each with optional additional gas
- Unbound pressure subtypes (C/D/E) represented as `None` in the model; displayed as `> 10.0 bar`

**Phase 4 — Gas composition (WBH pp. 87–95)**

Full gas mix generation for Exotic/Corrosive/Insidious atmospheres:
- 7 temperature-banded gas tables (Boiling-VH, Boiling-H, Hot, Temperate, Cold, Frozen-M, Frozen-D)
- 24 named gases, each with an eHex percentage
- CO* substitution: CO → CO₂ when not frozen with water; CO → N₂ when frozen with water
- Gas codes appended to profile string as `:code-##` tokens

**Phase 5 — Altitude bands and Unusual subtypes (WBH pp. 90–93)**

Altitude band computation for Very Dense (code 13/D) and Low (code 14/E) atmospheres:
- Minimum safe altitude above baseline (code 13) or maximum safe depth below baseline (code 14), derived from the WBH Bad Ratio formula: `altitude = ln(bad_ratio) × scale_height`
- `no_safe_altitude = True` when no breathable level exists
- Optional taint roll (1D ≥ 4) for codes 13 and 14

D26 subtype generation for Unusual (code 15/F) atmospheres:
- 12-entry D26 table (11–26) covering Dense subtypes, Ellipsoid, High Radiation, Layered, Panthalassic, Steam, Variable Pressure, Variable Composition, Combination, and Other
- Prerequisite checks: Layered requires size ≥ 9 (gravity > 1.2 G); Panthalassic requires hydro = 10; Steam requires hydro ≥ 5
- Combination result (D26 = 25) produces two independent non-Combination subtypes
- Profile string format: `F-S{code}` or `F-S{code1}.{code2}`, e.g. `F-S7` or `F-S3.A`

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
| Atmosphere Phase 1 — pressure, O₂, scale height | +52 |
| Atmosphere Phase 2 — taints (subtype, severity, persistence, cascade) | +42 |
| Atmosphere Phase 3 — exotic/CI subtypes, insidious hazards | +33 |
| Atmosphere Phase 4 — gas composition (7 tables, CO* substitution, profile) | +62 |
| Atmosphere Phase 5 — altitude bands, unusual subtypes, display | +58 |
| API and display regression tests | +8 |
| **Total new tests** | **+367** |
| **Suite total** | **890** |

All 890 tests pass. Pylint 10.00/10 on all core generation modules.
