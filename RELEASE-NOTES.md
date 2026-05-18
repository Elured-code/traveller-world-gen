# Release Notes — v1.2.0

**Branch:** `feature/updates` → `main`
**Sessions:** 36–41
**Tests:** 969 (up from 890 in v1.1)

---

## New Features

### Hydrographic Detail (Session 37)

New module `traveller_hydro_detail.py` implements WBH p.93 surface liquid percentages.

`HydrographicDetail` dataclass carries `surface_liquid_pct` (a flat random value within the WBH code range). `generate_hydrographic_detail()` is called from the shared section of `traveller_system_gen.py` and all API handlers. Exposed in:
- **JSON** — `hydrographics.detail.surface_liquid_pct`
- **HTML** — Hydrographic Detail inner-card in `World.to_html()`, `TravellerSystem.to_html()`, and `World.summary()`
- **gen-ui** — `_build_hydrographic_card()`

---

### NHZ Atmosphere Generation (Session 38)

Out-of-habitable-zone worlds now roll NHZ atmosphere codes when the `nhz_atmospheres` flag is set. Two new atmosphere codes are added: code 16 (Gas, Helium / G) and code 17 (Gas, Hydrogen / H).

Four NHZ tables cover the four deviation bands (HZCO ≤ −2.01, −2.0 to −1.01, +1.01 to +3.0, ≥ +3.01). Each table result carries an atmosphere code, an optional exotic subtype key, and display markers. NHZ worlds with an exotic subtype bypass the standard `_roll_exotic_subtype()` roll.

NHZ generation is applied to mainworlds, secondary worlds, and moons:
- `generate_full_system()` and `generate_mainworld_at_orbit()` accept `nhz_atmospheres: bool = False`
- `TravellerSystem` stores `nhz_atmospheres` and threads it through `attach_detail()` to all secondary-world and moon paths
- gen-ui: "NHZ Atmospheres" checkbox added (enabled only when System detail is checked)
- CLI: `--nhz-atmospheres` flag added
- JSON Schema: `atmosphere.code.maximum` updated from 15 to 17

---

### Primary Star Outer Zone Placement (Session 39)

Primary stars in binary systems now populate the outer zone `[companion + 3.0, 17.0]` as well as the inner zone `[MAO, companion − 1.0]`. Previously all primary worlds were placed in the inner zone; the outer zone was unused.

A `star_outer` dict tracks the outer zone bounds. `_avail_range()` includes the outer range in proportional world allocation across stars. The placement loop wraps in a `for zone in zones` iterator that runs once per zone (inner, then outer), keeping the existing baseline → spread → slot logic unchanged within each pass.

Seed-breaking for any primary star that has a close/near/far companion with a valid inner zone.

---

### System Map — Column Label Sub-header Row (Session 39)

The orbit table in every system map now displays a column label row (`#  Orbit#  AU  Type  Profile  Codes  Zone ♦`) between the star header and the first world row. `Zone ♦` makes explicit that the last column shows both the temperature zone and moon count. `_TBL_ROW0_OFF` bumped from 38 to 50 px to accommodate the new row.

---

### Anomalous Orbits (Session 41, issue #12)

WBH Step 7 (pp.49-50) is now implemented. After normal orbit placement, `generate_orbits()` rolls for anomalous orbit count (2D: ≤9 = 0, 10 = 1, 11 = 2, 12 = 3) and type.

**Anomaly types:**

| Type | Frequency | Effect |
|------|-----------|--------|
| Random | 2D ≤ 7 | Orbit placed anywhere in the star's valid zone |
| Eccentric | 2D = 8 | As random (eccentricity DM deferred) |
| Inclined | 2D = 9 | Inclination rolled (1D+2)×10° + d10; stored in notes |
| Retrograde | 2D = 10–11 | "Retrograde" noted |
| Trojan | 2D = 12 | Co-orbital with an existing non-empty world; 1D ≤ 3 → leading (L4), ≥ 4 → trailing (L5) |

Each anomalous orbit adds one terrestrial (or belt when the maximum of 13 terrestrials has been reached). In multi-star systems the star is chosen randomly from those with available orbit space.

Anomalous orbit positions respect companion exclusion bands (the same valid zone bounds used for normal placement, with ±0.01 clearance from each boundary to avoid landing exactly on the band edge).

**New field:** `OrbitSlot.anomaly_type: str` — one of `""`, `"random"`, `"eccentric"`, `"inclined"`, `"retrograde"`, `"trojan_leading"`, `"trojan_trailing"`. Included in `to_dict()` when non-empty.

**Display:**
- `system_map.py` — anomaly indicator appended to the type column: `"terr *"`, `"terr ~"`, `"terr /"`, `"terr R"`, `"terr L4"`, `"terr L5"`; belts use analogous `"belt ..."` labels
- `TravellerSystem.to_html()` orbit table — anomaly notes shown in the notes column (e.g., `[Inclined 45°]`, `[Trojan leading (L4)]`)
- `SystemOrbits.summary()` text output — same notes shown inline

**Seed impact:** The new `roll(2)` for anomalous count fires for every system — all seeds shift from Session 41 onwards.

---

### Orbit Notes Column (Session 41 cont.)

`OrbitSlot.notes` is now surfaced in every output that displays the orbit table:

- **gen-ui** — System Orbits card gains a trailing `Notes` column in both header variants: 10 columns (detail attached: `Star | Orbit# | AU | Type | Profile | Codes | HZ | Zone | Period | Notes`) and 8 columns (no detail: `Star | Orbit# | AU | Type | HZ | Zone | Period | Notes`).
- **`TravellerSystem.to_html()`** — orbit table notes cell now uses a `note_parts` list that combines the `"← mainworld"` marker with `OrbitSlot.notes`, showing all notes unconditionally for every orbit row (HZ placement notes, anomaly type notes, etc.).

---

### Orbital Periods (Session 40)

Kepler orbital periods are now computed and displayed for every star and world in a generated system.

**Stellar periods (`Star.orbit_period_yr`)**

`generate_stellar_data()` computes `P = √(AU³ / (M_central + m))` for every non-primary star after all dice rolls are complete (no seed disruption). Central mass rules follow WBH:
- Companion stars (e.g. Ab orbiting A): M_central = parent mass only
- Secondary stars (e.g. B, C): M_central = combined mass of all stars with effective system orbit# < this star's orbit#

`_eff_sysorn()` ensures that a companion to a secondary (e.g. Ba) uses its parent's orbit# when computing central mass for farther secondaries (so Ca's M_central correctly includes Ba). Periods are included in `Star.to_dict()` and `StarSystem.summary()`.

**World periods (`OrbitSlot.orbit_period_yr`)**

`generate_orbits()` computes `P = √(AU³ / M_central)` for every non-empty orbit slot after placement. M_central = designated star mass plus any companions whose `orbit_au < world.orbit_au` (WBH: worlds outside a tight companion include it in the central mass). Planet mass correction (`mE × 0.000003`) is omitted as negligible. Periods are emitted in `OrbitSlot.to_dict()`.

**Display — `system_map.py` and gen-ui**

- New `Period` column (x=490) in the orbit table of every system map, populated for both star rows and world rows
- `_fmt_period()` module-level helper auto-scales: `< 1 day → Xh`, `1–365 days → Xd`, `≥ 365 days → Xy`
- gen-ui System Orbits card gains a `Period` column in both detail-attached and non-attached variants
- gen-ui Stellar card gains a `Period` column (7 columns total, right-aligned)

---

## Bug Fixes

### System HTML Missing Mainworld Detail (Session 36, issue #51)

`TravellerSystem.to_html()` was omitting the `WorldPhysical` and atmosphere detail inner-cards from the mainworld panel — only `BeltPhysical` was handled. Added `.inner-card`, `.inner-lbl`, `.drow`, `.dlbl` CSS; `drow()` helper; and imports for `WorldPhysical`, `TIDAL_STATUS_LABELS`, and `format_atmosphere_profile()`.

### TravellerMap Fetch Incomplete Atmosphere Pipeline (Session 36, issue #51)

`generate_system_from_map()` was not calling `generate_gas_mix()` or `generate_unusual_subtype()` after `generate_atmosphere_detail()`, leaving gas composition and unusual subtypes absent for TravellerMap-fetched worlds. Also threaded `hz_deviation` into `generate_atmosphere_detail()` for orbit-position DMs. Both calls now follow the same pipeline as procedurally generated worlds.

### H/L Oxygen Taint Validation (Session 37, issue #55)

`_roll_single_taint()` now accepts `ppo: Optional[float]` and rerolls High Oxygen (H) results unless `ppo > 0.5 bar`, and Low Oxygen (L) results unless `ppo < 0.1 bar`. The `ppo` computation was moved before the taint block in `generate_atmosphere_detail()` so it is available at taint time. Seed-breaking for tainted atmosphere codes.

### Companion Star Exclusion Zone (Session 39)

When a companion orbit# was less than 1.0, `excl = companion_orbit − 1.0` was ≤ 0 and never triggered the `max_o` cap, allowing primary worlds inside the WBH exclusion band `[companion − 1, companion + 3]`. Fixed: an `else` branch now pushes `mao = max(mao, companion_orbit + 3.0)` and syncs `star_mao[designation]` in-place.

`system_map.py` extended to render companion star rows inside the primary star's orbit-table section, sorted by orbit number.

---

## Test Coverage

| Scope | Tests added |
|---|---|
| `traveller_hydro_detail.py` — surface liquid percentages | +29 |
| H/L oxygen taint ppo validation | +6 |
| NHZ atmosphere generation (mainworld) | +33 |
| NHZ atmosphere generation (secondary worlds and moons) | +5 |
| Companion star exclusion zone fix | +2 |
| Primary star outer zone placement | +4 |
| Anomalous orbits (Step 7) | +6 |
| **Total new tests** | **+79** |
| **Suite total** | **969** |

All 969 tests pass. Pylint 10.00/10 on all core generation modules.

---

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
