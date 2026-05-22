# Release Notes — v1.3.0 (draft)

**Branch:** `feature/updates` → `main`
**Sessions:** 55–61
**Tests:** 1267

---

## Native Life — Biomass Rating (Session 61, WBH pp.127–131)

Biomass ratings are now generated for all terrestrial worlds and moons in a system.

**Generation:** `generate_biomass_rating()` rolls 2D with DMs from atmosphere, hydrographics, system age, and temperature (simplified zone or mean K when available). Combined DM is clamped to [−12, +4]. Roll ≤ 0 → no native life. Special Case 1 (biologic taint + rolled 0 → biomass 1) is implemented but dormant pending biologic taint generation. Special Case 2 (inhospitable atmospheres 0, 1, A, B, C, F+ → biomass adjusted upward) is active. The optional rule (oxygenated atmospheres minimum biomass 1) is implemented off by default — see **Optional rule** below.

**RNG placement:** All biomass rolls are appended at the end of `attach_detail()` via `_apply_biomass()`, preserving all existing seed outputs for other fields.

**Mainworld requirement:** Mainworld biomass is only computed when Mainworld Detail is enabled (`WorldPhysical` set). Secondary worlds and their moons always receive biomass ratings when System Detail is enabled.

**Data structures:**
- `World.biomass_rating: Optional[int]` — mainworld biomass (set by `_apply_biomass()`)
- `WorldDetail.biomass_rating: Optional[int]` — secondary world and moon biomass

**Display:**
- System card orbit table Notes column: "Biomass N" for any terrestrial world or moon with biomass > 0
- Mainworld physical card (World Body): always shows biomass rating when Mainworld Detail is enabled
- JSON output: `biomass_rating` field added to World schema (optional integer, min 0)

**Optional rule — "Oxygen requires biomass":** When enabled (`optional_biomass_rule=True` in `attach_detail()`), any world with an oxygenated atmosphere (codes 2–9, D, E) that rolls biomass 0 is raised to 1. In gen-ui, controlled by the **"Oxygen requires biomass"** checkbox (enabled only when System detail is active; cleared when System detail is disabled). No seed disruption when disabled. Rare earth variant remains deferred.

**Tests:** 72 new tests in `tests/test_biomass.py` covering all DM table entries, DM clamping, Special Cases 1 and 2, temperature paths, age DM cumulative application, and the optional oxygen rule.

---

## World Physical Detail

### Tidal Stress Factor (issue #67, WBH p.126)

`WorldPhysical` gains `tidal_stress_factor: Optional[int]` — the seismic stress
contribution from surface tidal forces.

**Formula:** `floor(tidal_amplitude_m / 10)` where `tidal_amplitude_m` is the
combined surface tidal amplitude already computed by Session 58 (star + moons).

**Example:** A world with 30.6 m of moon tidal effect + 0.24 m star effect gives
tidal_amplitude_m = 30.84 → TSF = 3.

**Integration:** `total_seismic_stress` is now the sum of all three components:
Residual Seismic Stress + Tidal Seismic Stress + Tidal Stress Factor. Both
`tidal_amplitude_m` and `tidal_stress_factor` are set together inside
`_apply_seismic_stress()` via `_compute_tidal_amplitude()`.

Displayed in gen-ui World Body card, `world_card.html`, and `render_system_json.py`
in the order: Tidal Seismic Stress → Tidal Stress Factor → Residual → Total.
`tidal_stress_factor` is emitted to JSON and schema only when > 0.

6 new tests in `TestTidalStressFactor`.

---

### Surface Tidal Amplitude (issue #68, WBH pp.107–108)

`WorldPhysical` gains `tidal_amplitude_m: Optional[float]` — the combined surface tidal
amplitude in metres from the primary star and all significant moons.

**Star effect:** `(star_mass_solar × size) / (32 × AU³)`. Sol acting on Terra ≈ 0.25 m.

**Moon effect per moon:** `(moon_mass_earth × size) / (3.2 × (orbit_km / 10⁶)³)`. Moon mass
estimated from size using Terran density: `(size × 1600 / 12742)³` M⊕ (same method used in
`WorldPhysical.mass`). Rings and moons without `orbit_km` are excluded.

**Pipeline:** `generate_world_physical()` stores a star-only preliminary value in
`tidal_amplitude_m`; `apply_moon_tidal_effects()` adds all moon contributions and updates
the field in-place.

**Display:** "Tidal amplitude: X.XX m" row appears after the Tidal status row in all four
output surfaces — gen-ui World Body card, `world_card.html` Jinja2 template,
`render_system_json.py`, and the JSON schema (`tidal_amplitude_m` added to the
`WorldPhysical` branch).

21 new tests across `TestStarTidalEffectM`, `TestMoonMassEarth`, `TestMoonTidalEffectM`,
`TestComputeTidalAmplitude`, `TestTidalAmplitudeIntegration`.

Also in this session: the pre-existing `_ZONE_OBJECT_NAME → ZONE_CSS_CLASS` name typo in
`gen-ui/app.py` was fixed, and `test_moon_lock_occurs_when_dm_high_enough` was patched to
be fully deterministic (the broken-lock check was a source of intermittent test flap).

---

- **Seismic stress** is now calculated for every mainworld that has physical detail
  generated (i.e., when "World physical" is checked in the app). Three components are
  shown in the World Body card:
  - **Residual Seismic Stress** — derived from the world's size, age, density, and
    moon sizes. A young, large, dense world with big moons will have high residual stress.
  - **Tidal Heating Factor** — contribution from orbital eccentricity around the primary
    star. Significant only for close, highly eccentric orbits (e.g., tidally locked
    worlds that have retained eccentricity through resonance).
  - **Total Seismic Stress** — sum of the above (Tidal Stress Factor from WBH p.126
    is deferred — see below).
  - **Seismic Temperature** — the mean temperature adjusted for internal heat:
    ⁴√(T⁴ + TSS⁴). Shown only when the adjustment rounds to a different value than
    the base mean temperature.

---

## Bug Fixes

### Mainworld-as-moon row not bold in orbit table (Session 61)

When the mainworld is a satellite of a gas giant it appears as a moon sub-row in the system orbit table. It was rendered with the `table-moon` CSS class instead of `table-mw`, so the row was not displayed in bold like other mainworld rows. Fixed: `moon_css` is now `"table-mw"` when `is_mw and mi == 1 and orbit.world_type == "gas_giant"`.

---

### BeltPhysical crash in `apply_moon_tidal_effects()` (Session 59)

`apply_moon_tidal_effects()` was called for belt mainworlds (Size 0), passing a
`BeltPhysical` object where `WorldPhysical` was expected. Both the tidal lock
re-run and `_apply_seismic_stress()` access attributes (`density`, `axial_tilt`,
`tidal_status`, etc.) that exist only on `WorldPhysical`, raising `AttributeError`.

Fix: `apply_moon_tidal_effects()` now returns immediately when `physical` is not
a `WorldPhysical` instance. Belt worlds have no tidal lock or seismic stress fields,
so the early return is semantically correct, not just defensive.

---

## Maintenance

### gen-ui: eccentricity and inclination always calculated (issue #58)

The "Orbital Eccentricity" and "Orbital Inclination" checkboxes have been removed
from the desktop UI. Both flags are now always passed as `True` when "System detail"
is enabled, so the Ecc/Incl column is always populated.

---

### Rename: `tidal_heating_factor` → `tidal_seismic_stress` (Session 59)

The WBH term for the orbital tidal contribution to seismic stress is "Tidal Seismic
Stress", not "Tidal Heating Factor". Renamed throughout:

- `WorldPhysical.tidal_heating_factor` field → `tidal_seismic_stress`
- `_compute_thf()` → `_compute_tidal_ss()`
- JSON key `"tidal_heating_factor"` → `"tidal_seismic_stress"`
- JSON schema property and description updated
- Display label in gen-ui, `world_card.html`, and `render_system_json.py`
- Tests updated (`TestComputeThf` → `TestComputeTidalSS`)

Formula and logic unchanged. Total Seismic Stress = Residual Seismic Stress +
Tidal Seismic Stress.

---

### Static typing — enum types (issue #38)

Five `StrEnum` / `IntEnum` types added to a new `world_codes.py` module, compatible with all existing `str` / `int` comparisons and JSON serialisation.

| Enum | Values |
|---|---|
| `StarportCode` (`StrEnum`) | `A B C D E X` |
| `TemperatureCategory` (`StrEnum`) | `Frozen Cold Temperate Hot Boiling` |
| `TradeCode` (`StrEnum`) | all 18 codes (`Ag As Ba De Fl Ga Hi Ht Ic In Lo Lt Na Ni Po Ri Va Wa`) |
| `TravelZone` (`StrEnum`) | `Green Amber Red` |
| `AtmosphereCode` (`IntEnum`) | codes 0–17 |

**`parse_uwp()` validation (`traveller_map_fetch.py`):** The UWP parser now raises `ValueError` (with chained exception context via `from exc`) for any of: wrong length, missing `-` separator at position 7, unrecognised starport letter, or non-hex digit in code positions. Previously it silently substituted defaults for malformed input.

**`World._validate_world_codes()` (`traveller_world_gen.py`):** New static method called at the top of `World.from_dict()`. Validates starport, atmosphere, temperature, trade codes, travel zone, and all integer range fields against the enum types and schema constraints. All validation failures raise `ValueError` with a descriptive message and chained exception context.

**Pyright CI:** `.github/workflows/typecheck.yml` added — runs `pyright` on every push/PR to `main`. `pyrightconfig.json` updated (`typeCheckingMode: "basic"`, explicit `exclude` list re-specifying all default patterns). `requirements-dev.txt` gains `pyright>=1.1.0`. Eight pre-existing Pyright errors in `traveller_world_gen.py`, `traveller_world_physical.py`, and `traveller_world_detail.py` were fixed: stored-boolean narrowing replaced with inline `isinstance()`, `Moon` forward reference resolved via `TYPE_CHECKING` guard, `hasattr()` narrowing replaced with `isinstance()`.

---

### Centralised display tables (issue #39)

Seven display-layer lookup tables previously duplicated across two to three files have been consolidated into a new `tables.py` module — a single definition is now the canonical source for each label set.

| Table | Previously defined in |
|---|---|
| Size → diameter label | `traveller_world_gen.py` ×2 |
| Size → gravity label | `traveller_world_gen.py` ×2 |
| Population → range label | `traveller_world_gen.py` ×2 |
| Trade code full names | `traveller_world_gen.py`, `gen-ui/app.py` |
| Base facility labels | `traveller_world_gen.py`, `gen-ui/app.py`, `render_system_json.py` |
| Travel zone → CSS class | `traveller_world_gen.py`, `gen-ui/app.py`, `render_system_json.py` |
| Tidal lock status labels | `traveller_world_physical.py`, `render_system_json.py` |

All five consumer files (`traveller_world_gen.py`, `traveller_system_gen.py`, `render_system_json.py`, `gen-ui/app.py`, `tests/test_world_physical.py`) now import from `tables`. No display output was changed.

---

### Pylint

`.pylintrc` restored after accidental deletion in commit f9f6ca1. The `[MESSAGES CONTROL]` block suppresses two structural false positives with inline documentation:

- `duplicate-code` — identical pipeline boilerplate exists across five entry-point files; several data-table copies are intentional to break circular imports. Tracked for future refactoring.
- `cyclic-import` — pre-existing `traveller_system_gen` → `traveller_world_detail` cycle resolved at runtime via `TYPE_CHECKING` guard. Tracked for cleanup.

Pylint 10.00/10 maintained across all core generation modules.

---

# Release Notes — v1.2.0

**Branch:** `feature/updates` → `main`
**Sessions:** 36–54
**Tests:** 1146

---

## Maintenance

### Static type-checking (Pyright / Pylance)

`pyrightconfig.json` added to the project root so Pylance resolves imports from
the project root (`extraPaths: ["."]`) consistent with the runtime `sys.path` that
`conftest.py` establishes for pytest.

All six test files made fully Pyright-clean (0 errors, 0 warnings):

| File | Issues fixed |
|------|-------------|
| `test_belt_physical.py` | 2 unguarded `system.mainworld` accesses |
| `test_function_app.py` | Azure stub used direct attribute assignment on `ModuleType` (→ `setattr()`); 4 unguarded `err` accesses |
| `test_hydro_detail.py` | 4 unguarded `generate_hydrographic_detail()` return accesses |
| `test_moon_gen.py` | `list[float | None]` not narrowed through intermediate comprehension |
| `test_traveller_world_gen.py` | Two pairs of shadowed class names; `Optional` attribute guards; `comp.orbit_number` arithmetic guards |
| `test_world_physical.py` | `_World` stub now inherits from `World`; mixed-type `**kwargs` dicts annotated `dict[str, Any]` |

**Notable bug found:** `TestWorldToDict` and `TestWorldToJson` were each declared
twice in `test_traveller_world_gen.py`. Python's namespace rules mean the second
definition silently replaced the first, so the first class's tests **never ran**.
The first instances are renamed `TestWorldToDictValues` and `TestWorldToJsonBasic`;
61 previously-invisible tests now execute.

**Source fix:** `World.to_json(indent: int = 2)` signature corrected to
`indent: Optional[int] = 2`, matching the docstring ("Pass `None` for compact
single-line output") and the `json.dumps` behaviour already in use.

**1146 tests** pass (1085 previously confirmed + 61 now un-shadowed).

---

## Improvements

### Basic Mean Temperature (Session 54, WBH p.47)

`WorldPhysical` gains `mean_temperature_k: Optional[int]` — the Basic Mean Temperature
in Kelvin computed from orbital position and atmosphere code.

**Formula:** modified roll = 7 (base/HZCO) + orbital DM + atmosphere DM.
Orbital DMs: `+4 +1 per 0.5 Orbit# below HZCO-1`; `−4 −1 per 0.5 Orbit# above HZCO+1`.
Atmosphere DMs are the same HZ Regions table DMs used for temperature categories.
Table lookup covers rolls 0–12 (178K–388K); extrapolates below 0 (−5K/step) and
above 12 (+50K/step); minimum 3K.

**Call sites:** `generate_world_physical()` gains `hz_deviation: Optional[float] = None`
parameter; `function_app._attach_mainworld_physical()` and `gen-ui/app.py` both pass
`mw_orbit.hz_deviation`. Value is absent when hz_deviation is not available (e.g., simple
standalone world generation without orbit context).

**Display:** all four HTML templates gain a "Mean temperature" row after "Day length";
`render_system_json.py._phys_rows()` and `traveller_world_schema.json` updated.

17 new tests in `TestOrbitDmForMeanTemp` (7) and `TestComputeMeanTemperature` (10);
**1085 tests** pass.

### HTML Template Refactor (Session 53, issue #40)

`World.to_html()` and `TravellerSystem.to_html()` now use Jinja2 templates
instead of hand-built f-strings. This eliminates doubled braces in CSS blocks,
makes the HTML structure directly editable without touching Python, and enables
Jinja2's built-in autoescaping (replaces the custom `esc()` helper).

**New files:**
- `html_render.py` — thin rendering module with a module-level `jinja2.Environment`
- `templates/world_card.html` — single world card
- `templates/world_list.html` — multi-world list (used by `--html` with multiple worlds)
- `templates/system_card.html` — full system card

**`requirements.txt`** gains `Jinja2>=3.1.0`.

The multi-world CLI `--html` output was previously stitched together with a fragile
regex that re-parsed each card's HTML. It now uses `world_list.html` directly.

---

## New Features

### Moon Tidal Lock DMs and Planet-to-Moon Lock (Session 52, WBH pp.106–107, issue #11)

Moon orbital positions (added in Session 51) unlock two previously deferred tidal effects.

**Moon-size DM in star-lock (WBH p.106):** `_tidal_lock_dm()` now subtracts the total size of all significant moons (Size 1+, non-ring) from the tidal lock DM when evaluating planet-to-star lock.

**Multi-star DM (WBH p.106):** `_tidal_lock_dm()` subtracts the number of stars orbited when > 1. Currently simplified to `num_stars_orbited=1` (full multi-star support deferred); the parameter is wired through the full call chain.

**Planet-to-moon lock (WBH p.107):** New `_planet_moon_lock_dm(moon, all_moons)` implements the WBH p.107 DM table: base −10, +Moon Size (Size 1+), PD-range DMs (orbit PD < 5: `+5 + ceil((5−PD)×5)`, 5–10: +4, 10–20: +2, 20–40: +1, 40–60: no DM, > 60: −6), −2 per moon beyond the first.

**Lock candidate ordering:** `_roll_tidal_lock_status()` now assembles all candidates (star + each qualifying moon), sorts by highest DM (moon before star on tie), and cascades until a lock result is found or all candidates are exhausted.

**Circular dependency resolution:** `WorldPhysical` needs moon data for DMs, but moons need `WorldPhysical` (diameter/mass) for Hill sphere. A new public `apply_moon_tidal_effects(physical, moons, ...)` function resolves this via a three-phase pipeline: `generate_world_physical()` runs first (no moon DMs), moons are generated using actual planet mass/diameter, then `apply_moon_tidal_effects()` re-runs tidal lock with full moon data and mutates `WorldPhysical` in-place.

New helpers in `_get_mainworld_moons()` and `_apply_mainworld_moon_tidal()` in `function_app.py` handle both GG satellite (moons at `orbit.detail.moons[0].detail.moons`) and non-GG (moons at `orbit.detail.moons`) cases. `gen-ui/app.py` `_finish_system_generation()` calls `apply_moon_tidal_effects()` after detail attachment.

24 new tests across `TestTidalLockDmMoon` (8), `TestPlanetMoonLockDm` (10), `TestRollTidalLockStatusMoons` (3), `TestApplyMoonTidalEffects` (3); **1068 tests** pass.

---

### Moon Quantity Adjacency DMs (Session 52, WBH p.56, issue #14)

Three of the four WBH p.56 moon quantity DM conditions that were previously deferred (blocked on moon orbital positions) are now implemented.

`_moon_quantity()` in `traveller_moon_gen.py` gains three new optional parameters, applied as `DM−1 per dice` when any condition is met (only one DM applies per world):

| Condition | Parameter |
|-----------|-----------|
| Planet orbit within companion star exclusion zone (±1 to +3 of companion orbit#) | `companion_exclusion_zones: list[tuple]` |
| Planet orbit adjacent to host star MAO boundary (±1.0) | `star_mao: float` |
| Planet orbit adjacent to outermost Far-star slot (±1.0) | `is_adjacent_outermost_far: bool` |

The fourth condition (`orbit_number < 1.0`) was already implemented. `generate_moons()` passes through the three new parameters.

`_moon_adjacency_context()` in `traveller_world_detail.py` computes these values from the system context (iterating `stellar_system.stars` for companions and Far stars, reading `system_orbits.star_mao`). The context dict is passed to `_moons_for()` and forwarded to both `generate_moons()` call sites in `generate_system_detail()` and `attach_detail()`.

8 new tests in `TestMoonQuantityAdjacencyDMs`; **1044 tests** after this feature (1068 after both features in Session 52).

---

### Moon Orbit Placement (Session 51, WBH pp.74–77, issue #16)

Moons now have orbital positions. `generate_moons()` accepts five new optional parameters (`orbit_au`, `star_mass_solar`, `planet_ecc`, `planet_diameter_km`, `planet_mass_earth`); when `orbit_au > 0` and `star_mass_solar > 0` the full orbit placement pipeline runs.

**Hill sphere** caps the outer moon limit: `Hill_AU = orbit_au × (1 − ecc) × ∛(mass_earth × 3e-6 / (3 × star_mass_solar))`, converted to PD by dividing by planet diameter. The practical moon limit is `floor(Hill_PD / 2)`.

**Moon removal:** if the moon limit is < 1 PD, no moons or rings survive; if 1 PD, significant moons are converted to a ring.

**Moon Orbit Range** = `Moon Limit − 2` (capped at `200 + n_moons`). Each moon rolls independently on the Inner/Middle/Outer table (DM+1 when MOR < 60), PDs are sorted ascending (closest-first), and adjacent collisions are resolved by bumping the outer moon out 1 PD.

**Orbital period** in hours: `√(orbit_km³ / mass_earth) / 361730`.

**Ring placement:** centre = `0.4 + roll(2)/8` PD, span = `roll(3)/100 + 0.07` PD; inner edge clamped ≥ 0.55 PD.

For secondary worlds (no `WorldPhysical`), mass and diameter are estimated from size code. For the mainworld, `WorldPhysical.diameter_km` and `WorldPhysical.mass` are used directly. `attach_detail()` and `_moons_for()` automatically pass orbit data to `generate_moons()`.

Moon orbit eccentricity and retrograde direction (WBH p.76) are deferred; the fields exist on `Moon` but default to 0.0/False.

22 new tests in `tests/test_moon_gen.py`; **1036 tests** pass.

---

### Tidal Lock Eccentricity DM (Session 50, WBH p.105)

The eccentricity DM for the Tidal Lock Status table is now applied. WBH p.105 specifies this as a general DM for all cases: when `eccentricity > 0.1`, apply `DM − floor(eccentricity × 10)`. Examples: e=0.25 → DM−2; e=0.50 → DM−5; e=0.999 → DM−9.

`_tidal_lock_dm()` gains `orbit_eccentricity: float = 0.0` as a new parameter; threaded through `_roll_tidal_lock_status()` and into `generate_world_physical()` (which already accepted `orbit_eccentricity` since Session 44). No seed disruption when `orbital_eccentricity=False` (default) — the parameter defaults to 0.0 and applies no DM. When the flag is True, tidal lock outcomes for worlds with `eccentricity > 0.1` will shift (fewer locks for eccentric orbits).

The stale "Orbital eccentricity" entry has been removed from `context/deferred-features.md` — that feature was fully implemented across Sessions 43 (orbital eccentricity rolls) and 48 (anomalous orbit DMs).

6 new tests in `TestTidalLockEccentricityDm`; **1014 tests** pass.

---

### System JSON HTML Renderer (Session 49)

New standalone script `render_system_json.py` reads any system JSON file produced by `TravellerSystem.to_dict()` and renders it as a rich, self-contained HTML document. No project module imports are required — the script uses Python stdlib only (`json`, `sys`, `html`, `pathlib`).

**Usage:**
```bash
python render_system_json.py system.json [output.html]
```
Output defaults to `<input-stem>.html` in the same directory.

**Rendered sections:**
- System header (name, age, star count, seed, mainworld UWP)
- Stars table (designation, type, mass, temperature, diameter, luminosity, orbit, period)
- Habitable zones summary (per star: HZ range, MAO, temperature zone)
- World count chips (gas giants, belts, terrestrials, total, empty)
- Orbital survey table — 11 columns: Star, #, Orbit#, AU, Period, Ecc/Incl, Type, Profile, Codes, Zone, Notes; moon sub-rows when `attach_detail()` has been called
- Mainworld panel: 11-cell stats grid, trade code badges, World Body card (WorldPhysical or BeltPhysical), atmosphere detail card (profile, pressure, O₂, scale height, taints, gas mix, altitude bands), hydrographic detail card, notes
- Raw JSON collapsible `<details>` block

Distinguishes `WorldPhysical` vs `BeltPhysical` by checking for `"composition"` key. CSS matches the existing `to_html()` design: CSS variables, dark mode, colour-coded temperature zones, trade code badges. Pylint 10.00/10.

Sample output: `examples/system_seed42.html` (seed=42, 3-star system named Aramis, mainworld UWP D200000-0, full eccentricity + inclination).

---

### Orbital Inclination (Session 46, issue #59)

WBH p.28 orbital inclination is now implemented as an optional gated feature using the same pattern as orbital eccentricity.

**`_roll_inclination()`** uses a 6-row severity table (2D ≤ 6 = Very Low through 2D = 11 = Extreme), each with a different degree formula, plus a recursive retrograde case (2D = 12 → `180 − re-roll`). Anomalous orbits already typed as `"inclined"` are skipped (their angle is stored in `notes`).

**New fields:**
- `OrbitSlot.inclination: float = 0.0` — `to_dict()` emits `"inclination"` (2 d.p.) when > 0
- `Star.orbit_inclination: float = 0.0` — `to_dict()` emits `"orbit_inclination"` when > 0
- `TravellerSystem.orbital_inclination: bool = False`

**API:** `parse_orbital_inclination()` added to `shared/helpers.py`; wired through all 5 system endpoints.

**Display:** The "Ecc" column is renamed **"Ecc/Incl"** in both gen-ui and HTML. When both are set, the cell shows `0.123/45.0°`; when only one is set, the other shows `—`; when neither is set, the cell shows just `—`.

**gen-ui:** "Orbital Inclination" checkbox added (enabled only when "System detail" is checked). When False (default), no dice fire — no seed disruption.

---

### Orbital Eccentricity Display Column (Session 44 cont.)

The inline `(e=X.XXX)` text formerly embedded in the AU cell of both the gen-ui System Orbits card and the `to_html()` orbit table has been replaced with a dedicated right-aligned **Ecc** column inserted after **AU**.

- Shows `0.350` (3 d.p.) when `OrbitSlot.eccentricity > 0`; `—` otherwise
- gen-ui detail_attached variant: 11 columns — `Star | Orbit# | AU | Ecc | Type | Profile | Codes | HZ | Zone | Period | Notes`; `right_cols={1,2,3,9}`
- gen-ui non-attached variant: 9 columns — `Star | Orbit# | AU | Ecc | Type | HZ | Zone | Period | Notes`; `right_cols={1,2,3,7}`
- HTML table: `<th>Ecc</th>` added after `<th>AU</th>`; moon sub-row `colspan` widened from 3 → 4
- System map SVG retains the inline `(e=0.35)` in the AU text column (no SVG layout change)

A missing **"Orbital Eccentricity"** checkbox was also added to the gen-ui toolbar row (alongside "NHZ Atmospheres", enabled only when "System detail" is checked). Without this checkbox, `generate_full_system()` was always called with `orbital_eccentricity=False`, leaving every `OrbitSlot.eccentricity` at 0.0 and the Ecc column always showing `—`.

---

### 1:1 Tidal Lock Axial Tilt & Eccentricity (Session 44, issue #10)

WBH p.77 Rules 3 and 4 for 1:1 tidal lock interactions are now implemented.

**Rule 3 — Axial tilt recomputed with 1D on Axial Tilt table.** Previously the 1:1 lock path used `(2D-2)/10` with a `> 3.0` guard (incorrect). New helper `_roll_axial_tilt_1d()` rolls 1D to select the outer band of the Axial Tilt table (the same 6 rows as `_roll_axial_tilt()`), then 1D within the band. The recompute is unconditional — any initial axial tilt is replaced.

**Rule 4 — Eccentricity reduction.** `generate_world_physical()` gains an `orbit_eccentricity: float = 0.0` parameter. When a world reaches 1:1 lock and `orbit_eccentricity > 0.1`, `_reroll_eccentricity_tidal()` re-rolls with DM-2 (using `_ECC_TABLE_PHYS`, an inline copy of the eccentricity table to avoid circular imports). The lower value is stored in new `WorldPhysical.eccentricity_adjusted` (`Optional[float]`, `init=False`). `_attach_mainworld_physical()` in `function_app.py` reads this field and writes it back to the orbit slot, updating the eccentricity that appears in JSON output and system maps.

**Seed impact:** The axial tilt change is seed-breaking for 1:1 locked worlds (same dice count, different interpretation). Eccentricity path only fires for locked worlds with `eccentricity > 0.1` when the orbital eccentricity feature flag is enabled.

---

### Orbital Eccentricity (Session 43, issue #57)

WBH p.27 orbital eccentricity is now implemented as an optional feature gated on `orbital_eccentricity=False`.

**Roll mechanic:** Two dice rolls per orbit. A first `2D+DM` selects a row in the six-row Eccentricity Values table; a second `1D` or `2D` roll divided by a row-specific divisor gives the fractional part. Final value is clamped to [0.000, 0.999].

**DMs (first roll only):**

| Condition | DM |
|---|---|
| Star eccentricities | +2 |
| Each close/near/far star with orbit# < slot (primary slots) | +1 per star |
| Orbit# < 1.0 and system age > 1 Gyr | −1 |
| Belt slot | +1 |

**Min/Max separation:** `AU × (1 − eccentricity)` and `AU × (1 + eccentricity)`

**New fields:**
- `OrbitSlot.eccentricity: float` — `field(default=0.0, init=False)`; `to_dict()` emits `"eccentricity"`, `"orbit_au_min"`, `"orbit_au_max"` when non-zero
- `Star.orbit_eccentricity: float = 0.0` — set for secondary stars by `generate_orbits()`; `to_dict()` emits when non-zero

**Flag plumbing:** `orbital_eccentricity` parameter added to `generate_orbits()`, `generate_full_system()`, `generate_system_from_world()`, and all relevant API endpoints. New `parse_orbital_eccentricity()` helper in `shared/helpers.py` reads the query parameter.

**Display:** System map AU text shows `1.234 (e=0.35)` inline when eccentricity > 0. gen-ui System Orbits card and `to_html()` orbit table each have a dedicated `Ecc` column (see above).

**Seed impact:** Flag False (default) → no new dice, no seed disruption. Flag True → seed-breaking (2 rolls per non-empty slot + 2 per secondary star).

---

### Orbit Notes Column (Session 41 cont.)

`OrbitSlot.notes` is now surfaced in every output that displays the orbit table:

- **gen-ui** — System Orbits card gains a trailing `Notes` column in both header variants: 10 columns (detail attached: `Star | Orbit# | AU | Type | Profile | Codes | HZ | Zone | Period | Notes`) and 8 columns (no detail: `Star | Orbit# | AU | Type | HZ | Zone | Period | Notes`).
- **`TravellerSystem.to_html()`** — orbit table notes cell now uses a `note_parts` list that combines the `"← mainworld"` marker with `OrbitSlot.notes`, showing all notes unconditionally for every orbit row (HZ placement notes, anomaly type notes, etc.).

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

### System Map — Column Label Sub-header Row (Session 39)

The orbit table in every system map now displays a column label row (`#  Orbit#  AU  Type  Profile  Codes  Zone ♦`) between the star header and the first world row. `Zone ♦` makes explicit that the last column shows both the temperature zone and moon count. `_TBL_ROW0_OFF` bumped from 38 to 50 px to accommodate the new row.

---

### Primary Star Outer Zone Placement (Session 39)

Primary stars in binary systems now populate the outer zone `[companion + 3.0, 17.0]` as well as the inner zone `[MAO, companion − 1.0]`. Previously all primary worlds were placed in the inner zone; the outer zone was unused.

A `star_outer` dict tracks the outer zone bounds. `_avail_range()` includes the outer range in proportional world allocation across stars. The placement loop wraps in a `for zone in zones` iterator that runs once per zone (inner, then outer), keeping the existing baseline → spread → slot logic unchanged within each pass.

Seed-breaking for any primary star that has a close/near/far companion with a valid inner zone.

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

### Hydrographic Detail (Session 37)

New module `traveller_hydro_detail.py` implements WBH p.93 surface liquid percentages.

`HydrographicDetail` dataclass carries `surface_liquid_pct` (a flat random value within the WBH code range). `generate_hydrographic_detail()` is called from the shared section of `traveller_system_gen.py` and all API handlers. Exposed in:
- **JSON** — `hydrographics.detail.surface_liquid_pct`
- **HTML** — Hydrographic Detail inner-card in `World.to_html()`, `TravellerSystem.to_html()`, and `World.summary()`
- **gen-ui** — `_build_hydrographic_card()`

---

## Bug Fixes

### JSON Schema Missing `eccentricity_adjusted` Property (Session 49)

`WorldPhysical.to_dict()` emits `eccentricity_adjusted` when `tidal_status == "1:1_lock"` and
`orbit_eccentricity > 0.1` (WBH p.77 Rule 4), but the property was absent from the
`WorldPhysical` branch of `traveller_world_schema.json`. Validation with `jsonschema.validate()`
failed for any such world with the error "is not valid under any of the given schemas ['size_detail']"
(due to `"additionalProperties": false`).

Fix: `eccentricity_adjusted` added as an optional `number` property (`minimum: 0`, `maximum: 0.999`)
to `size_detail.oneOf[0].properties` (the `WorldPhysical` branch). No code change — the schema was
the only gap. The case is rare (requires 1:1 lock **and** `eccentricity > 0.1`), which is why it
was not caught by the existing 200-seed validation sweep in the test suite.

---

### Anomalous Orbit Eccentricity DMs Not Applied (Session 48, issue #64)

WBH pp.49-50 specifies DMs on the Eccentricity Values table for anomalous orbit types.
These DMs were silently ignored — all anomalous orbits used the base table.

| Anomaly type | WBH DM | Was applied |
|---|---|---|
| Random | +2 | No |
| Eccentric | +5 | No |
| Inclined | +2 | No |
| Retrograde | +2 | No |

Fix: added `_ANOM_ECC_DM` lookup dict and `anomaly_dm: int = 0` parameter to
`_roll_eccentricity()`. The eccentricity pass in `generate_orbits()` now passes
`anomaly_dm=_ANOM_ECC_DM.get(o.anomaly_type, 0)` for each orbit slot. No seed
disruption for systems without anomalous orbits. 6 regression tests added
(`TestAnomalyEccentricityDMs`); 1008 tests pass.

---

### Orbital Flags Not Wired Through TravellerMap Endpoints (Session 47, issue #63)

`orbital_eccentricity` and `orbital_inclination` parameters were silently ignored on both `/api/map/system` and `/api/map/system/{name}`. Three layers all missed the flags:

1. `generate_system_from_map()` called `generate_orbits(stellar)` with no keyword arguments and did not accept the flags at all.
2. The shared `_map_system_response()` helper had no `want_ecc` / `want_incl` parameters.
3. Neither endpoint handler called `parse_orbital_eccentricity()` or `parse_orbital_inclination()`.

A fourth gap in gen-ui was also found: `_do_travellermap_generation()` and both its call sites were not forwarding checkbox state.

Fix: flags added to `generate_system_from_map()` signature and threaded into `generate_orbits()` and the `TravellerSystem` constructor. Both `_map_system_response()` and the two endpoint handlers updated to parse and forward the flags. gen-ui call sites updated. 4 regression tests added (`TestGenerateSystemFromMapOrbitalFlags`); 1002 tests pass.

---

### JSON Unicode Error on Windows (Session 45, issue #60)

`open(schema_path)` in `tests/test_traveller_world_gen.py` was called without `encoding="utf-8"`. On Windows, Python defaults to the system codepage (cp1252), which cannot decode the non-ASCII characters in `traveller_world_schema.json` (e.g. `–` U+2013, `…` U+2026). Fixed to `open(schema_path, encoding="utf-8")`, matching the pattern used elsewhere in the test file.

---

### Virtual Environment Consolidated (Session 45, issues #61 and #62)

The dual-environment setup (`.venv` for Azure Functions, `.venv-1` for PySide6/gen-ui) has been replaced by a single `.venv` that contains all dependencies.

- `requirements-dev.txt` added for pytest and pylint
- Install scripts (`install.sh`, `install.ps1`, `install.bat`) now install all three requirements files in one pass and activate the venv at the end
- All `.vscode/settings.json`, `docs/VSCODE.md`, `docs/developer-guide.md`, `docs/uat-plan.md`, and `gen-ui/README.md` updated from `.venv-1` to `.venv`

---

### Incorrect Belt Counts for Fetched Mainworlds (Session 42, issue #52)

Two bugs in `traveller_map_fetch.py` caused the belt count shown in the orbit table to differ from the canonical PBG value on TravellerMap.

**Bug 1 — Pool truncation always dropped belts.** `_reconcile_orbit_types()` built the redistribution pool as `["gas_giant"] * canonical_gg + ["belt"] * canonical_belt` and truncated with `pool[:n]` before shuffling. Because gas giants are at the front of the pool, all GGs were preserved and only belts were dropped when there were too few available orbit slots. Fix: when `canonical_gg + canonical_belt > n`, empty orbit slots are now promoted to world slots before distribution, ensuring the canonical counts are always honoured.

**Bug 2 — Mainworld belt double-counted.** The WBH PBG convention (confirmed at `generate_belt_count()` line 2611) includes the mainworld in the belt count when the mainworld is Size 0. `_reconcile_orbit_types()` was distributing the full `canonical_belt` count among non-mainworld slots, and Step 6 then separately set the mainworld slot to `"belt"`, producing `canonical_belt + 1` total belts. Fix: `generate_system_from_map()` now subtracts 1 from `canonical_belt` before calling `_reconcile_orbit_types()` when `world.size == 0`.

---

### Companion Star Exclusion Zone (Session 39)

When a companion orbit# was less than 1.0, `excl = companion_orbit − 1.0` was ≤ 0 and never triggered the `max_o` cap, allowing primary worlds inside the WBH exclusion band `[companion − 1, companion + 3]`. Fixed: an `else` branch now pushes `mao = max(mao, companion_orbit + 3.0)` and syncs `star_mao[designation]` in-place.

`system_map.py` extended to render companion star rows inside the primary star's orbit-table section, sorted by orbit number.

---

### H/L Oxygen Taint Validation (Session 37, issue #55)

`_roll_single_taint()` now accepts `ppo: Optional[float]` and rerolls High Oxygen (H) results unless `ppo > 0.5 bar`, and Low Oxygen (L) results unless `ppo < 0.1 bar`. The `ppo` computation was moved before the taint block in `generate_atmosphere_detail()` so it is available at taint time. Seed-breaking for tainted atmosphere codes.

---

### System HTML Missing Mainworld Detail (Session 36, issue #51)

`TravellerSystem.to_html()` was omitting the `WorldPhysical` and atmosphere detail inner-cards from the mainworld panel — only `BeltPhysical` was handled. Added `.inner-card`, `.inner-lbl`, `.drow`, `.dlbl` CSS; `drow()` helper; and imports for `WorldPhysical`, `TIDAL_STATUS_LABELS`, and `format_atmosphere_profile()`.

### TravellerMap Fetch Incomplete Atmosphere Pipeline (Session 36, issue #51)

`generate_system_from_map()` was not calling `generate_gas_mix()` or `generate_unusual_subtype()` after `generate_atmosphere_detail()`, leaving gas composition and unusual subtypes absent for TravellerMap-fetched worlds. Also threaded `hz_deviation` into `generate_atmosphere_detail()` for orbit-position DMs. Both calls now follow the same pipeline as procedurally generated worlds.

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
| Incorrect belt counts for fetched mainworlds (issue #52) | +4 |
| Orbital eccentricity (issue #57) | +6 |
| Orbital inclination (issue #59) | +8 |
| TravellerMap orbital flag wiring (issue #63) | +4 |
| Anomalous orbit eccentricity DMs (issue #64) | +6 |
| Moon orbit placement (issue #16) | +22 |
| Moon quantity adjacency DMs (issue #14) | +8 |
| Moon tidal lock DMs and planet-to-moon lock (issue #11) | +24 |
| **Total new tests** | **+167** |
| **Suite total** | **1068** |

All 1068 tests pass. Pylint 10.00/10 on all core generation modules.

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
