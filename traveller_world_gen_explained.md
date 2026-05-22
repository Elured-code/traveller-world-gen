# Understanding `traveller_world_gen.py`

A guide for Python beginners. This file generates Traveller RPG worlds — it reads
the rulebook tables, rolls virtual dice, and produces a `World` object that
captures everything about a planet: its atmosphere, population, starport, and so on.

---

## How the file is laid out

The file is about 2,600 lines long. It is divided into clear sections (look for the
dashed comment banners like `# -----`). Reading top-to-bottom, the sections are:

| Section | What it contains |
|---------|-----------------|
| Imports | Standard library tools the file needs |
| Dice helpers | `roll()` — how virtual dice work |
| eHex helper | `to_hex()` — Traveller's unusual number encoding |
| Lookup tables | Python dicts mapping codes → descriptions |
| Atmosphere detail | Functions that compute pressure, oxygen, taints |
| `World` class | The main data structure |
| Generator functions | One function per world characteristic |
| `generate_world()` | Entry point that ties everything together |
| `main()` | Command-line interface |

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

The `World` class (line ~1454) is a **dataclass** — a Python shortcut for creating
classes that mainly hold data. The `@dataclass` decorator automatically generates
`__init__`, `__repr__`, and other boilerplate:

```python
@dataclass
class World:
    name: str
    size: int
    atmosphere: int
    temperature: str
    hydrographics: int
    population: int
    ...
```

Each line `name: str` declares a **field**: its name and its type. When you create
a `World` you pass values for all these fields. The generated `__init__` stores them.

### `field(default=None, init=False)`

Some fields are set *after* construction by other code, not when `World` is first
created. These use `field(default=..., init=False)`:

```python
physical: Optional[Union["WorldPhysical", BeltPhysical]] = field(default=None, init=False)
```

`init=False` means the field is **not** a parameter to `__init__` — it starts at its
default and is set later by `generate_world_physical()` or `attach_detail()`.

---

## The `to_hex()` function and Traveller eHex encoding

Traveller worlds are described by a **Universal World Profile (UWP)** like `A688542-B`.
Each character is a single digit in **eHex** (extended hexadecimal): 0–9 then A=10,
B=11 … G=16. The `to_hex()` function converts an integer to that format:

```python
def to_hex(value: int) -> str:
    return _HEX_DIGITS[value]   # _HEX_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
```

So `to_hex(11)` → `"B"`, `to_hex(15)` → `"F"`.

---

## How a world is generated: `generate_world()`

The entry point is `generate_world(name)` (line ~2466). It calls each characteristic's
generator in rulebook order, passing earlier results as inputs to later ones:

```python
def generate_world(name: str = "Unknown") -> World:
    size         = generate_size()
    atmosphere   = generate_atmosphere(size)          # needs size
    temperature  = generate_temperature(atmosphere)   # needs atmosphere
    hydrographics = generate_hydrographics(
                       size, atmosphere, temperature)  # needs all three
    population   = generate_population()
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
stored as `World.atmosphere_detail` and only set when the full atmosphere pipeline
has been run.

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

## The random seed

Many functions use `random.randint(1, 6)` (through `roll()`) from Python's standard
`random` module. The global random state means every roll feeds into the next.

If you set the seed with `random.seed(42)` before calling `generate_world()`, you
get the same world every time. This is how the `--seed` CLI argument works.

---

## Running the file directly

```bash
python traveller_world_gen.py               # one random world
python traveller_world_gen.py --name Terra  # give it a name
python traveller_world_gen.py --count 5     # five worlds
python traveller_world_gen.py --seed 42     # reproducible
```

`main()` (line ~2564) parses the command-line arguments with `argparse`, calls
`generate_world()` for each world, and prints the result.

---

## Summary of the pipeline

```
random seed (optional)
        │
        ▼
  generate_size()
        │
        ▼
  generate_atmosphere(size)
        │
        ▼
  generate_temperature(atmosphere)
        │
        ▼
  generate_hydrographics(size, atmosphere, temperature)
        │
        ▼
  generate_population()    generate_government(pop)
        │                         │
        └──────────┬──────────────┘
                   ▼
          generate_law_level(gov)
          generate_starport(pop)
          generate_tech_level(...)
          generate_bases(...)
          assign_trade_codes(...)
          assign_travel_zone(...)
                   │
                   ▼
              World(...)   ← all values assembled into the dataclass
```
