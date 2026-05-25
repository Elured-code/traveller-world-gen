# system-world.md — traveller_system_gen.py, traveller_world_gen.py, traveller_world_physical.py

Read this when working on system integration, mainworld generation, temperature
derivation from orbital position, physical characteristics, or any code that
bridges the stellar/orbit layer and the world layer.

See `context/data-structures.md` for `TravellerSystem`, `World`, and
`WorldPhysical` dataclass definitions.  
See `context/generation-pipeline.md` for the full pipeline and RNG rules.

---

## traveller_system_gen.py — Integration layer

### Public API

```python
system: TravellerSystem = generate_full_system(
    name: str = "Unknown",
    seed: Optional[int] = None,
    nhz_atmospheres: bool = False,  # Session 38: use WBH NHZ tables for out-of-HZ worlds
) -> TravellerSystem

system: TravellerSystem = generate_system_from_world(
    world: World,
    seed: Optional[int] = None,
) -> TravellerSystem
# Generates fresh stellar data and orbits around an existing World.
# Preserves UWP and PBG; recalculates temperature from assigned orbital position.
# Stamps canonical_profile on the mainworld orbit slot.
```

### Temperature integration — critical link

Rather than rolling temperature randomly (the standalone CRB procedure),
`generate_temperature_from_orbit()` converts an orbit's HZ deviation to the raw
2D roll that the CRB temperature table expects, then applies atmosphere DMs.

```python
raw: int = hz_deviation_to_raw_roll(deviation: float) -> int
temp: str = generate_temperature_from_orbit(
    atmosphere: int,
    hz_deviation: float,
    hzco: float,
    orbit: float,
) -> str
```

| Raw 2D roll | HZ deviation     | Zone      |
|-------------|------------------|-----------|
| 2−          | +1.1 or more     | Frozen    |
| 3           | +1.00            | Cold      |
| 4           | +0.50            | Cold      |
| 5           | +0.20 to +0.49   | Temperate |
| 6–9         | −0.20 to +0.19   | Temperate |
| 10          | −0.50 to −0.21   | Hot       |
| 11          | −1.00            | Hot       |
| 12+         | −1.1 or less     | Boiling   |

This same function is used for **all** secondary worlds and moons — temperature
is always derived from the parent orbit's HZ deviation, never rolled
independently.

**No deviation scaling.** Earlier versions applied a scaling formula
`eff_dev = dev / min(hzco, orbit)` for sub-Orbit#1 positions. This was a
compliance bug (Session 12) that produced 58% Frozen results for dim M-type
star HZ worlds. The WBH HZ Regions table is applied directly to the unscaled
deviation.

### Gas giant mainworld (WBH p.57)

When the selected mainworld orbit is a gas giant, `generate_mainworld_at_orbit()`
generates the mainworld as a **satellite** of that giant, not the giant itself.

- `_gg_diameter(gg_sah: str) -> int` — decodes the eHex diameter digit from the
  gas giant's `gg_sah` string (e.g. `"GM9"` → 9 Terran diameters).
- Satellite size is clamped to `min(max(generate_size(), 1), gg_diameter - 1)`.
- A note recording the host giant's SAH and orbital position is appended to
  `world.notes`.
- The `gg_sah` value was rolled at orbit-gen time and stored in
  `OrbitSlot.gg_sah` — there is **no second SAH roll** here.

### Belt mainworld override

The CRB mainworld generator is orbit-agnostic. When `orbit.world_type == "belt"`,
`generate_mainworld_at_orbit()` forces `size=0`, `atm=0`, `hydro=0`. This is
why the `As` (Asteroid) trade code fires correctly on belt mainworlds.

### `canonical_profile` display priority

For TravellerMap mainworld orbit slots, `canonical_profile` takes display
priority over `WorldDetail.profile`. Without this, an uninhabited mainworld
(population = 0) would display as `Y{SAH}000-0` rather than its true UWP.

### HTML rendering — Jinja2 templates (Session 53, issue #40)

Both `World.to_html()` and `TravellerSystem.to_html()` now delegate to Jinja2
templates via `html_render.render(template_name, **context)` in `html_render.py`.

**Templates** (in `templates/`):

| Template | Used by |
|----------|---------|
| `world_card.html` | `World.to_html()` |
| `world_list.html` | multi-world CLI `--html` output |
| `system_card.html` | `TravellerSystem.to_html()` |

**`html_render.py`** — thin module-level `jinja2.Environment` with
`autoescape=True` and `FileSystemLoader` pointing at `templates/`.
Single public function `render(template_name, **context) -> str`.

**`_world_html_ctx(world: "World") -> dict`** — module-level helper in
`traveller_world_gen.py` (between the `World` class and generation functions).
Pre-computes every display value (zone badge, TL era, starport labels, formatted
sizes, trade code full labels, belt/world physical flag, tidal label, JSON dump,
etc.) and returns a single flat dict. Used by both `World.to_html()` and the
multi-world CLI path.  Has `# pylint: disable=too-many-locals,protected-access`
(the protected-access is for `World._tl_era` / `World._tl_era_css`, accessed
within the same module).

**Multi-world CLI fix:** the previous regex-based HTML stitching of multiple
`to_html()` outputs was replaced with `render("world_list.html", worlds=[...])`.

**`requirements.txt`** gains `Jinja2>=3.1.0`.

The system card still renders the same mainworld detail sections:
- **`WorldPhysical`** — composition, diameter, density, mass, gravity, escape
  velocity, axial tilt, day length, mean temperature (K, when hz_deviation available),
  tidal status.
- **Atmosphere detail** — profile, pressure, O₂ ppo, scale height, altitude,
  unusual subtypes, taints, hazards, gas mix.
- **Hydrographic detail** — surface liquid percentage.
- **`BeltPhysical`** — belt span, composition, bulk, resource rating, bodies.

---

## traveller_world_gen.py — CRB pp. 248–261

### Public API

```python
world: World = generate_world(name: str = "Unknown") -> World
```

Individual step functions (also used by `traveller_system_gen.py`):

```python
size: int        = generate_size()
atm: int         = generate_atmosphere(size)
atm, exotic_key  = generate_nhz_atmosphere(size, hz_deviation)  # Session 38: NHZ alternative
temp: str        = generate_temperature(atmosphere)     # standalone random roll
detail: AtmosphereDetail = generate_atmosphere_detail(
    atm, size, system_age_gyr, temp,
    hz_deviation=None, exotic_key_override=None,  # exotic_key_override: Session 38
)
hydro: int       = generate_hydrographics(size, atm, temp)
pop: int         = generate_population()
gov: int         = generate_government(population)
law: int         = generate_law_level(government)
port: str        = generate_starport(population)
tl: int          = generate_tech_level(starport, size, atm, hydro, pop, gov)
bases: List[str] = generate_bases(starport, tl, pop, law)
codes: List[str] = assign_trade_codes(size, atm, hydro, pop, gov, law, tl)
zone: str        = assign_travel_zone(atm, gov, law)
```

When called from `generate_mainworld_at_orbit()`, `generate_temperature` is
bypassed and the orbit-derived temperature is injected instead.

### Atmosphere detail helpers (WBH pp. 78–95, Sessions 31–34)

```python
detail = generate_atmosphere_detail(code, size, system_age_gyr=None,
                                     temperature=None, hz_deviation=None,
                                     exotic_key_override=None)
# Returns AtmosphereDetail. For standard codes: pressure_bar, oxygen_partial_pressure,
# scale_height_km (each Optional[float]). For tainted codes (2,4,7,9): also taints.
# For codes 10/A (Exotic), 11/B (Corrosive), 12/C (Insidious): also subtype_code,
# subtype_name, pressure (from subtype roll). For code 12 only: also hazards list.
# Unbound-pressure subtypes (C/D/E) store pressure_bar=None; display as "> 10.0 bar".
# For codes 16/17 (Gas Helium/Hydrogen — NHZ only): returns empty AtmosphereDetail.
#
# `hz_deviation` drives orbit-position DMs on the subtype tables.
# Pass orbit.hz_deviation; standalone worlds pass None.
# `exotic_key_override` bypasses _roll_exotic_subtype() for NHZ exotic worlds:
# pass the key returned by generate_nhz_atmosphere() directly.

generate_gas_mix(detail, atm_code, size, temperature, hz_deviation, hydro)
# No-op for codes outside {10, 11, 12}. Mutates detail.gas_mix in-place.
# MUST be called AFTER hydrographics is set (CO* footnote substitution needs hydro).
# Rolls primary + secondary gas from one of 7 temperature-banded tables (WBH pp.95+).
# Table selected by temperature category string + hz_deviation (Boiling splits at
# -2.01; Frozen splits at +3.01). CO* → CO₂ (non-frozen, hydro>0) or N₂ (frozen,
# hydro>0). Gas mix is omitted for standalone worlds (generate_world() path).

generate_unusual_subtype(detail, atm_code, size, hydro)
# No-op for codes other than 15 (F). Mutates detail.unusual_subtypes in-place.
# MUST be called AFTER hydrographics is set (Panthalassic/Steam prerequisites need hydro).
# Rolls D26 subtype from a 12-entry table; rerolls if Layered/Panthalassic/Steam
# prerequisites are not met. Combination result (D26=25) produces two non-combination
# subtypes. Call immediately after generate_gas_mix() at all three call sites in
# traveller_system_gen.py, four mainworld handlers + batch in function_app.py,
# and both _finish_generation paths in gen-ui/app.py.

profile = format_atmosphere_profile(code, detail)
# Returns the WBH p.82 profile string, e.g. "6-1.013-0.212" for Terra,
# "0" for vacuum. For codes 10/11/12 with gas_mix populated, gas codes
# are appended as :code-## tokens, e.g. "A-St4-0.55:N₂-75:CO₂-20-P.7.9".
# For tainted codes: taint suffix appended as -T.S.P per taint.
# For code 15 (F): short-circuits to "F-S{subtype_codes}" e.g. "F-S5" or "F-S3.7".
```

### NHZ Atmosphere generation (Session 38)

```python
atm_code, exotic_key = generate_nhz_atmosphere(size: int, hz_deviation: float) -> tuple
```

Replaces `generate_atmosphere()` for worlds outside the HZ.  Caller is
responsible for checking `abs(hz_deviation) > 1.0`.  Returns
`(atm_code, exotic_key)` where `exotic_key` is a `_EXOTIC_SUBTYPE_TABLE`
key (only when `atm_code == 10`); `None` otherwise.

Table column selection:
- `hz_deviation ≤ -2.01` → `_NHZ_HOT_A`
- `-2.0 to -1.01` → `_NHZ_HOT_B`
- `+1.01 to +3.0` → `_NHZ_COLD_A`
- `≥ +3.01` → `_NHZ_COLD_B`

New atmosphere codes produced by NHZ tables: 16 ("Gas, Helium", eHex G) and
17 ("Gas, Hydrogen", eHex H).  Both return an empty `AtmosphereDetail` from
`generate_atmosphere_detail()` and force `generate_hydrographics()` to 0.

The `star` flag in a table entry triggers an irritant roll (1D ≥ 4);
the `dagger` flag adds DM+1 to that roll when `hz_deviation ≤ -3.0`.

Constants exported for tests and downstream callers:
- `ATMOSPHERE_PRESSURE_SPAN_BAR` — `{code: (min_bar, span_bar)}` for codes
  1, 2-9, 13 (D), 14 (E). Codes 0, 10-12 (A/B/C), 15 (F), 16-17 (G/H)
  have no defined span.
- `SIZE_GRAVITY_G` — Size-to-gravity-in-G dict, same values already used
  by `World.to_dict()`. Powers the scale-height approximation.
- `_dice(n)` — unclamped `sum(random.randint(1, 6) for _ in range(n))`.
  Use this instead of `roll()` for formulas where a negative variance
  term is legitimate, e.g. the WBH p.80 `(2D-7)/100` term.

Orchestrator hook: `generate_mainworld_at_orbit()` takes `system_age_gyr`
and threads `stellar.age_gyr` from `generate_full_system()` so the WBH
p.80 DM+1 fires on systems older than 4 Gyr.

### `World.from_dict(d)`

Reconstructs a `World` from the dict produced by `to_dict()`. Handles both the
nested form (`starport: {code: "A", ...}`) and flat forms where the value is the
code directly. Missing fields receive safe defaults. Used by
`generate_system_from_world()` and the `/api/system/from-world` endpoint.

### Ag trade code criteria (CRB p.260)

The correct criteria are:
- `4 <= atmosphere <= 9`
- `4 <= hydrographics <= 8`
- `5 <= population <= 7`

There is **no size criterion**. An earlier version had wrong ranges and a missing
population check (compliance fix, Session 15). Do not add a size DM or extend
these ranges.

---

## traveller_world_physical.py — WBH pp. 74–77, 103

### Public API

```python
physical: Optional[WorldPhysical] = generate_world_physical(
    world: World,
    age_gyr: float = 0.0,              # system age for rotation rate and tidal DMs
    orbit_number: Optional[float] = None,  # WBH Orbit# for tidal lock DM
    orbit_au: Optional[float] = None,      # AU for orbital period calculation
    star_mass: Optional[float] = None,     # solar masses for tidal lock DM + period
    orbit_eccentricity: float = 0.0,       # current eccentricity; triggers Rule 4 if > 0.1
) -> Optional[WorldPhysical]
# Returns None for size 0 (belts). Size S/R not yet handled.
# Tidal lock check runs only when all three orbital parameters are non-None.
# If tidal_status == "1:1_lock" and orbit_eccentricity > 0.1:
#   WorldPhysical.eccentricity_adjusted = min(orbit_eccentricity, re-rolled with DM-2)
# NOTE: call apply_moon_tidal_effects() after moon generation to apply moon DMs.

apply_moon_tidal_effects(
    physical: WorldPhysical,
    moons: list,                       # list of Moon objects from generate_moons()
    world_size: int,
    world_atmosphere: int,
    age_gyr: float,
    orbit_number: float,
    orbit_au: float,
    star_mass: float,
    orbit_eccentricity: float = 0.0,
    num_stars_orbited: int = 1,
    is_moon: bool = False,             # True when mainworld is a satellite of a gas giant
    gg_mass_earth: float = 0.0,        # parent gas giant mass (M⊕); used for seismic stress
    gg_satellite_moon: Optional["Moon"] = None,  # the satellite Moon object when is_moon=True
) -> None
# Re-runs tidal lock check with moon data (skipped when moons is empty).
# Always computes seismic stress (RSS + Tidal SS + TSF) and tidal amplitude.
# Returns immediately (no-op) when physical is not a WorldPhysical instance (BeltPhysical guard).
# Mutates physical in-place. Must be called AFTER generate_moons() completes.
# Call sites: function_app._apply_mainworld_moon_tidal(), gen-ui _finish_system_generation().

generate_advanced_mean_temperature(
    physical: WorldPhysical,
    atmosphere: int,
    hydrographics: int,
    pressure_bar: Optional[float],     # None → 10.0 bar fallback (unbound-pressure subtypes)
    luminosity: float,                 # combined luminosity of stars interior to world's orbit (L☉)
    orbit_au: float,
    hz_deviation: float,
    orbit_eccentricity: float = 0.0,   # used for near/far AU in high/low temperature steps
    star_mass: float = 1.0,            # solar masses; used for orbital-period step 1 year test
) -> None
# Physics-based mean temperature: T = 279 × ⁴√(L × (1−A) × (1+G) / AU²) (WBH pp.47-48).
# Also computes high and low temperature via Steps 1-9 (WBH pp.48-50):
#   Step 1: axial_tilt_factor = sin(eff_tilt ∈ [0°,90°]); year<0.1 → ÷2; year>2.0 → +0.01×yr, cap 1.0
#   Step 2: rotation_factor = min(1.0, √|day_hours|/50); 1:1 lock → 1.0
#   Step 3: geographic_factor = (10−HYD)/20
#   Step 4: variance = clamp(atilt+rot+geo, 0, 1)
#   Step 5: atmospheric_factor = 1 + pressure_bar
#   Step 6: luminosity_modifier = variance / atmospheric_factor
#   Step 7: high_lum = L×(1+LM); low_lum = L×(1−LM)
#   Step 8: near_au = AU×(1−ecc); far_au = AU×(1+ecc)
#   Step 9: high_T / low_T = 279×⁴√(lum × common / au²)
# Rolls albedo and greenhouse factor, then computes all three temperatures.
# Sets physical.albedo, physical.greenhouse_factor, physical.advanced_mean_temperature_k,
#   physical.high_temperature_k, physical.low_temperature_k in-place.
# "Interior luminosity" = sum of luminosity for stars with orbit_au≤0 or orbit_au < mw_orbit_au.
# Temperature clamped to minimum 3K (CMB floor); 3K returned when orbit_au=0 or luminosity=0.
# BeltPhysical guard: returns immediately when physical is not a WorldPhysical instance.
# Call site: gen-ui _finish_system_generation() BEFORE _attach_detail() (inside if world is not None:
#   block) when _check_advanced_temp is checked. Must precede _attach_detail() so that
#   high_temperature_k and advanced_mean_temperature_k are set before _apply_biomass() reads them.
```

### Generation tables summary

| Step | WBH | Procedure |
|------|-----|-----------|
| Composition | p.75 | 2D + size DM → 5 categories (Heavy Iron Core / Dense Core / Standard / Low Density / Icy) |
| Density | p.75–76 | 1D → base + 1D × multiplier g/cm³ per composition category |
| Diameter | p.74 | Base = size × 1,600 km; variation = (2D−7) × 200 km |
| Derived | p.76–77 | D* = diameter/12742; ρ* = density/5.515; mass = D*³×ρ*; gravity = D*×ρ*; v_e = 11.186×√(gravity×D*) |
| Axial tilt | p.77 | 2D selects band (6 bands); 1D within band gives degrees; ≥10 triggers extreme sub-table (retrograde up to 180°) |
| Day length | p.103 | (2D−2)×4 + 2 + 1D + DMs; DM+1 per 2 full Gyrs of system age |

### Advanced temperature private helpers (Session 65, WBH pp.47-50)

```python
_roll_albedo(atmosphere, hydrographics, density, hz_deviation) -> float
# World type: rocky (density>0.5), icy (density≤0.5 & hz_deviation≤2.0),
#   icy-far (density≤0.5 & hz_deviation>2.0).
# Base roll per type + atmosphere-group modifier + hydrographics modifier.
# Clamped to [0.02, 0.98]. pylint: disable=too-many-branches.

_roll_greenhouse_factor(atmosphere, pressure_bar) -> float
# atm 0 → 0.0; initial = 0.5×√bar.
# _ATM_GH_STANDARD: +3D×0.01; _ATM_GH_EXOTIC: ×max(0.5,1D-1);
# _ATM_GH_EXTREME: ×1D (or ×3D on 6).

_axial_tilt_factor(axial_tilt, orbital_period_hours) -> float
# sin(eff_tilt) where eff_tilt = min(axial_tilt, 180-axial_tilt) capped at 90°.
# year = orbital_period_hours/8766; year<0.1 → factor÷2;
# year>2.0 → factor + min(0.01×year, 0.25), cap 1.0.

_rotation_factor(day_length, tidal_status) -> float
# 1:1_lock → 1.0; otherwise min(1.0, √|day_length|/50).

_geographic_factor(hydrographics) -> float
# (10 − hydrographics) / 20; result in [0.0, 0.5].
```

Atmosphere constant sets used in albedo and greenhouse calculations:
```python
_ATM_THIN   = {1, 2, 3, 14}
_ATM_MID    = {4, 5, 6, 7, 8, 9}
_ATM_VDENSE = {13}
_ATM_HEAVY  = {10, 11, 12, 15, 16, 17}
_ATM_GH_STANDARD = {1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14}
_ATM_GH_EXOTIC   = {10, 15}
_ATM_GH_EXTREME  = {11, 12, 16, 17}
```

### Axial tilt — extreme sub-table (implemented Session 25)

On a 2D roll of 10+, `_roll_extreme_axial_tilt()` is called. The 1D sub-table:

| 1D | Result | Range |
|----|--------|-------|
| 1–2 | 10 + 1D × 10 | 20–70° (high axial tilt) |
| 3 | 30 + 1D × 10 | 40–90° (extreme axial tilt) |
| 4 | 90 + 1D × 1D | 91–126° (retrograde rotation) |
| 5 | 180 − 1D × 1D | 144–179° (extreme retrograde) |
| 6 | 120 + 1D × 10 | 130–180° (extreme retrograde, high variance) |

Result is clamped to [0, 180]. Values above 90° represent retrograde rotation.

### Integration with `World.size_detail`

`World.size_detail` is `Optional[Union[WorldPhysical, BeltPhysical]] = field(default=None, init=False)`.
It is `None` unless `generate_world_physical()` (or `generate_belt_physical()`) is called and the result assigned.

- `World.to_dict()` includes a `"size_detail"` key if set; omits it if `None`.
- `World.to_html()` adds a "World Body" (or "Belt Body") inner card if set.
- `World.summary()` adds a "World body" section if set.

### Tidal lock status (WBH pp. 105–107) — implemented Session 27

After the basic rotation rate is rolled, `_roll_tidal_lock_status()` runs the
planet-to-star tidal lock check when `orbit_number`, `orbit_au`, and `star_mass`
are all provided. It rolls 2D + DM on the Tidal Lock Status table and returns the
final `(day_length, axial_tilt, tidal_status)` triple.

**DM sources:** General DMs (size, eccentricity, axial tilt, atmosphere pressure, system age) +
star-lock DMs (base −4, orbit# band, star mass band). See WBH pp. 105–106.

**Eccentricity DM (Session 50):** `e > 0.1 → DM − floor(e × 10)`. Passed from
`generate_world_physical()` through `_roll_tidal_lock_status()` into `_tidal_lock_dm()`
as `orbit_eccentricity: float = 0.0`. Default 0.0 means no effect when the
`orbital_eccentricity` flag is False.

**Moon-size DM (Session 52, WBH p.106):** `DM − total size of all significant moons (Size 1+, non-ring)`. Applied inside `_tidal_lock_dm()` via `moons` parameter. Only available after `apply_moon_tidal_effects()` is called.

**Multi-star DM (partially implemented, Session 52, WBH p.106):** `DM − number of stars orbited` when > 1. `_tidal_lock_dm()` has `num_stars_orbited: int = 1` parameter; currently always passed as 1 (full multi-star support deferred).

**Planet-to-moon lock (Session 52, WBH p.107):** `_planet_moon_lock_dm(moon, all_moons)` computes the DM for each qualifying moon (Size 1+, non-ring, orbit_pd not None). Base −10; +Moon Size; PD-range DMs; −2 per moon beyond the first. `_roll_tidal_lock_status()` assembles all lock candidates (star + each qualifying moon), sorts by highest DM (moon before star on tie), and cascades until a lock fires.

**Outcomes and `tidal_status` values:**

| 2D+DM | tidal_status | Effect on day_length |
|-------|-------------|----------------------|
| 2− | `"none"` | Unchanged |
| 3–6 | `"braking"` | Multiplied (×1.5 / ×2 / ×3 / ×5) |
| 7–8 | `"prograde"` | 1D × N × 24 h (slow prograde) |
| 9–10 | `"retrograde"` | 1D × N × 24 h; axial tilt → 180°−tilt if < 90° |
| 11 | `"3:2_lock"` | 2/3 × orbital period; axial tilt rerolled ((2D-2)/10) if > 3° |
| 12+ | `"1:1_lock"` | Orbital period; axial tilt rerolled via `_roll_axial_tilt_1d()` unconditionally; broken-lock check |

**Broken-lock check:** On 1:1 result, roll 2D — on a natural 12, reroll with DM=0
(no further broken-lock check on the reroll).

**1:1 lock axial tilt (WBH p.77 Rule 3, Session 44):** `_roll_axial_tilt_1d()` — roll 1D to
select the outer band of the Axial Tilt table (same 6 rows as `_roll_axial_tilt()`), then 1D
within that band. Always replaces the existing tilt (no `> 3.0` guard).

**1:1 lock eccentricity reduction (WBH p.77 Rule 4, Session 44):** When
`orbit_eccentricity > 0.1`, `_reroll_eccentricity_tidal()` re-rolls with DM-2 (using
`_ECC_TABLE_PHYS`, an inline copy of `_ECC_TABLE` from `traveller_orbit_gen.py`). The lower
value is stored in `WorldPhysical.eccentricity_adjusted`. `_attach_mainworld_physical()` in
`function_app.py` propagates this back to the orbit slot's `eccentricity` field.

**Remaining deferred:** Full multi-star DM support (num_stars_orbited > 1; requires counting stars orbited per world slot).

**Three-phase pipeline for moon DMs (Session 52):**
1. `generate_world_physical()` — runs without moon data (moon DMs default to zero)
2. `generate_moons()` — uses `WorldPhysical.diameter_km` and `WorldPhysical.mass` for Hill sphere
3. `apply_moon_tidal_effects()` — re-runs tidal lock with full moon list; mutates `WorldPhysical` in-place

**Call site pattern in `function_app.py`:**
```python
_attach_mainworld_physical(system)   # phase 1
if want_detail:
    attach_detail(system)            # phase 2 (includes moon generation)
    _apply_mainworld_moon_tidal(system)  # phase 3
```

---

## traveller_hydro_detail.py — WBH p.93

### Public API

```python
detail: Optional[HydrographicDetail] = generate_hydrographic_detail(
    hydrographics: int,
    size: int,
) -> Optional[HydrographicDetail]
# Returns None for size 0 (belt mainworlds) or hydro out of range [0,10].
# For hydro 10 with size > 9 (ocean world): always returns surface_liquid_pct=100.
# Otherwise rolls uniformly over _HYDRO_PCT_RANGE[hydrographics].
```

Call site: `generate_mainworld_at_orbit()` in the shared section (after the
gas-giant / terrestrial if/else branches, after `generate_unusual_subtype`,
before social rolls). This positions the single `random.randint` call at the
end of the physical pipeline, minimising seed disruption.

The call must also appear in `function_app.py` (four mainworld handlers + batch
loop), `traveller_map_fetch.py` (after `generate_unusual_subtype`), and both
`_finish_generation` paths in `gen-ui/app.py`. In gen-ui, wrap in
`if world.hydrographic_detail is None:` to avoid re-rolling worlds that were
already processed by the system pipeline.

Exported constants:
- `HydrographicDetail` — the dataclass
- `generate_hydrographic_detail` — the public function
- `_HYDRO_PCT_RANGE` — `{code: (low, high)}` for codes 0–10 (used by tests)

---

## Key design decisions (cross-cutting)

**Orbital temperature over random temperature.** All worlds derive temperature
from HZ deviation, not an independent dice roll. `generate_temperature_from_orbit()`
is the single source of truth.

**Secondary government defaults to dependent (Case 1).** The WBH offers two
procedures. Case 2 (independent, `2D-7 + Population`) is not yet implemented.

**`attach_detail()` is always a separate explicit step.** Never call it
automatically inside `generate_full_system()`.
