# Understanding `traveller_world_physical.py`

A guide for Python beginners. This file generates the physical characteristics of a
terrestrial world — how big it is, what it is made of, how strong gravity is, how
fast it rotates, and what the temperature actually is.

---

## What this file does

The UWP gives a world a Size code (0–A) but that is just a digit. This file turns
it into physical reality:

- **Diameter** — actual kilometres, with per-world variation around the Size band
- **Composition and density** — rock, iron-rich, icy, etc.
- **Derived properties** — mass, gravity, and escape velocity from physics formulae
- **Axial tilt** — degrees of tilt, including extreme retrograde tilts
- **Day length** — how long a rotation takes, including tidal lock effects
- **Stellar day** — the length of the solar day (different from the sidereal day
  when the world is also orbiting)
- **Advanced mean temperature** — a more accurate temperature based on luminosity,
  orbit distance, albedo, and greenhouse factor
- **High/low temperature** — seasonal extremes driven by axial tilt, rotation, and
  geography

Implements WBH pp.74–78, 103–107, and 47–50.

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | `math`, `random`, `dataclass` |
| `WorldPhysical` dataclass | All physical fields |
| Internal helpers | `_roll_diameter()`, `_roll_composition()`, `_roll_axial_tilt()`, etc. |
| `generate_world_physical()` | Main entry point |
| `generate_advanced_mean_temperature()` | Optional second pass for accurate temperatures |
| `apply_moon_tidal_effects()` | Updates day length and stellar day after moon data |

---

## Key Python concept: physics formulae

Several properties are *calculated*, not rolled. For example:

```python
# Surface gravity in Earth G
gravity = (diameter_km / 12_742) * (density_g_cm3 / 5.515)

# Escape velocity in km/s
escape_velocity = 11.186 * math.sqrt(gravity * (diameter_km / 12_742))
```

`12_742` is Earth's diameter in km; `5.515` is Earth's density in g/cm³; `11.186`
is Earth's escape velocity in km/s. The underscores in `12_742` are a Python
readability convention — they are ignored by the interpreter (the same as writing
`12742`).

---

## Key Python concept: `init=False` fields

`WorldPhysical` has many fields that are filled in across several function calls:

```python
@dataclass
class WorldPhysical:
    # Set by generate_world_physical():
    composition: str
    diameter_km: int
    density_g_cm3: float
    mass_earth: float
    gravity_g: float
    escape_velocity_km_s: float
    axial_tilt_deg: float
    day_length_hours: float
    tidal_status: str

    # Set by generate_advanced_mean_temperature() (optional):
    albedo: Optional[float] = field(default=None, init=False)
    greenhouse_factor: Optional[float] = field(default=None, init=False)
    advanced_mean_temperature_k: Optional[int] = field(default=None, init=False)
    high_temperature_k: Optional[int] = field(default=None, init=False)
    low_temperature_k: Optional[int] = field(default=None, init=False)

    # Set after moon orbital data is known:
    stellar_day_hours: Optional[float] = field(default=None, init=False)
```

The constructor fields are set first. The `init=False` fields are filled in by
separate function calls if the caller wants that level of detail.

---

## Advanced mean temperature

The WBH temperature formula (p.47–50) is more accurate than the basic CRB table
because it uses real stellar physics:

```
T = 279 × ⁴√( L × (1−A) × (1+G) / AU² )
```

Where:
- `L` is the star's luminosity in Solar units
- `A` is the world's **albedo** (reflectivity; 0.02 to 0.98)
- `G` is the **greenhouse factor** (how much the atmosphere traps heat)
- `AU` is the orbital distance in Astronomical Units

This is the same formula used by planetary scientists for real planets. `279` is
derived from Earth's values (effective radiation constant at Earth's orbit).

Albedo and greenhouse factor are each rolled from sub-tables in the WBH, then this
formula gives the mean temperature. High/low seasonal extremes are derived from
axial tilt, rotation rate, and hydrographics.

### Very cold worlds (below 10 K)

WBH p.47 footnote: when the extrapolated mean temperature would fall below 10 K
(modified roll ≤ −34), the result is replaced with `1D+5` — a random value from
6 K to 11 K. This represents the floor of measurable surface temperatures where
the linear formula breaks down.

### Seismic heating baked in

After `generate_advanced_mean_temperature()` sets `advanced_mean_temperature_k`,
`high_temperature_k`, and `low_temperature_k`, a later call to
`apply_moon_tidal_effects()` may invoke `_apply_seismic_stress()`. If total
seismic stress is non-zero and produces a higher temperature via Stefan-Boltzmann
superposition, the three temperature fields are updated **in place**:

```python
# T_total = ⁴√(T₁⁴ + T₂⁴)  — heat sources add in quadrature
adv_adj = round((adv_t ** 4 + tss ** 4) ** 0.25)
```

There is no separate "seismic temperature" display field — the seismic heating is
already included in the values shown on the world card.

---

## Tidal lock and stellar day

A world very close to its star can become **tidally locked** — one side always faces
the star (like our Moon faces Earth). `generate_world_physical()` rolls on the Tidal
Lock Status table:

| Tidal status | Effect |
|---|---|
| Normal | Day length is the rolled sidereal day |
| Slow prograde/retrograde | Multiplied day length |
| 3:2 lock | Day = 2/3 × orbital period |
| 1:1 lock | Day = orbital period (locked face-to-face with star) |

The **stellar day** (time between sunrises) is different from the **sidereal day**
(time for one complete rotation) because the world is also orbiting the star.
`apply_moon_tidal_effects()` recalculates the stellar day after moon data is known.

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `WorldPhysical` | Serialises all fields to a plain dict |
| `.from_dict(d)` | `WorldPhysical` | Reconstructs from a dict |
| `generate_world_physical(...)` | module | Main entry point |
| `generate_advanced_mean_temperature(...)` | module | Optional second pass |
| `apply_moon_tidal_effects(...)` | module | Updates day/stellar day after moon data |

---

## How this fits in the pipeline

```
generate_world()                      →  World (UWP)
        │
        ▼
generate_world_physical(world, ...)   →  WorldPhysical
        │  (sets World.size_detail)
        ▼
generate_advanced_mean_temperature()  →  sets WorldPhysical.advanced_mean_temperature_k
        │  (optional; also sets high_temperature_k, low_temperature_k)
        ▼
attach_detail()                       →  reads World.size_detail for biomass DMs
```

`BeltPhysical` (in `traveller_belt_physical.py`) handles size-0 asteroid belt
mainworlds along a parallel path — not through this file.
