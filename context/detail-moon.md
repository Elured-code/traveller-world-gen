# detail-moon.md — traveller_world_detail.py and traveller_moon_gen.py

Read this when working on secondary world generation, moon generation, the
`attach_detail()` pipeline, the gas giant orbit display logic, or tech level
viability checks.

See `context/data-structures.md` for `WorldDetail` and `Moon` dataclass
definitions and profile string formats.

---

## traveller_world_detail.py — Secondary world SAH/social detail

### Public API

```python
attach_detail(system: TravellerSystem) -> None
    # Populates orbit.detail (WorldDetail) on every OrbitSlot,
    # and moon.detail (WorldDetail) on every Moon in orbit.detail.moons.
    # Also generates BeltPhysical for belt mainworlds and sets both
    # system.mainworld.physical and system.mainworld_orbit.detail.physical.
    # Reads system.nhz_atmospheres and threads it through all secondary and
    # moon atmosphere generation (Session 38 cont.).

table: str = system_body_table(system: TravellerSystem) -> str
    # Formatted text table of all orbits and their moon sub-rows.

detail_map: dict = generate_system_detail(
    system: TravellerSystem,
    nhz_atmospheres: bool = False,   # Session 38 cont.
) -> dict
    # Returns {"{desig}-{slot_index}": WorldDetail} without attaching to slots.
    # Used for testing.
```

### Population cap

A system-wide secondary population cap is rolled once per system as
`mainworld.population - 1D`. If the result is ≤ 0, no secondaries or moons
are inhabited. This cap is shared across all secondary worlds and moons in the
same system.

### Tech Level viability

After any population roll, the minimal sustainable TL for that atmosphere code
is checked against the mainworld TL. If `minimal_tl(atm) > mainworld_tl`, the
world is forced uninhabited regardless of the population roll.

| Atmosphere | Minimal TL | Rationale |
|------------|-----------|-----------|
| 0, 1       | 8         | Vacc suits required |
| 2, 3       | 5         | Filter mask + cold gear |
| 4, 5       | 3         | Filter mask |
| 6–9        | 0         | No special equipment |
| A+         | 8         | Hostile environment suit |

**Belts** use atmosphere 0 for this check, so they are only inhabited when
the mainworld TL ≥ 8.

### Gas giant orbit detail

`attach_detail()` uses `orbit.gg_sah` (rolled at orbit-gen time) to set the
gas giant's profile. Do not re-roll the SAH — use `orbit.gg_sah` directly.

**If `orbit.gg_sah` is empty** (legacy data predating Session 13), a fresh SAH
is rolled as a fallback. This should not occur in newly generated systems.

### Gas giant mainworld orbit display (Session 24 fix)

When `attach_detail()` runs on a gas giant orbit that is the mainworld:

1. `orbit.detail` is built with `sah=orbit.gg_sah` (making `is_gas_giant=True`
   and `profile="GM7"` etc.)
2. The mainworld satellite is wrapped as `Moon(size_code=mw_size)` and inserted
   as `orbit.detail.moons[0]`, so it appears as a sub-row beneath the gas giant.

This ensures `orbit.detail.is_gas_giant == True` and the gas giant's own
profile is displayed — not the satellite's UWP. See also `_orbit_profile()` in
`gen-ui/app.py` and `to_html()` in `traveller_system_gen.py` (both have
complementary display-layer guards using `orbit.gg_sah` directly).

### Gas giants are never directly inhabited

Their moons can be. The gas giant SAH itself does not receive population, government,
law, or tech level.

---

## traveller_moon_gen.py — WBH pp. 55–57, 74–77

### Public API

```python
moons: List[Moon] = generate_moons(
    size_code: int | str,         # planet size (int 1–15, or "S")
    orbit_number: float,          # orbital Orbit# for DM check
    is_gas_giant: bool = False,
    gg_category: str = "M",       # "S", "M", or "L"
    gg_diameter: int = 8,         # Terran diameters, for moon size capping
    # Orbit placement parameters (all default 0.0 = skip placement):
    planet_diameter_km: float = 0.0,  # 0.0 → estimated from size_code
    planet_mass_earth: float = 0.0,   # 0.0 → estimated from size_code
    orbit_au: float = 0.0,
    star_mass_solar: float = 0.0,
    planet_ecc: float = 0.0,
) -> List[Moon]

display: str = moons_str(moons: List[Moon]) -> str
    # Compact string e.g. "R01, S, S, 3, 5"
```

When `orbit_au == 0.0` or `star_mass_solar == 0.0`, orbit placement is skipped
and all `Moon.orbit_pd` fields remain `None` (backwards-compatible).

### Quantity DM (Session 52, WBH p.56)

Four DM conditions are implemented; at most one applies per world (`DM-1 per dice`):

| Condition | Parameter | Source |
|-----------|-----------|--------|
| `orbit_number < 1.0` | (always checked) | built-in |
| Within companion star exclusion zone (orbit# ±1 to +3) | `companion_exclusion_zones: list[tuple[float,float]]` | `_moon_adjacency_context()` |
| Adjacent to host star MAO boundary (±1.0 of MAO orbit#) | `star_mao: float` | `_moon_adjacency_context()` |
| Adjacent to outermost Far-star slot (±1.0) | `is_adjacent_outermost_far: bool` | `_moon_adjacency_context()` |

`_moon_adjacency_context(orbit_number, star_designation, system_orbits, stellar_system)` in
`traveller_world_detail.py` computes all three context values by inspecting
`stellar_system.stars` (for companion exclusion zones and Far star orbits) and
`system_orbits.star_mao`. Returns a dict unpacked as `**ctx` into `generate_moons()`.

### Orbit placement (WBH pp.74–77, Session 51)

When orbit data is provided, `generate_moons()` runs a Hill sphere calculation
and places each significant moon at an orbital distance in Planetary Diameters (PD).

**Hill sphere** — outer limit on stable moon orbits:

```
Hill (AU)   = orbit_au × (1 − ecc) × ∛(mass_earth × 3e-6 / (3 × star_mass_solar))
Hill (PD)   = Hill_AU × 149,597,870.9 / planet_diameter_km
Moon Limit  = floor(Hill_PD / 2)
```

**Roche limit** — simplified constant 2 PD (WBH p.75).

**Moon removal rules:**

| Moon Limit (PD) | Action |
|-----------------|--------|
| < 1 (floor < 1) | No moons; no rings — return `[]` |
| 1 (floor = 1)   | No significant moons; first moon converted to ring (or existing ring kept) |
| ≥ 2             | Normal placement |

**Moon Orbit Range (MOR):**

```
MOR = Moon Limit − 2
if MOR > 200: MOR = min(MOR, 200 + n_moons)
```

**Orbit PD rolling** — `_roll_moon_pd(mor)`:

| 1D + DM | Range  | PD formula |
|---------|--------|------------|
| 1–3     | inner  | `(2D−2) × MOR / 60 + 2` |
| 4–5     | middle | `(2D−2) × MOR / 30 + MOR / 6 + 3` |
| 6+      | outer  | `(2D−2) × MOR / 20 + MOR / 2 + 4` |

DM+1 on the 1D roll when MOR < 60. PD values are sorted ascending and
assigned closest-first. Collision resolution: if two adjacent moons have
the same orbit PD, the outer is pushed out by 1 PD.

**Period formula (WBH p.76):**

```
orbit_km          = orbit_pd × planet_diameter_km
orbit_period_hours = √(orbit_km³ / mass_earth) / 361730
```

**Ring placement (WBH p.77):**

```
ring_centre_pd = 0.4 + roll(2) / 8       # roll(2) = 2D total
ring_span_pd   = roll(3) / 100 + 0.07    # roll(3) = 3D total
```
Inner edge clamped: if `centre − span/2 < 0.55`, centre is shifted outward.

**Mass/diameter estimation for secondary worlds** (no `WorldPhysical` available):

| Body | diameter_km | mass_earth |
|------|------------|------------|
| Size S | 800 | (800/12742)³ |
| Terrestrial size N | N × 1600 | (N × 1600 / 12742)³ |
| Gas giant diam D | D × 12800 | D² |

For the mainworld, `WorldPhysical.diameter_km` and `WorldPhysical.mass` are used
directly (accessed via `mainworld.size_detail`).

**Optional eccentricity/direction** (WBH p.76) — deferred; fields are present
on `Moon` but left at defaults (`orbit_eccentricity=0.0`, `orbit_retrograde=False`).

### Belt physical detail (WBH pp.131-133)

`generate_system_detail()` calls `generate_belt_physical()` for every belt orbit
slot and attaches the result as `WorldDetail.physical`. This field is `None` for
all non-belt slot types.

Parameters computed inside `generate_system_detail()` before the main loop:

| Parameter | Source |
|-----------|--------|
| `star_orbit_spreads` | Per-star dict: `(max orbit# − MAO) / n_orbits` — the WBH orbit generation spread (Orbit# units). **Not** the AU range of the system. |
| `outermost_au` | `max(orbit_au)` across all non-empty orbits |
| `is_exploited` | mainworld has `"In"` trade code **and** `tech_level >= 8` |

Per-belt parameters computed inside the loop:

| Parameter | Source |
|-----------|--------|
| `orbit_spread` | `star_orbit_spreads[orbit.star_designation]` |
| `next_is_gas_giant` | First non-empty orbit outward on the same star with `world_type == "gas_giant"` |
| `is_outermost` | `orbit.orbit_au >= outermost_au` |
| `orbit_au` / `hz_deviation` | Taken directly from the `OrbitSlot` |
| `age_gyr` | `system.stellar_system.primary.age_gyr` |

### Belt mainworld guard

`generate_moons(size_code=0)` returns `[]` immediately when `not is_gas_giant`.
Belts are diffuse debris fields and cannot host moons.

### Ring consolidation

Multiple rings rolled for a single planet are merged into one `Moon(is_ring=True)`
with `_ring_count` set to the total. `_ring_count` is declared as
`field(default=1, init=False)` in the dataclass — it is not accepted by
`__init__` but is a known field for type checkers.

### Moon detail generation

`_moon_detail()` in `traveller_world_detail.py` handles all moon social data.

- Uses the **parent planet's HZ deviation**, not the moon's own position.
- Size S and size 0–1 moons automatically receive `atmosphere=0`, `hydro=0`
  (too small to retain atmosphere).
- Size 2+ moons go through the full `generate_atmosphere()` /
  `generate_hydrographics()` pipeline.
- Moon size must be ≤ parent size (WBH p.57): `sz = min(sz, parent_size)`.
