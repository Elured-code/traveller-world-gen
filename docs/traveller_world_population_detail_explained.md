# Understanding `traveller_world_population_detail.py`

A guide for Python beginners. This file takes the raw UWP population code from a
world's Universal World Profile and expands it into a full demographic picture: how
concentrated people are, what fraction live in cities, how many major cities exist,
and roughly how big each one is. The result is a `PopulationDetail` object and a
compact population profile string in WBH format.

---

## What this file does

In Traveller, a world's UWP gives you a single-digit population code (0–C) and a
population multiplier. A pop-7 world with multiplier 4 has about 40 million people,
but that single figure tells you nothing about whether they are scattered across the
countryside or crammed into a handful of megacities. This file answers that question
by implementing WBH §2 Social Characteristics.

The main public function is `generate_population_detail()`. It runs the following
steps in order:

1. **Population Concentration Rating (PCR, 0–9)** — a measure of how urbanised the
   world is. PCR 0 means people are spread very thinly; PCR 9 means nearly everyone
   lives in a small number of dense centres. Low-population worlds (pop code < 6) get
   a special quick-check: roll 1D, and if the result exceeds the pop code, PCR jumps
   straight to 9 (a sparse world almost always puts everyone in one place).
2. **Urbanisation %** — what fraction of the total population lives in urban
   settlements. Rolled on a 2D table with DMs from PCR, government, tech level, law,
   trade codes, and atmosphere. Min and max constraints from world size and pop code
   can override the result.
3. **Major city count and total major-city population** — the number of cities large
   enough to qualify as "major" and the aggregate population that lives in them. A
   five-case procedure handles edge cases (PCR 0 = no cities; PCR 9 on a small world
   = one huge city; etc.).
4. **Individual city populations** — up to 10 cities are listed individually. Their
   populations are assigned by a chunk-allocation algorithm that distributes the
   major-city population pool semi-randomly based on PCR.
5. **Population profile string** — formatted as `P-p-C-%-M` (e.g. `7-4-6-52-8`),
   where P is the population code in eHex, p is the multiplier, C is the PCR, % is
   the urbanisation percentage, and M is the major city count.

The function returns `None` for uninhabited worlds (pop code 0). The companion
function `attach_population_detail()` walks an entire `TravellerSystem` and applies
population detail to the mainworld and every inhabited secondary world and moon.

Implements WBH §2 Social Characteristics (Population Concentration Rating,
Urbanisation, Major Cities).

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | `math`, `random`, `dataclasses`, plus the `WorldPhysical` type |
| Module-level `_rng` | Injectable RNG sentinel (see "Key Python concept" below) |
| `_PCR_LABELS` | Dict mapping PCR codes 0–9 to human-readable descriptions |
| `_round_sig()` | Helper: rounds a population number to 3 significant figures |
| `City` dataclass | One entry in the major-cities list: population + optional codes |
| `PopulationDetail` dataclass | The full 10-field demographic profile for one world |
| PCR helpers | `_minimal_tl()`, `_pcr_dms()`, `generate_pcr()` |
| Urbanisation helpers | `_urb_pct_from_result()`, `_urb_dms_and_constraints()`, `generate_urbanisation_pct()` |
| Major-city helpers | `_total_world_population()`, `_major_cities_and_total_pop()`, `_distribute_city_populations()` |
| `generate_population_detail()` | Main public entry point |
| `attach_population_detail()` | System-wide attachment: mainworld + secondaries + moons |
| Private secondary helpers | `_gen_p_value()`, `_ehex_int()`, `_pop_detail_for_det()`, `_attach_detail_population()` |

---

## Key Python concept: the module-level `_rng` sentinel

Every module in this project uses the same pattern for injectable random number
generation. At the top of the file you will see:

```python
import random
_rng: random.Random = random  # type: ignore[assignment]
```

`random` (the module) behaves like a `random.Random` instance for most purposes —
it has `.randint()`, `.random()`, and so on. So at startup, `_rng` points at the
module itself, which uses Python's global RNG state.

When a caller passes in a seeded `random.Random` instance:

```python
def generate_pcr(..., rng: Optional[random.Random] = None) -> int:
    global _rng
    if rng is not None:
        _rng = rng
```

the module switches to that deterministic RNG for all subsequent rolls. This is how
the generator can reproduce identical worlds from the same seed. The `global _rng`
statement is required here because we are replacing the module-level variable, not
just reading it.

---

## Key Python concept: the `@dataclass` decorator

`City` and `PopulationDetail` are decorated with `@dataclass`. This is a Python
shortcut that automatically generates an `__init__` method from the class body's
type-annotated fields, saving you from writing repetitive boilerplate:

```python
@dataclass
class City:
    population: int
    codes: list = field(default_factory=list)
```

This is equivalent to writing:

```python
class City:
    def __init__(self, population: int, codes: list = None):
        self.population = population
        self.codes = codes if codes is not None else []
```

`field(default_factory=list)` is used instead of `codes: list = []` because mutable
defaults like `[]` are shared across all instances in Python, which causes subtle
bugs. `default_factory=list` creates a fresh `[]` for each new `City`.

---

## The PCR procedure in game terms

PCR stands for Population Concentration Rating. A PCR of 0 means people are
scattered across wilderness — no one city is large enough to matter. A PCR of 9 is a
world where a single megacity holds nearly everyone, like a planet-wide hive.

The roll works like this:

1. If the world has fewer than 6 million people (pop code < 6), first check: roll 1D.
   If the result is higher than the pop code, the world is so sparsely settled that
   everyone clusters together — PCR = 9 automatically.
2. Otherwise, roll 1D and add DMs:
   - Small worlds (size 1–3): +1 or +2, because there is little habitable land.
   - Tidally locked: +2, because one hemisphere is uninhabitable.
   - Hostile atmosphere requiring high TL: +1 to +3, because only reinforced
     settlements are viable.
   - Agricultural trade code: −2, because farmers spread out.
   - Industrial trade code: +1, because factory workers cluster.

```python
if pop_code < 6 and _rng.randint(1, 6) > pop_code:
    return 9
```

---

## The urbanisation table

Urbanisation is not a single linear table — it maps a 2D+DM roll result to a
percentage using inner dice. For example, a result of 3 gives `12 + 1D` per cent
(so anywhere from 13 % to 18 %), while a result of 9 gives `70 + 1D×2 + D2`
(somewhere in the 72–82 % range). This gives realistic variation around each band
instead of fixed jump points.

Min and max constraints can override the rolled result. A pop-9 world always has at
least `18 + 1D` % urban population; a TL-2 world can never exceed `30 + 1D` %.
If a minimum and maximum conflict, the minimum wins.

---

## The population profile string

The profile string `P-p-C-%-M` packages the key figures into a compact notation that
matches WBH convention:

| Position | Meaning | Example |
|----------|---------|---------|
| P | Population code (eHex) | `7` = pop 7 |
| p | Population multiplier | `4` means ×4 |
| C | PCR (0–9) | `6` = Partially Concentrated |
| % | Urbanisation percentage | `52` = 52 % urban |
| M | Major city count | `8` major cities |

For a world with pop code 7, multiplier 4, PCR 6, 52 % urbanisation, 8 major cities,
the profile is `7-4-6-52-8`.

---

## How this fits in the pipeline

Population detail is generated after the mainworld's social codes (pop code,
government, tech level, law level, trade codes) are finalised. It feeds into
government detail (which uses `pcr` as a DM), law detail (subcategory DMs), and tech
detail (low common TL DMs). The recommended call order is:

```
attach_population_detail(system, rng)
attach_government_detail(system, rng)    # uses pcr from population_detail
attach_law_detail(system, rng)           # uses pcr from population_detail
attach_tech_detail(system, rng)          # uses pcr from population_detail
```

---

## Key methods

| Method / function | What it does |
|-------------------|-------------|
| `generate_pcr(pop_code, size, tl, government, trade_codes, ...)` | Rolls Population Concentration Rating (0–9) with all WBH DMs |
| `generate_urbanisation_pct(pcr, pop_code, size, tl, ...)` | Rolls urbanisation percentage with min/max constraints |
| `generate_population_detail(pop_code, p_value, size, tl, ...)` | Main entry point: returns a full `PopulationDetail` or `None` for pop 0 |
| `attach_population_detail(system, rng=None)` | Walks the system, calling `generate_population_detail()` for every inhabited world and moon |
| `PopulationDetail.to_dict()` | Serialises to a plain dict for JSON output |
| `PopulationDetail.from_dict(d)` | Reconstructs from a saved dict |
| `City.to_dict()` | Serialises one city entry |
| `City.from_dict(d)` | Reconstructs one city entry |
