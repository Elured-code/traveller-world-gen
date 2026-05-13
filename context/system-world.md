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

### `TravellerSystem.to_html()` mainworld detail rendering (Session 36)

The system HTML builds a `mw_panel` for the mainworld section. As of Session 36
this panel renders both detail card types when present:

- **`WorldPhysical`** — an "inner-card" with composition, diameter, density, mass,
  gravity, escape velocity, axial tilt, day length, and tidal status rows.
- **Atmosphere detail** — an "inner-card" matching the cards in `World.to_html()`:
  profile, pressure, O₂ ppo, scale height, altitude, unusual subtypes, taints,
  hazards, gas mix.
- **`BeltPhysical`** — unchanged; rendered as a `.mw-grid` block (pre-existing).

The CSS classes `.inner-card`, `.inner-lbl`, `.drow`, `.dlbl` are defined in the
`<style>` block of `TravellerSystem.to_html()`. The helper `drow(label, value)`
generates a single detail row. `WorldPhysical`, `TIDAL_STATUS_LABELS`, and
`format_atmosphere_profile` are imported at module level.

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
temp: str        = generate_temperature(atmosphere)     # standalone random roll
detail: AtmosphereDetail = generate_atmosphere_detail(atm, size, system_age_gyr, temp)  # WBH pp. 78-82
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
                                     temperature=None, hz_deviation=None)
# Returns AtmosphereDetail. For standard codes: pressure_bar, oxygen_partial_pressure,
# scale_height_km (each Optional[float]). For tainted codes (2,4,7,9): also taints.
# For codes 10/A (Exotic), 11/B (Corrosive), 12/C (Insidious): also subtype_code,
# subtype_name, pressure (from subtype roll). For code 12 only: also hazards list.
# Unbound-pressure subtypes (C/D/E) store pressure_bar=None; display as "> 10.0 bar".
#
# `hz_deviation` drives orbit-position DMs on the subtype tables.
# Pass orbit.hz_deviation; standalone worlds pass None.

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
) -> Optional[WorldPhysical]
# Returns None for size 0 (belts). Size S/R not yet handled.
# Tidal lock check runs only when all three orbital parameters are non-None.
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

**DM sources:** General DMs (size, axial tilt, atmosphere pressure, system age) +
star-lock DMs (base −4, orbit# band, star mass band). See WBH pp. 105–106.

**Outcomes and `tidal_status` values:**

| 2D+DM | tidal_status | Effect on day_length |
|-------|-------------|----------------------|
| 2− | `"none"` | Unchanged |
| 3–6 | `"braking"` | Multiplied (×1.5 / ×2 / ×3 / ×5) |
| 7–8 | `"prograde"` | 1D × N × 24 h (slow prograde) |
| 9–10 | `"retrograde"` | 1D × N × 24 h; axial tilt → 180°−tilt if < 90° |
| 11 | `"3:2_lock"` | 2/3 × orbital period; axial tilt rerolled if > 3° |
| 12+ | `"1:1_lock"` | Orbital period; axial tilt rerolled if > 3°; broken-lock check |

**Broken-lock check:** On 1:1 result, roll 2D — on a natural 12, reroll with DM=0
(no further broken-lock check on the reroll).

**Deferred within tidal implementation:**
- Eccentricity DM (blocked by orbital eccentricity feature)
- Moon-size DM in star-lock check (blocked by moon orbital positions feature)
- Planet-orbits-multiple-stars DM (simplified to 1 star)
- Planet-locked-to-moon check (blocked by moon orbital positions feature)

**Call site in gen-ui (`_finish_system_generation`):**
```python
mw_orbit = system.mainworld_orbit
orbit_number = mw_orbit.orbit_number if mw_orbit is not None else None
orbit_au    = mw_orbit.orbit_au     if mw_orbit is not None else None
star_mass   = stars[0].mass         if stars else None
world.size_detail = generate_world_physical(world, age, orbit_number, orbit_au, star_mass)
```

---

## Key design decisions (cross-cutting)

**Orbital temperature over random temperature.** All worlds derive temperature
from HZ deviation, not an independent dice roll. `generate_temperature_from_orbit()`
is the single source of truth.

**Secondary government defaults to dependent (Case 1).** The WBH offers two
procedures. Case 2 (independent, `2D-7 + Population`) is not yet implemented.

**`attach_detail()` is always a separate explicit step.** Never call it
automatically inside `generate_full_system()`.
