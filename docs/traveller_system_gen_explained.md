# Understanding `traveller_system_gen.py`

A guide for Python beginners. This file is the top-level assembler — it calls the
stellar, orbit, and world generators and weaves their outputs into one coherent
`TravellerSystem` object.

---

## What this file does

`traveller_system_gen.py` does not do much new generation itself. Its job is
**integration**: it calls the three major generators in the right order and ensures
each step receives the information it needs from the previous steps:

1. Generate stars (`traveller_stellar_gen.py`)
2. Place orbits (`traveller_orbit_gen.py`)
3. Generate the mainworld UWP (`traveller_world_gen.py`) — using the orbit's
   habitable zone position to set temperature, so the mainworld is physically
   consistent with where it orbits

The key integration: temperature is **not** rolled randomly here. Instead, the orbit's
`hz_deviation` value is converted to the raw 2D roll that the temperature table
expects, and *that* value is fed to the standard temperature procedure. This is the
WBH's "Habitable Zones Regions" table (p.46).

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | Pulls in all three sub-generators plus `World`, `html_render`, etc. |
| `generate_temperature_from_orbit()` | Maps HZ deviation → temperature |
| `TravellerSystem` dataclass | Holds the assembled system |
| `generate_full_system()` | Entry point for procedural generation |
| `generate_system_from_canonical()` | Entry point for TravellerMap-derived systems |

---

## Key Python concept: tying two random sequences together

`generate_world()` normally rolls 2D for temperature. In `generate_full_system()`,
that roll is **replaced** by the orbit's HZ position:

```python
raw_roll = generate_temperature_from_orbit(hz_deviation)
temperature, temperature_raw = temperature_category(atmosphere, raw_roll)
```

`generate_temperature_from_orbit()` reads the HZ deviation and returns the
equivalent raw 2D result (2–12) from the WBH Habitable Zones Regions table. The
rest of the temperature procedure then runs normally — the atmosphere code still
adds its DMs on top of this raw roll.

---

## Key Python concept: `secrets.token_hex` for seeds

When no seed is provided, `generate_full_system()` creates a random seed using
`secrets.token_hex(4)` — a cryptographically random 8-character hex string. This is
different from `random.seed()`: `secrets` is used only to *generate* the seed string.
The actual game-dice randomness uses Python's standard `random` module throughout.

```python
seed = seed or secrets.token_hex(4)
random.seed(seed)
```

Storing the seed string in the output makes every generated system exactly
reproducible if the seed is saved.

---

## The `TravellerSystem` dataclass

```python
@dataclass
class TravellerSystem:
    stellar_system: StarSystem        # from traveller_stellar_gen.py
    system_orbits: SystemOrbits       # from traveller_orbit_gen.py
    mainworld: Optional[World]        # from traveller_world_gen.py
    mainworld_orbit: Optional[OrbitSlot]
```

This is the root object for a complete system. Everything else hangs off it.

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `TravellerSystem` | Full system as a nested dict (JSON-ready) |
| `.to_json()` | `TravellerSystem` | JSON string of the full system |
| `.to_html()` | `TravellerSystem` | HTML system card (Jinja2 template) |
| `.summary()` | `TravellerSystem` | Human-readable multi-line text |
| `.from_dict(d)` | `TravellerSystem` | Reconstructs the full system from a saved dict |
| `generate_full_system(...)` | module | Procedural entry point |
| `generate_system_from_canonical(...)` | module | TravellerMap entry point |

---

## The two entry points

### Procedural generation

```python
system = generate_full_system(name="Homeworld", seed="a3b1c9d0")
```

Rolls everything from scratch using the WBH procedures. The `seed` string controls
the random sequence — the same seed always produces the same system.

Optional flags:
- `nhz_atmospheres=True` — allow non-habitable-zone atmospheres for secondary worlds
- `orbital_eccentricity=True` — roll orbital eccentricities and inclinations
- `orbital_inclination=True` — roll inclinations separately

### TravellerMap (canonical) generation

```python
system = generate_system_from_canonical(canonical_data, seed=42)
```

The mainworld UWP and stellar string come from published Second Survey data. Orbits
and secondary worlds are generated procedurally from the canonical stellar data.

---

## How this fits in the pipeline

```
generate_stellar_data()           →  StarSystem
        │
        ▼
generate_orbits(star_system, ...) →  SystemOrbits
        │
        ▼
generate_world(name, ...)         →  World (mainworld)
        │  (temperature driven by hz_deviation, not a free dice roll)
        ▼
TravellerSystem(stellar, orbits, mainworld, mainworld_orbit)
        │
        (optional)
        ▼
attach_detail(system, ...)        →  fills OrbitSlot.detail for each secondary world
```
