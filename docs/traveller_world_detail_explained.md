# Understanding `traveller_world_detail.py`

A guide for Python beginners. This file generates the detailed profile for every
world in the system — not just the mainworld — and also computes the biological
characteristics (biomass, life complexity, native sophonts) for the mainworld.

---

## What this file does

This file's main function is `attach_detail()`. When called on a `TravellerSystem`,
it:

1. **Secondary worlds** — for every non-empty orbit slot, rolls a SAH (Size/
   Atmosphere/Hydrographics) profile, government, law level, tech level, and moons.
   Each slot's `OrbitSlot.detail` field is filled with a `WorldDetail` object.

2. **Mainworld physical detail** — calls `generate_world_physical()` and optionally
   `generate_advanced_mean_temperature()` for the mainworld.

3. **Belt physical detail** — calls `generate_belt_physical()` for belt mainworlds.

4. **Biological detail** — if the mainworld has a biomass-supporting atmosphere and
   temperature, rolls biomass rating, biocomplexity, sophont presence, biodiversity,
   and compatibility ratings. Sets these on `World` (not on `WorldDetail`).

Implements WBH pp.53–55 (secondary worlds), 44–50 (physical), 125–131 (biology).

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | All sub-generators, `WorldDetail`, `Moon`, `BeltPhysical`, `WorldPhysical` |
| Dice helpers | Local `roll()` function |
| SAH generation | `_generate_sah()` for gas giants, belts, terrestrials |
| Social generation | Government, law level, tech level for secondary worlds |
| `WorldDetail` class | The detail object for one orbit slot |
| `_apply_biomass()` | Orchestrates the full biological detail pipeline |
| Biological generators | `generate_biomass_rating()`, `generate_biocomplexity_rating()` etc. |
| `attach_detail()` | Entry point |

---

## Key Python concept: the `WorldDetail` class

Unlike the `World` dataclass (which uses `@dataclass`), `WorldDetail` uses a manual
`__init__`. This is because it has complex default logic that the `@dataclass`
decorator can not express concisely.

```python
class WorldDetail:
    def __init__(self, sah, population, government, law_level,
                 tech_level, spaceport, moons):
        self.sah = sah               # "000", "GM9", "560", ...
        self.population = population
        self.government = government
        self.law_level  = law_level
        self.tech_level = tech_level
        self.spaceport  = spaceport
        self.moons      = moons      # list of Moon objects
        self.trade_codes: list[str] = []
        self.physical: BeltPhysical | WorldPhysical | None = None
        self.biomass_rating: Optional[int] = None
        self.biocomplexity_rating: Optional[int] = None
```

`trade_codes` and `physical` are set after construction by separate steps.

---

## Key Python concept: `TYPE_CHECKING` imports

`WorldDetail` needs `WorldPhysical` as a type annotation for the `physical` field,
but importing `traveller_world_physical` at the top of the file would work fine at
runtime. To keep Pyright happy without making the import look odd, the import is
placed inside a `TYPE_CHECKING` guard:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from traveller_world_physical import WorldPhysical
```

`TYPE_CHECKING` is `False` at runtime (so the import never actually runs), but
Pyright evaluates it as `True` when doing static analysis. This gives Pyright the
type information it needs without affecting how the program behaves when it runs.
The actual runtime import of `WorldPhysical` happens as a local import inside
`from_dict()`, where it is needed.

---

## Key Python concept: biological DM tables

The biomass and biocomplexity rolls use atmosphere-code DM tables defined as
module-level constants:

```python
_ATM_BIOMASS_DM: dict[int, int] = {
    0: -6, 1: -6, 2: -2, 3: 0, 4: -2, 5: 0, 6: 0, 7: -2, ...
}
```

When computing biomass, the atmosphere code is used as the key:

```python
dm += _ATM_BIOMASS_DM.get(atmosphere, -6)
```

`.get(key, default)` returns `default` if `key` is not in the dict. Here, any
atmosphere code not listed gets `−6` (hostile/unknown environment).

---

## The biological pipeline

`_apply_biomass()` is called for the mainworld only. It runs a chain of dependent
checks:

```
atmosphere + temperature + age
        │
        ▼
generate_biomass_rating()       →  World.biomass_rating
        │
  (skip if biomass == 0)
        │
        ▼
generate_biocomplexity_rating() →  World.biocomplexity_rating
        │
  (if biocomplexity ≥ 8)
        │
        ▼
generate_sophont_checks()       →  World.native_sophont, World.extinct_sophont
        │
        ▼
generate_biodiversity_rating()  →  World.biodiversity_rating
generate_compatibility_rating() →  World.compatibility_rating
        │
        ▼
lifeform_profile = to_hex(M) + to_hex(X) + to_hex(D) + to_hex(C)
                             →  World.lifeform_profile
```

All these fields remain `None` (or `False` for the booleans) if `biomass_rating` is 0.

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `WorldDetail` | Serialises the slot's detail to a plain dict |
| `.from_dict(d)` | `WorldDetail` | Reconstructs from a dict, including nested Moon and physical objects |
| `attach_detail(system, ...)` | module | Entry point — populates every slot and the mainworld biology |
| `generate_biomass_rating(...)` | module | WBH p.127 biomass roll with atmosphere/temperature DMs |
| `generate_biocomplexity_rating(...)` | module | WBH p.129 biocomplexity roll |
| `generate_sophont_checks(...)` | module | WBH p.131 current and extinct sophont rolls |
| `generate_biodiversity_rating(...)` | module | WBH p.130 biodiversity roll |
| `generate_compatibility_rating(...)` | module | WBH p.130 compatibility roll with atmosphere DMs |

---

## How this fits in the pipeline

```
TravellerSystem
        │
        ▼
attach_detail(system, nhz=False, use_oxygen=False, advanced_temp=False)
        │
        ├─ For each non-empty OrbitSlot:
        │       _generate_sah()   →  WorldDetail.sah
        │       social rolls      →  WorldDetail.population / government / law / tech
        │       generate_moons()  →  WorldDetail.moons
        │       OrbitSlot.detail  = WorldDetail
        │
        └─ For mainworld:
                generate_world_physical()           →  World.size_detail
                generate_advanced_mean_temperature() →  WorldPhysical advanced fields
                _apply_biomass()                    →  World.biomass_rating, etc.
```
