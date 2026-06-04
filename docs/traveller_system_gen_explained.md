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
3. Generate the mainworld **physical** characteristics (`traveller_world_gen.py`)
   — size, atmosphere, hydrographics, using the orbit's habitable zone position to
   set temperature

Social characteristics (population, government, law, starport, TL, bases, trade
codes, travel zone) are **deferred**. The world returned by
`generate_mainworld_at_orbit()` carries placeholder values (`starport='X'`,
all social codes 0) until `apply_mainworld_social()` is called after mainworld
selection (a future step).

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
The actual game-dice randomness uses a dedicated `random.Random` instance throughout.

```python
seed = seed or secrets.token_hex(4)
rng = random.Random(seed)   # fresh instance — always propagated to sub-generators
```

`generate_full_system()` always creates a fresh `random.Random(seed)` and passes it
to every sub-generator (`generate_stellar_data`, `generate_orbits`, `generate_world`,
etc.) so that the full system is isolated from any global random state. Storing the
seed string in `TravellerSystem.seed` makes every system exactly reproducible.

---

## The `TravellerSystem` dataclass

```python
@dataclass
class TravellerSystem:
    stellar_system: StarSystem        # from traveller_stellar_gen.py
    system_orbits: SystemOrbits       # from traveller_orbit_gen.py
    mainworld: Optional[World]        # from traveller_world_gen.py
    mainworld_orbit: Optional[OrbitSlot]
    seed: Optional[str] = None        # the seed used to generate this system
```

This is the root object for a complete system. Everything else hangs off it.
`seed` is emitted by `to_dict()` when set, so a saved system always records the
seed that produced it.

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `TravellerSystem` | Full system as a nested dict (JSON-ready) |
| `.to_json()` | `TravellerSystem` | JSON string of the full system |
| `.to_html()` | `TravellerSystem` | HTML system card (Jinja2 template) |
| `.summary()` | `TravellerSystem` | Human-readable multi-line text |
| `.from_dict(d)` | `TravellerSystem` | Reconstructs the full system from a saved dict |
| `generate_full_system(...)` | module | Procedural entry point — returns physical-only mainworld |
| `select_mainworld(system, rng)` | module | Score all terrestrials and promote the winner; returns `True` if swapped |
| `generate_system_from_world(world, ...)` | module | Procedural entry point around an existing World |
| `generate_system_from_canonical(...)` | module | TravellerMap entry point |
| `attach_body_names(system)` | module | Assign placeholder names to all stars, orbits, moons; call after `attach_detail()` |

---

## The two entry points

### Procedural generation

```python
system = generate_full_system(name="Homeworld", seed="a3b1c9d0")
```

Rolls everything from scratch using the WBH procedures. The `seed` string controls
the random sequence — the same seed always produces the same system.

Optional flags:
- `nhz_atmospheres=True` — allow non-habitable-zone atmospheres for secondary worlds.
  Also accepted by `generate_system_from_world()` and `generate_system_from_map()`;
  stored in `TravellerSystem.nhz_atmospheres` in all cases so it appears in the JSON
  and can be passed back to reproduce the system.
- `orbital_eccentricity=True` — roll orbital eccentricities and inclinations
- `orbital_inclination=True` — roll inclinations separately
- `rng` — an existing `random.Random` instance to use instead of creating a new one
  (when provided, `seed` is still recorded but the supplied `rng` drives generation)

### TravellerMap (canonical) generation

```python
system = generate_system_from_canonical(canonical_data, seed=42)
```

The mainworld UWP and stellar string come from published Second Survey data. Orbits
and secondary worlds are generated procedurally from the canonical stellar data.

---

## How this fits in the pipeline

```
generate_stellar_data()                  →  StarSystem
        │
        ▼
generate_orbits(star_system, ...)        →  SystemOrbits
        │
        ▼
generate_mainworld_at_orbit(name, ...)   →  World (physical only — SAH, no social)
        │  (temperature driven by hz_deviation, not a free dice roll)
        ▼
TravellerSystem(stellar, orbits, mainworld, mainworld_orbit)
        │
        (when detail requested)
        ▼
attach_detail(system, ...)               →  WorldDetail for each secondary; biomass; habitability
attach_body_names(system)                →  name="" → "Homeworld-Primary", "Homeworld-A", etc.
_attach_mainworld_physical(system)       →  WorldPhysical for mainworld (resource_rating)
_apply_mainworld_moon_tidal(system)      →  tidal effects on mainworld
        │
        ▼
select_mainworld(system, rng)            →  scores all terrestrials; may swap mainworld
        │
        ▼
apply_mainworld_social(mainworld, rng)   →  pop, gov, law, starport, TL, trade codes
apply_secondary_social(system, ...)      →  re-applies social to all secondaries and moons
```

---

## `attach_body_names()` — placeholder body names (Session 102, issue #131)

`attach_body_names(system)` assigns a human-readable placeholder name to every
star, orbit slot, and moon in the system. It must be called **after**
`attach_detail()` because moon objects don't exist until then. It is
deterministic (no dice) and idempotent.

**Naming scheme:**

| Body | Placeholder |
|------|-------------|
| Mainworld orbit | `World.name` (already set) |
| Star A (non-companion) | `<mw>-Primary` |
| Star B (non-companion) | `<mw>-Secondary`, then Tertiary, etc. |
| Companion stars | Not named (`name` stays `""`) — companions share their parent's orbit |
| Non-mainworld terrestrial / GG | `<mw>-A`, `<mw>-B`, … (separate counter from belts) |
| Belt | `<mw>-Belt-A`, `<mw>-Belt-B`, … (separate counter from worlds) |
| Non-ring moon | `<orbit_name>-alpha`, `…-beta`, … (Greek sequence; rings skipped) |
| Ring moon | Not named (`name` stays `""`) |

`orbit.detail.name` and `moon.detail.name` are also set to mirror the parent
slot/moon name, so `WorldDetail` objects carry their own name for JSON output.

---

## `to_html()` — system card (Session 53, issues #114, #115)

`TravellerSystem.to_html()` renders the `system_card.html` Jinja2 template. It passes
two main data structures:

- **`star_rows`** — one dict per star: `designation`, `classification`, `mass`,
  `temperature`, `luminosity`, `orbit`, plus four new fields added in Session 83
  (issue #115):
  - `mao` — Minimum Armistice Orbit (Orbit# at stellar separation / 3), or `"—"` for
    the primary
  - `hz_inner` / `hzco` / `hz_outer` — inner edge, centre, and outer edge of the
    Habitable Zone, formatted to 2 decimal places, or `"—"` for stars without a
    computed HZ
- **`orbit_rows`** — one dict per orbit slot, with inline `moons` list. Session 102 added
  `"name"` as the first key in each orbit row and moon sub-dict, so `system_card.html` can
  display it as the leftmost column.

The system card shows **stellar data and orbital survey only**. Mainworld detail
(UWP stats, atmosphere, hydrographic, biological, habitability) appears exclusively
on the Mainworld tab via `World.to_html()` — the `mw_data` construction block and
the corresponding HTML section were removed in Session 83 (issue #114) to eliminate
duplication between the System tab and Mainworld tab in gen-ui.
