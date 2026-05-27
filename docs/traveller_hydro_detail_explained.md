# Understanding `traveller_hydro_detail.py`

A guide for Python beginners. This file refines the Hydrographics code into a
precise surface liquid percentage and identifies the chemical nature of the liquid.

---

## What this file does

The UWP Hydrographics digit is a code from 0 (no liquid) to A (fully covered).
This file adds two further details:

1. **Surface liquid percentage** — a precise value within the code's range, e.g.
   code 7 covers 66–75 %; the file rolls a random value in that window (WBH p.93)
2. **Fluid type** — what the liquid actually is: water, ammonia, liquid hydrocarbons,
   or sulfuric acid, depending on the world's temperature zone (WBH pp.91–92)

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | `random`, `dataclass` |
| `_HYDRO_PCT_RANGE` | Lookup dict: Hydro code → (low %, high %) |
| `_FLUID_TYPE_BY_TEMP` | Lookup dict: temperature zone → fluid name |
| `_NO_SURFACE_LIQUID_ATMS` | Set of atmosphere codes that suppress liquid entirely (gas giant atmospheres) |
| `_AMMONIA_ELIGIBLE_ATMS` | Set of atmosphere codes where Cold temperature → Ammonia fluid (exotic/corrosive/insidious) |
| `HydrographicDetail` dataclass | The two output fields |
| `generate_hydrographic_detail()` | Entry point |

---

## Key Python concept: random range selection

The WBH Hydrographics Ranges table gives a window for each Hydro code:

```python
_HYDRO_PCT_RANGE: dict[int, tuple[int, int]] = {
    0:  (0,   5),
    1:  (6,  15),
    2:  (16, 25),
    ...
    10: (96, 100),
}
```

To get a precise percentage, the code picks uniformly from the window:

```python
low, high = _HYDRO_PCT_RANGE[hydrographics]
surface_liquid_pct = random.randint(low, high)
```

`random.randint(a, b)` returns a random integer between `a` and `b` inclusive.

---

## Key Python concept: frozenset for fast membership tests

Some atmosphere codes suppress surface liquid entirely (exotic, corrosive, gas
giant atmospheres):

```python
_NO_SURFACE_LIQUID_ATMS: frozenset[int] = frozenset({16, 17})
```

`frozenset` is like `set` but **immutable** (can not be changed after creation).
Using `in` with a `frozenset` is O(1) — much faster than checking a list:

```python
if atmosphere in _NO_SURFACE_LIQUID_ATMS:
    fluid_type = None   # no surface liquid for these atmosphere types
```

A second `frozenset` restricts the Cold → Ammonia mapping to only the atmosphere
codes that can physically support an ammonia ocean (exotic, corrosive, insidious,
and unusual atmospheres — codes 10–15). Standard breathable atmospheres (0–9)
keep Water even at Cold temperatures:

```python
_AMMONIA_ELIGIBLE_ATMS: frozenset[int] = frozenset({10, 11, 12, 13, 14, 15})
```

---

## The `HydrographicDetail` dataclass

```python
@dataclass
class HydrographicDetail:
    surface_liquid_pct: int            # precise percentage 0–100
    fluid_type: Optional[str] = None   # "Water", "Ammonia", etc.; None for dry worlds
```

This is a small, two-field dataclass. Both fields are set at construction time.

---

## Fluid type logic

The fluid type depends on the world's temperature zone:

| Temperature zone | Atmosphere codes | Fluid type |
|---|---|---|
| Boiling | any | Sulfuric Acid |
| Hot / Temperate | any | Water |
| Cold | standard breathable (0–9) | Water |
| Cold | exotic/corrosive/insidious (10–15) | Ammonia |
| Frozen | any | Liquid Hydrocarbons |

The Cold/Ammonia combination only applies to exotic, corrosive, insidious, and unusual
atmosphere codes (10–15). A breathable or trace atmosphere at Cold temperatures produces
water — liquid water can persist at low temperatures in sheltered environments. Only
the chemically exotic atmosphere types can sustain a world-ocean of ammonia.

Worlds with hydrographics = 0 (no surface liquid) get `fluid_type = None` regardless
of temperature. Worlds with gas-atmosphere codes (16, 17) also get `None`.

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `HydrographicDetail` | Serialises to `{"surface_liquid_pct": ..., "fluid_type": ...}` |
| `.from_dict(d)` | `HydrographicDetail` | Class method — reconstructs from a dict |
| `generate_hydrographic_detail(hydrographics, size, *, atmosphere, temperature)` | module | Entry point |

---

## How this fits in the pipeline

```
generate_world()
        │  (hydrographics integer is part of the World dataclass)
        ▼
generate_hydrographic_detail(
    hydrographics=world.hydrographics,
    size=world.size,
    atmosphere=world.atmosphere,
    temperature=world.temperature,
)   →  HydrographicDetail
        │
        └─ World.hydrographic_detail = HydrographicDetail
```

`generate_hydrographic_detail()` is called inside `generate_world()` as part of the
standard mainworld generation path. The result is stored as `World.hydrographic_detail`
and serialised alongside the rest of the world in `World.to_dict()`.
