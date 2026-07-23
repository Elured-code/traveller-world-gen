# Understanding `traveller_world_gen.py`

A guide for Python beginners. This file generates Traveller RPG worlds — it reads
the rulebook tables, rolls virtual dice, and produces a `World` object that
captures everything about a planet: its atmosphere, population, starport, and so on.

---

## How the file is laid out

The file is about 2,800 lines long. It is divided into clear sections (look for the
dashed comment banners like `# -----`). Reading top-to-bottom, the sections are:

| Section | What it contains |
|---------|-----------------|
| Imports | Standard library tools the file needs |
| Dice helpers | `roll()` — how virtual dice work |
| eHex helper | `to_hex()` — Traveller's unusual number encoding |
| Lookup tables | Python dicts mapping codes → descriptions |
| Atmosphere detail | Functions that compute pressure, oxygen, taints |
| Social application | `apply_mainworld_social()` — deferred social steps |
| `World` class | The main data structure |
| Generator functions | One function per world characteristic |
| `generate_world()` | Entry point that ties everything together |
| `main()` | Command-line interface |

Several related modules work alongside this file:

| Module | Role |
|--------|------|
| `world_codes.py` | Shared enums (`StarportCode`, `TradeCode`, `AtmosphereCode`, etc.) and `APP_VERSION` |
| `traveller_world_physical.py` | Physical characteristics (diameter, gravity, temperature, day length) |
| `traveller_belt_physical.py` | Asteroid belt characteristics (span, composition, bulk) |
| `traveller_hydro_detail.py` | Hydrographic detail (surface liquid percentage, fluid type) |
| `traveller_world_detail.py` | Secondary world profiles, biological ratings, sophont checks |

---

## Key Python concept: the `roll()` function

```python
def roll(num_dice: int, modifier: int = 0) -> int:
    total = sum(random.randint(1, 6) for _ in range(num_dice))
    return max(0, total + modifier)
```

This simulates rolling dice:

- `random.randint(1, 6)` gives one die result (1 through 6).
- `for _ in range(num_dice)` repeats that `num_dice` times.
- `sum(...)` adds all the dice together.
- `modifier` shifts the total up or down.
- `max(0, ...)` prevents the result from going below zero (many Traveller tables
  treat negative results as zero).

**Example:** `roll(2, -3)` rolls two dice, adds them, then subtracts 3.

---

## Key Python concept: lookup tables (dictionaries)

Traveller uses a lot of tables. Rather than a chain of `if`/`elif` statements, the
code stores tables as Python **dictionaries** (`dict`) — a data structure that maps
a key to a value.

```python
ATMOSPHERE_NAMES = {
    0:  "None",
    1:  "Trace",
    2:  "Very Thin, Tainted",
    ...
    11: "Corrosive",
}
```

To look up an atmosphere name, you just write:

```python
name = ATMOSPHERE_NAMES[atmosphere_code]   # e.g. ATMOSPHERE_NAMES[11] → "Corrosive"
```

If the code might be missing from the table, `.get()` is used with a fallback:

```python
dm = STARPORT_TL_DM.get(starport, 0)   # returns 0 if starport isn't in the dict
```

---

## Key Python concept: `Optional[int]` and `None`

You will see types like `Optional[int]` throughout the file. This means the value
could be an integer **or** `None` (i.e., nothing/absent). Python's `None` is used
when a value hasn't been set yet or doesn't apply.

```python
mean_temperature_k: Optional[int] = field(default=None, init=False)
```

This declares a field that starts as `None` and is filled in later by a separate
function. You will often see guards like:

```python
if phys is not None:
    ...   # only runs when phys has been set
```

---

## Key Python concept: `@dataclass` and the `World` class

The `World` class (line ~1510) is a **dataclass** — a Python shortcut for creating
classes that mainly hold data. The `@dataclass` decorator automatically generates
`__init__`, `__repr__`, and other boilerplate.

### Constructor fields (set when `World` is created)

These are the fields passed directly to `generate_world()` and stored at construction
time:

```python
@dataclass
class World:
    name:           str   = "Unknown"
    size:           int   = 0
    atmosphere:     int   = 0
    atmosphere_detail:   Optional[AtmosphereDetail]   = None
    temperature:         str  = "Temperate"
    hydrographics:       int  = 0
    hydrographic_detail: Optional[HydrographicDetail] = None
    population:     int   = 0
    government:     int   = 0
    law_level:      int   = 0
    starport:       str   = "X"
    tech_level:     int   = 0
    has_gas_giant:  bool  = False
    gas_giant_count: int  = 0
    belt_count:      int  = 0
    population_multiplier: int = 0
    bases:       List[str] = field(default_factory=list)
    trade_codes: List[str] = field(default_factory=list)
    travel_zone: str = "Green"
    notes:       List[str] = field(default_factory=list)
    seed:            Optional[int] = None
    settlement_type: str = "standard"
```

`seed` and `settlement_type` are stamped by `generate_world()` itself
(mirroring `TravellerSystem`'s `seed`/`nhz_atmospheres`/etc.) so a saved
world JSON records everything needed to reproduce it: pass the same
`seed` and `settlement_type` back to `generate_world()` for identical
output (Session 178).

### `field(default=None, init=False)` — fields set later

Some fields are set *after* construction by other code, not when `World` is first
created. These use `field(default=..., init=False)`:

```python
    # Set by generate_world_physical() or attach_detail()
    size_detail: Optional[Union["WorldPhysical", BeltPhysical]] = field(default=None, init=False)

    # Set by attach_detail() → _apply_biomass()
    biomass_rating:       Optional[int] = field(default=None, init=False)
    biocomplexity_rating: Optional[int] = field(default=None, init=False)
    native_sophont:  bool = field(default=False, init=False)
    extinct_sophont: bool = field(default=False, init=False)
    biodiversity_rating:  Optional[int] = field(default=None, init=False)
    compatibility_rating: Optional[int] = field(default=None, init=False)
    lifeform_profile:     Optional[str] = field(default=None, init=False)

    # Set by attach_detail() → _apply_habitability()
    habitability_rating:  Optional[int] = field(default=None, init=False)
```

`init=False` means the field is **not** a parameter to `__init__` — it starts at its
default and is set later by a dedicated function. See **Two-phase generation** below.

---

## The `to_hex()` function and Traveller eHex encoding

Traveller worlds are described by a **Universal World Profile (UWP)** like `A688542-B`.
Each character is a single digit in **eHex** (extended hexadecimal): 0–9 then A=10,
B=11 … G=16. The `to_hex()` function converts an integer to that format:

```python
def to_hex(value: int) -> str:
    return _HEX_DIGITS[value]   # _HEX_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTU"
```

So `to_hex(11)` → `"B"`, `to_hex(15)` → `"F"`.

eHex encoding is also used for biological ratings. The four-character **lifeform
profile** `MXDC` is built by encoding Biomass (M), Biocomplexity (X), Biodiversity
(D), and Compatibility (C) as eHex digits:

```python
lifeform_profile = (
    f"{to_hex(biomass_rating)}"
    f"{to_hex(biocomplexity_rating)}"
    f"{to_hex(biodiversity_rating)}"
    f"{to_hex(compatibility_rating)}"
)
```

---

## How a world is generated: `generate_world()`

The entry point is `generate_world(name, seed=None, rng=None, settlement_type="standard")`.
It calls each characteristic's generator in rulebook order, passing earlier results as
inputs to later ones. When `seed` or `rng` is provided, the module-level `_rng` instance
is replaced with a seeded `random.Random` for that call; without either argument the
existing `_rng` state is used unchanged. `settlement_type` selects an optional
atmosphere-dependent DM applied to the population roll (see Settlement type section below).

```python
def generate_world(name="Unknown", seed=None, rng=None, settlement_type="standard") -> World:
    size         = generate_size()
    atmosphere   = generate_atmosphere(size)          # needs size
    temperature  = generate_temperature(atmosphere)   # needs atmosphere
    hydrographics = generate_hydrographics(
                       size, atmosphere, temperature)  # needs all three
    population   = generate_population(
                       _population_settlement_dm(settlement_type, atmosphere))
    government   = generate_government(population)    # needs population
    law_level    = generate_law_level(government)     # needs government
    starport     = generate_starport(population)      # needs population
    tech_level   = generate_tech_level(...)           # needs many fields
    ...
    return World(name=name, size=size, atmosphere=atmosphere, ...)
```

This sequential dependency — each step feeds into the next — mirrors exactly how
the Traveller rulebook instructs the referee to roll characteristics in order.

---

## Individual generator functions

Each generator follows the same pattern: roll dice, apply modifiers from a lookup
table, clamp the result, return it.

### `generate_size()` — the simplest example

```python
def generate_size() -> int:
    return roll(2, -2)   # 2D-2, range 0-10
```

Roll two dice and subtract 2. That's it. Size 0 is a belt or very small body;
size 10 (A in eHex) is a large world.

### `generate_atmosphere(size)` — using a DM from a previous result

```python
def generate_atmosphere(size: int) -> int:
    if size == 0:
        return 0   # belts have no atmosphere
    return roll(2, size - 7)   # 2D + (size - 7)
```

The `size - 7` term is the DM (Dice Modifier) from the size value. Larger worlds
tend to have thicker atmospheres.

### `generate_tech_level(...)` — stacking multiple DMs

```python
def generate_tech_level(starport, size, atmosphere, hydrographics,
                        population, government) -> int:
    dm  = STARPORT_TL_DM.get(starport, 0)
    dm += SIZE_TL_DM.get(size, 0)
    dm += ATMOSPHERE_TL_DM.get(atmosphere, 0)
    dm += HYDROGRAPHICS_TL_DM.get(hydrographics, 0)
    dm += POPULATION_TL_DM.get(population, 0)
    dm += GOVERNMENT_TL_DM.get(government, 0)
    return max(0, roll(1, dm))
```

Each characteristic contributes its own DM from a lookup table. All DMs are summed,
then `1D + total_DM` is rolled. The result is clamped to at least 0.

---

## The `World` class methods

`World` has several methods that format or serialise the data:

| Method | What it does |
|--------|-------------|
| `.uwp()` | Returns the 9-character UWP string, e.g. `A688542-B` |
| `.summary()` | Returns a human-readable multi-line text description |
| `.to_dict()` | Returns a plain Python dictionary (for JSON export) |
| `.to_json()` | Returns the dictionary as a JSON string |
| `.to_html()` | Returns an HTML card (uses a Jinja2 template) |
| `.from_dict(d)` | Class method — reconstructs a `World` from a dictionary |

### `.uwp()` example

```python
def uwp(self) -> str:
    return (
        f"{self.starport}"
        f"{to_hex(self.size)}"
        f"{to_hex(self.atmosphere)}"
        f"{to_hex(self.hydrographics)}"
        f"{to_hex(self.population)}"
        f"{to_hex(self.government)}"
        f"{to_hex(self.law_level)}"
        f"-{to_hex(self.tech_level)}"
    )
```

Each characteristic is converted to its eHex digit, then assembled into the
standard UWP format.

### `.from_dict(d)` — reconstructing from saved data

`from_dict` is a **classmethod** — called on the class itself, not an instance:

```python
world = World.from_dict(saved_dict)
```

It reads back every field that `to_dict()` wrote, including nested objects:

- `AtmosphereDetail.from_dict(...)` if atmosphere detail was saved
- `HydrographicDetail.from_dict(...)` if hydrographic detail was saved
- `WorldPhysical.from_dict(...)` or `BeltPhysical.from_dict(...)` for physical detail
- All biological ratings (`biomass_rating`, `biocomplexity_rating`, `biodiversity_rating`,
  `compatibility_rating`, `lifeform_profile`) and sophont flags

This means a world saved to JSON can be fully restored — you get back exactly the same
`World` object with all its detail, not just the basic UWP digits.

---

## Atmosphere detail — the deeper layer

The WBH rulebook gives each atmosphere code a full set of quantitative properties.
These are computed by several functions:

| Function | What it computes |
|----------|-----------------|
| `_atmosphere_pressure_bar(code)` | Surface pressure in bar, drawn from the span table |
| `_oxygen_partial_pressure(code, pressure)` | Breathable oxygen fraction |
| `_scale_height_km(size, code)` | How quickly atmosphere thins with altitude |
| `generate_atmosphere_detail(...)` | Calls all of the above and returns an `AtmosphereDetail` object |

`AtmosphereDetail` is a dataclass that holds all of these values together. It is
stored as `World.atmosphere_detail` and is populated when the full atmosphere pipeline
has been run (either during world generation or restored from JSON by `from_dict()`).

---

## Trade codes — `assign_trade_codes()`

Trade codes (like `Ag` for Agricultural or `Hi` for High Population) describe a
world's economic and social character. They are assigned by checking conditions on
the world's characteristics:

```python
def assign_trade_codes(size, atmosphere, hydrographics,
                       population, government, law_level, tech_level) -> list:
    codes = []
    if atmosphere in range(4, 10) and hydrographics in range(4, 9) \
            and population in range(5, 8):
        codes.append("Ag")   # Agricultural
    if size == 0:
        codes.append("As")   # Asteroid belt
    ...
    return codes
```

The function returns a list of the string codes that apply. Each condition directly
follows the rulebook table.

---

## Three-phase generation (WBH workflow)

When generating a full star system via the WBH procedure, world generation is split
into **three separate phases**:

**Phase 1 — Physical** (`generate_mainworld_at_orbit()` in `traveller_system_gen.py`)
Rolls size, atmosphere, hydrographics, and temperature. Social data (population,
government, starport, TL) is *not* rolled here. The world returns with placeholder
values: `starport='X'`, all social codes 0, empty trade codes.

**Phase 2 — Detail and mainworld selection** (`attach_detail()` + `select_mainworld()`)
Generates secondary worlds and moons, runs biological and habitability ratings for
all worlds, scores every terrestrial candidate, and promotes the highest-scoring
world to mainworld. The scoring formula is:

```
score = habitability_rating × 50
      + native_sophont × 50
      + resource_rating × 30
      + refuelling_score × 10
```

On a 3D roll of 18, the selection is random. If a secondary wins, it is regenerated
as a full `World` and the old mainworld is demoted to a `WorldDetail`.

**Phase 3 — Social** (`apply_mainworld_social()`)
Rolls population, government, law, starport, TL, bases, trade codes, and travel zone
for the selected mainworld. After that, `apply_secondary_social()` (in
`traveller_world_detail.py`) re-applies social data to all secondary worlds and moons
using the mainworld's real values.

These three phases are always kept separate. `apply_mainworld_social()` is never
called automatically inside `generate_mainworld_at_orbit()`. This matters for the
random number sequence: dice in later phases extend the sequence from earlier phases,
so running or skipping a phase changes the seed state for subsequent worlds.

For the standalone CRB path (`generate_world()`), all three phases are rolled
together in one call — that path has no system context for mainworld selection.

`apply_mainworld_social()` accepts an optional `settlement_type` parameter:
```python
from traveller_world_gen import apply_mainworld_social
world = generate_mainworld_at_orbit(...)   # physical only
# ... selection logic ...
apply_mainworld_social(world, rng=rng, settlement_type="backwater")
```

## Settlement type population modifiers (issue #128)

Five named types shift the mainworld population roll by an atmosphere-dependent DM.
The result is clamped to the 0–10 range regardless of the DM.

| Type | Atm 5/6/8 | Atm 4/7/9 | Atm 0–3 | All other |
|------|-----------|-----------|---------|-----------|
| `"standard"` (default) | 0 | 0 | 0 | 0 |
| `"long_settled"` | +3 | +2 | +1 | 0 |
| `"well_settled"` | +2 | +1 | — | −1 |
| `"backwater"` | +1 | −1 | −3 | −5 |
| `"unsettled"` | −4 | −5 | — | −7 |

The lookup is performed by `_population_settlement_dm(settlement_type, atmosphere)`,
which reads `_SETTLEMENT_DMS` (explicit per-atm DMs) and `_SETTLEMENT_DEFAULT_DM`
(catch-all for atmospheres not listed). Both dicts are module-level constants.

`generate_population(settlement_dm=0)` performs `min(10, roll(2, -2 + settlement_dm))`.
`generate_world()` and `apply_mainworld_social()` both accept
`settlement_type: str = "standard"` and compute the DM internally from the world's
atmosphere code.

## Two-phase generation (standalone CRB path)

`generate_world()` produces a complete UWP — size, atmosphere, population, and so on.
The biological detail fields (`biomass_rating`, `biocomplexity_rating`,
`native_sophont`, `extinct_sophont`, `biodiversity_rating`, `compatibility_rating`,
`lifeform_profile`) and the physical detail (`size_detail`, `atmosphere_detail`,
`hydrographic_detail`) are populated in a **second, separate step** by calling
`attach_detail()` from `traveller_world_detail.py`.

The two phases are always kept separate. `attach_detail()` is never called
automatically inside `generate_world()`. This matters for the random number sequence:
any dice rolls in `attach_detail()` extend the sequence that started with
`generate_world()`, so running or skipping the detail step changes the seed state
for subsequent worlds.

### Biological ratings in detail

When a world has `biomass_rating ≥ 1`, `attach_detail()` also computes:

| Field | Formula | Range |
|-------|---------|-------|
| `biodiversity_rating` | `max(0, 2D−7 + Biomass + ⌈Biocomplexity/2⌉)` | 0+ |
| `compatibility_rating` | `max(0, 2D − ⌊Biocomplexity/2⌋ + DMs)` | 0+ |
| `lifeform_profile` | eHex string `MXDC` (Biomass, Biocomplexity, Biodiversity, Compatibility) | 4 chars |

Compatibility DMs are drawn from `_ATM_COMPAT_DM` (atmosphere code → DM) in
`traveller_world_detail.py`, with additional DMs for old systems (> 8 Gyr) and
"otherwise tainted" atmospheres.

All three fields are `None` when `biomass_rating` is 0 (no life present).

### Habitability rating

After biological detail, `_apply_habitability()` computes a **Habitability Rating**
(WBH p.131) for every mainworld regardless of whether it has life:

| Base | 10 |
|------|----|
| Size DM | −(6 − size) for very small or very large worlds |
| Atmosphere DM | lookup by atmosphere code; −12 for corrosive/insidious |
| Hydrographics DM | 0 for 30–60%, −2 for dry or waterworld extremes, −4 for none |
| Tidal lock DM | −2 for 1:1 or 3:2 lock |
| Temperature DM | up to −4 for too hot/cold mean; −2 for extreme high or low seasonal temps |
| Gravity DM | −4 to +1 depending on G; −6 for > 2G |

Result is clamped to a minimum of 0. The rating is stored on both `World.habitability_rating`
and `WorldDetail.habitability_rating`, and displayed on the world card with a
descriptive label from `tables.habitability_description()`.

---

## The random seed

Each generation module has a module-level `_rng` sentinel that starts as the standard
`random` module. When `generate_world()` is called with an explicit `seed` or `rng`
argument, it replaces `_rng` with a seeded `random.Random` instance, making that
world fully reproducible. Without either argument, `_rng` is left unchanged and the
existing random state continues.

`World.seed` is set when an explicit seed or RNG was supplied; it is included in
`to_dict()` output so that a saved world can document which seed produced it.

For standalone CLI use, `--seed 42` passes a seed to `generate_world()` and you
get the same world every time.

---

## Running the file directly

```bash
python traveller_world_gen.py               # one random world
python traveller_world_gen.py --name Terra  # give it a name
python traveller_world_gen.py --count 5     # five worlds
python traveller_world_gen.py --seed 42     # reproducible
```

`main()` (line ~2700) parses the command-line arguments with `argparse`, calls
`generate_world()` for each world, and prints the result.

---

## Summary of the pipeline

### Standalone CRB path (`generate_world()`)

```
random seed (optional)
        │
        ▼
  generate_size()
  generate_atmosphere(size)      ← AtmosphereDetail pipeline
  generate_temperature(atmosphere)
  generate_hydrographics(...)    ← HydrographicDetail pipeline
  generate_population()
  generate_government(pop)
  generate_law_level(gov)
  generate_starport(pop)
  generate_tech_level(...)
  generate_bases(...)
  assign_trade_codes(...)
  assign_travel_zone(...)
        │
        ▼
    World(...)   ← complete UWP in one call
        │
  (optional second phase)
        │
        ▼
  attach_detail()   ← from traveller_world_detail.py
  ├─ generate_world_physical()       → World.size_detail
  ├─ generate_biomass_rating()       → World.biomass_rating
  ├─ generate_sophont_checks()       → World.native_sophont
  └─ generate_habitability_rating()  → World.habitability_rating
```

### WBH system path (`generate_mainworld_at_orbit()` + selection + social)

```
Phase 1 — Physical
  generate_mainworld_at_orbit()   → World with SAH only (starport='X', social=0)
        │
Phase 2 — Detail and selection
        ▼
  attach_detail()               → secondary WorldDetails, biomass, habitability
  _attach_mainworld_physical()  → World.size_detail (resource_rating)
  select_mainworld()            → scores candidates; may swap mainworld
        │
Phase 3 — Social
        ▼
  apply_mainworld_social()      → pop, gov, law, starport, TL, bases, trade codes
  apply_secondary_social()      → re-applies social to all secondary WorldDetails
```
