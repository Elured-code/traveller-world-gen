# Understanding `traveller_moon_gen.py`

A guide for Python beginners. This file generates the moons and rings for every
world in the system, following the WBH sizing and orbit rules.

---

## What this file does

For each significant orbit slot (gas giants and terrestrial worlds), this file:

- Rolls **how many** significant moons the world has (WBH p.56)
- Determines each moon's **size** (ring `R`, small worldlet `S`, or numeric 1–G)
- Places moons in **orbits** — distance from the parent world in planetary diameters
- Rolls moon **orbital eccentricity** and **inclination**
- Optionally generates `WorldDetail` for habitable moons (recursive detail)

Gas giants can have many large moons; small terrestrial worlds often have none.
A roll of exactly 0 moons produces one significant **ring** instead.

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | `random`, `math`, `dataclass` |
| Constants | `_EHEX` string for eHex encoding |
| `Moon` dataclass | One moon or ring |
| `_moon_quantity()` | How many moons to generate |
| `_moon_size()` | What size each moon is |
| `place_moon_orbit()` | Distance and period for one moon |
| `generate_moons()` | Entry point — returns the full list |

---

## Key Python concept: the `Moon` dataclass

```python
@dataclass
class Moon:
    size_code: int | str   # integer 0-G, or the string "S", or 0 with is_ring=True
    is_ring: bool = False
    is_gas_giant_moon: bool = False

    # Set by place_moon_orbit() after construction:
    orbit_pd: Optional[float] = None          # orbit in planetary diameters
    orbit_km: Optional[float] = None
    orbit_range: Optional[str] = None         # "close" | "near" | "far"
    orbit_period_hours: Optional[float]= None
    orbit_eccentricity: float = 0.0
    orbit_inclination: float = 0.0            # > 90° means retrograde

    # Set if the moon has its own WorldDetail (habitable moons):
    detail: Optional[WorldDetail] = None
```

`size_code` uses the same eHex encoding as world sizes. Size 0 with `is_ring=True`
is a ring; size `"S"` is a small worldlet (~600 km diameter).

---

## Key Python concept: union types

`size_code: int | str` means the field can hold either an integer (for numeric sizes
0–16 in the eHex range) or the string `"S"`. The `|` operator for types was added
in Python 3.10 and is equivalent to the older `Union[int, str]` syntax.

Code that needs to handle both cases uses `isinstance()`:

```python
if isinstance(moon.size_code, str):
    label = moon.size_code        # "S"
else:
    label = to_hex(moon.size_code)  # integer → eHex digit
```

---

## Key Python concept: orbital mechanics (period)

Moon orbital periods are derived from Kepler's third law:

```python
# orbit_km = distance from planet centre in km
# planet_mass_earth = mass of the parent world in Earth masses
period_hours = 2 * math.pi * math.sqrt(
    (orbit_km * 1000) ** 3 / (G_EARTH * planet_mass_earth)
) / 3600
```

`G_EARTH` is the gravitational constant × Earth's mass (a known physical constant).
The `math.sqrt()` and exponent `** 3` implement the `√(r³ / GM)` formula. Dividing
by `3600` converts seconds to hours.

---

## Orbital eccentricity and inclination

After size and orbit placement, `generate_moons()` calls:

```python
eccentricity = roll_eccentricity()   # from traveller_orbit_gen
inclination  = roll_inclination()    # from traveller_orbit_gen
```

Both functions are shared with the main orbit generator. Inclinations over 90°
indicate a retrograde orbit (the moon orbits opposite to the planet's rotation).

---

## Recursive detail for habitable moons

If a moon is large enough and has a habitable atmosphere (checked by `attach_detail()`
in `traveller_world_detail.py`), a full `WorldDetail` can be generated for it. The
`Moon.detail` field holds this object. This is the same `WorldDetail` class used for
orbit slots — the recursion is intentional and the code guards against infinite loops
by only generating one level of moon detail.

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `Moon` | Serialises the moon to a plain dict |
| `.from_dict(d)` | `Moon` | Reconstructs from a dict (including nested detail) |
| `generate_moons(world_detail, orbit_number)` | module | Entry point — full list of moons |
| `place_moon_orbit(moon, parent_mass, ...)` | module | Sets orbit distance and period |
| `moons_str(moons)` | module | Compact display string e.g. `"R S 2 4"` |

---

## How this fits in the pipeline

```
attach_detail()
        │
        ├─ for each orbit slot:
        │       _generate_sah()  →  WorldDetail.sah
        │       generate_moons() →  WorldDetail.moons (list of Moon)
        │               │
        │               └─ place_moon_orbit() for each Moon
        │                  roll_eccentricity(), roll_inclination()
        │
        └─ (habitable moons may get WorldDetail.detail = WorldDetail(...))
```
