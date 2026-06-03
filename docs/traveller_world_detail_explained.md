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
   and compatibility ratings. Sets these on `World` (not on `WorldDetail`). After
   this step, `apply_biological_resource_dms()` is called to apply biomass,
   biodiversity, and compatibility DMs to the world's `resource_rating`
   (deterministic — no new dice roll).

5. **Habitability rating** — after biological detail, computes the WBH p.131
   Habitability Rating for the mainworld (base 10 + DMs for size, atmosphere,
   hydrographics, tidal lock, temperature, and gravity). No dice rolls; always runs
   after `_apply_biomass()` so low-oxygen taint is available.

Implements WBH pp.53–55 (secondary worlds), 44–50 (physical), 125–131 (biology, habitability).

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
| `_apply_habitability()` | Orchestrates the habitability rating pipeline |
| Habitability generators | `generate_habitability_rating()`, `_gravity_habitability_dm()`, `_atmosphere_habitability_dm()` |
| `attach_detail()` | Entry point |

---

## Key Python concept: the `WorldDetail` class

Unlike the `World` dataclass (which uses `@dataclass`), `WorldDetail` uses a manual
`__init__`. This is because it has complex default logic that the `@dataclass`
decorator can not express concisely.

```python
class WorldDetail:
    def __init__(self, sah, population, government, law_level,
                 tech_level, spaceport, moons,
                 is_independent_government=False):
        self.sah = sah               # "000", "GM9", "560", ...
        self.population = population
        self.government = government
        self.law_level  = law_level
        self.tech_level = tech_level
        self.spaceport  = spaceport
        self.moons      = moons      # list of Moon objects
        self.is_independent_government = is_independent_government
        self.classification: Optional[str] = None  # e.g. "Cy", "Fa", "Mi"
        self.trade_codes: list[str] = []
        self.physical: BeltPhysical | WorldPhysical | None = None
        self.biomass_rating: Optional[int] = None
        self.biocomplexity_rating: Optional[int] = None
        self.habitability_rating: Optional[int] = None
        self.native_sophont: bool = False
```

`trade_codes`, `physical`, the rating fields, `is_independent_government`,
`native_sophont`, and `classification` are set at construction time or by separate
steps. `is_independent_government` is `True` when the world was generated with
Case 2 (independent) government; `native_sophont` is `True` when a native sophont
was confirmed via `generate_sophont_checks()` during `_apply_biomass()`. Both
fields are emitted in `to_dict()` only when `True`. `classification` is the
WBH p.163 secondary world role code (e.g. `"Cy"` = Colony, `"Mi"` = Mining
Facility); emitted in `to_dict()` only when not `None`, and the code is also
appended to `trade_codes` so it appears in all profile displays.

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

## Secondary world classification (WBH p.163)

After a secondary world or moon is assigned its social codes, the code checks
whether it qualifies for one of seven WBH p.163 classification roles. The first
qualifying classification in table order is assigned — a world can only have one.

| Role | Code | What it means | How it's assigned |
|------|------|--------------|-----------------|
| Colony | Cy | A population of 5+ under a colonial government | Automatic if Pop ≥ 5 and Gov = 6 |
| Farming | Fa | An agricultural world in the habitable zone | Automatic if HZ, Atm 4–9, Hyd 2+ |
| Freeport | Fp | An independently governed trading hub | Roll 10+ (DM−2 if mainworld starport A or B) |
| Military Base | Mb | A garrison under an authoritarian mainworld | Roll 12+ (DM+4 if mainworld has bases) |
| Mining Facility | Mi | An industrial extraction site | Belt: roll 6+; terrestrial: roll 10+ |
| Penal Colony | Pe | A prison world under a strict mainworld | Roll 10+ (DM+2 if secondary LL ≥ 8) |
| Research Base | Rb | A scientific installation | Roll 10+ (DM+2 if mainworld TL ≥ 12) |

Colony and Farming are **automatic** — no dice roll needed if requirements are
met. The rest are probabilistic. Belts can only qualify for Mining Facility.
Gas giants and uninhabited worlds are never classified.

The two-letter code (e.g. `"Cy"`) is stored in `WorldDetail.classification` and
is also appended to `trade_codes`, so it appears alongside trade codes like `Ag`
or `Ni` in the system body table and JSON output.

---

## Secondary world government: Case 1 vs Case 2

WBH p.162 defines two ways to determine a secondary world's government, and the
code supports both.

**Case 1 — Dependent/Captive (default):** The secondary world is under direct
control of the mainworld's government. Roll 1D on the Secondary World Government
table with DMs based on the mainworld's government code. This produces only
government codes 0, 1, 2, 3, or 6.

```python
def _secondary_government(mainworld_pop, mainworld_gov):
    r = _rng.randint(1, 6)
    if mainworld_gov == 0: r = max(1, r - 2)
    elif mainworld_gov == 6: r += mainworld_pop
    if r <= 1: return 0
    if r <= 2: return 1
    ...
    return 6  # captive government
```

**Case 2 — Independent:** The secondary world governs itself. Roll `2D − 7 +
Population`, the same formula used for a mainworld. This can produce any
government code from 0 upwards.

```python
def _independent_government(population):
    return max(0, _roll(2, -7 + population))
```

The Case 2 path is activated by passing `independent_government=True` to
`attach_detail()`. When this is enabled, the law-level calculation for government
code 6 also changes: Case 1 uses a captive-relationship table (is the secondary
world more or less lawful than the mainworld?), but Case 2 treats government 6 as
an ordinary Feudal Technocracy and uses the standard `2D − 7 + Government`
formula.

The `WorldDetail.is_independent_government` flag records which path was used so
the information is preserved in saved JSON files.

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

After `_apply_biomass()` completes, `_apply_habitability()` runs unconditionally:

```
size + atmosphere + hydrographics + gravity + tidal_status
+ has_low_oxygen_taint (from biomass step)
+ advanced_mean_temperature_k / high_temperature_k (or temperature_category fallback)
        │
        ▼
generate_habitability_rating()  →  World.habitability_rating
                                →  WorldDetail.habitability_rating
```

No dice are rolled; the rating is purely deterministic from world characteristics.

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `WorldDetail` | Serialises the slot's detail to a plain dict |
| `.from_dict(d)` | `WorldDetail` | Reconstructs from a dict, including nested Moon and physical objects |
| `attach_detail(system, ..., rng=None)` | module | Entry point — populates every slot, mainworld biology, and habitability |
| `apply_secondary_social(system, independent_government, rng)` | module | Re-applies social data to all secondary WorldDetails after `apply_mainworld_social()`. Re-rolls population cap; regenerates government, law, TL, spaceport, trade codes, and classification for every secondary and moon. Also syncs mainworld's real social data back to the satellite WorldDetail. |
| `generate_system_detail(system, ..., rng=None)` | module | Alias / variant entry point; also accepts `rng` |
| `generate_biomass_rating(...)` | module | WBH p.127 biomass roll with atmosphere/temperature DMs |
| `generate_biocomplexity_rating(...)` | module | WBH p.129 biocomplexity roll |
| `generate_sophont_checks(...)` | module | WBH p.131 current and extinct sophont rolls |
| `generate_biodiversity_rating(...)` | module | WBH p.130 biodiversity roll |
| `generate_compatibility_rating(...)` | module | WBH p.130 compatibility roll with atmosphere DMs |
| `generate_habitability_rating(...)` | module | WBH p.131 habitability rating — base 10 + DMs, no dice |

---

## How this fits in the pipeline

```
TravellerSystem (mainworld has placeholder social data: starport='X', pop=0)
        │
        ▼
attach_detail(system, independent_government=False, ...)
        │
        ├─ For each non-empty OrbitSlot (secondaries):
        │       _generate_sah()        →  WorldDetail.sah
        │       social rolls           →  WorldDetail.population / government / law / tech
        │       (Case 1 or Case 2 per independent_government flag)
        │       WorldDetail.is_independent_government set accordingly
        │       _apply_classification() →  WorldDetail.classification + trade_codes
        │       WorldDetail.native_sophont set by _set_biocomplexity() when bio ≥ 8
        │       _moons_for()           →  generate_moons(), moon WorldDetails
        │       OrbitSlot.detail       = WorldDetail
        │
        └─ For mainworld:
                generate_world_physical()            →  World.size_detail
                generate_advanced_mean_temperature() →  WorldPhysical advanced fields
                _apply_biomass()                     →  World.biomass_rating, etc.
                _apply_habitability()                →  World.habitability_rating
                                                        WorldDetail.habitability_rating
        │
        ▼ (after select_mainworld() and apply_mainworld_social())
        │
apply_secondary_social(system, independent_government, rng)
        ├─ Re-rolls population cap from mainworld's real population
        ├─ For mainworld orbit satellite WorldDetail: syncs real social data back
        ├─ For all secondary orbit WorldDetails and their moons:
        │       _secondary_population() / government / law / TL / spaceport
        │       assign_trade_codes()
        │       _apply_classification() →  WorldDetail.classification + trade_codes
        └─ Physical data (SAH, biomass, habitability) is untouched
```
