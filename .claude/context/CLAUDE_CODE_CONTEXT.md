# Project Context — Traveller World & System Generator

This document is intended for import into Claude Code. It captures the full
project state, architecture, key design decisions, compliance history, and
open work items so development can continue without loss of context.

**Project location:** Extract `traveller-world-gen.zip` and open the
`traveller-world-gen/` folder in VS Code.

**Git state:** One commit on `main` (hash `6c07a67`). No remote configured yet
— see `docs/GITHUB_PUSH.md` for push instructions.

---

## What this project is

A Python implementation of the Traveller RPG star system and world generation
rules, exposed as a REST API via Azure Functions. Two source books are
implemented:

- **CRB** — Traveller 2022 Core Rulebook (Mongoose Publishing), pp. 248–261:
  mainworld generation (all 13 steps).
- **WBH** — World Builder's Handbook, Sept 2023 (Mongoose Publishing):
  stellar generation, orbit placement, secondary world detail, moon generation.

**Licence:** MIT + Mongoose Publishing Fair Use Policy. Non-commercial only.
Every Python source file contains the required IP notice in its module docstring.

---

## Repository layout

```
traveller-world-gen/
├── traveller_stellar_gen.py     # WBH pp.14-29: stars, multiples, age
├── traveller_orbit_gen.py       # WBH pp.36-51: orbits, HZ, MAO, spread
├── traveller_system_gen.py      # Integration + TravellerSystem.to_html()
├── traveller_world_gen.py       # CRB pp.248-261: mainworld, UWP, trade codes
├── traveller_world_detail.py    # Secondary world SAH/social + moon detail
├── traveller_moon_gen.py        # Moon quantity, sizing, SAH, social
├── traveller_world_schema.json  # JSON Schema (draft 2020-12) for World.to_dict()
├── function_app.py              # Azure Functions v2 — 9 HTTP endpoints
├── shared/helpers.py            # Request parsing, response builders, error codes
├── tests/
│   ├── test_traveller_world_gen.py  # ~2,940 lines, 342 tests
│   └── test_function_app.py         # ~976 lines, 98 tests
├── conftest.py                  # pytest path setup + azure.functions stub
├── pytest.ini                   # Test discovery config
├── host.json                    # Azure Functions host config
├── requirements.txt             # azure-functions>=1.18.0, jsonschema>=4.21,<5
├── local.settings.json.example  # Template — copy to local.settings.json
├── docs/
│   ├── AZURE_DEPLOYMENT.md      # Full REST API reference (bash + PowerShell)
│   ├── developer-guide.md       # Architecture, compliance notes, deferred features
│   └── GITHUB_PUSH.md           # GitHub push instructions (gh CLI + web UI)
└── .vscode/                     # VS Code settings and extension recommendations
```

---

## File sizes

| File | Lines | Description |
|------|-------|-------------|
| `traveller_stellar_gen.py` | 1,114 | WBH stellar generation (pp.14-29) |
| `traveller_orbit_gen.py` | 542 | WBH orbit placement (pp.36-51) |
| `traveller_system_gen.py` | 658 | Integration layer + TravellerSystem.to_html() |
| `traveller_world_gen.py` | 1,460 | CRB mainworld generation (pp.248-261) |
| `traveller_world_detail.py` | 734 | Secondary world SAH/social + satellite detail |
| `traveller_moon_gen.py` | 342 | Significant moon quantity, sizing, detail |
| `traveller_world_schema.json` | 346 | JSON Schema draft 2020-12 for World.to_dict() |
| `function_app.py` | 370 | Azure Functions v2 — 9 HTTP endpoints |
| `shared/helpers.py` | 278 | Request parsing, response builders, error codes |
| `tests/test_traveller_world_gen.py` | 2,940 | Unit tests — mainworld generation |
| `tests/test_function_app.py` | 976 | Unit tests — API endpoints |
| `docs/AZURE_DEPLOYMENT.md` | 805 | Full REST API reference (bash + PowerShell) |
| `docs/developer-guide.md` | 593 | Architecture, module reference, compliance notes |
| `docs/GITHUB_PUSH.md` | 166 | GitHub push instructions |

---

## Generation pipeline

The pipeline is strictly one-directional. Each stage consumes the output of
the previous one; nothing feeds back upstream.

```
generate_stellar_data()          →  StarSystem
        ↓
generate_orbits(stellar_system)  →  SystemOrbits
        ↓
generate_full_system(name, seed) →  TravellerSystem
        ↓  (optional — expensive)
attach_detail(system)            →  populates orbit.detail (WorldDetail)
                                    and moon.detail (WorldDetail) on all slots
```

`generate_full_system()` in `traveller_system_gen.py` is the main entry point.
`attach_detail()` is always a separate step — it adds secondary world profiles
and satellite detail for every orbit and moon, but is not called automatically
because it is expensive (O(total moons) additional RNG calls).

**RNG state is global.** All modules use `random.seed()` / `random.randint()`
on Python's global `random` module. The same seed always produces the same
system. Adding any dice roll anywhere in the pipeline shifts all subsequent
results for a given seed.

---

## Key data structures

### `Star` (traveller_stellar_gen.py)
```python
designation: str        # "A", "Aa", "Ab", "B", "Ca"
role: str               # "primary"|"companion"|"close"|"near"|"far"
spectral_type: str      # "O"|"B"|"A"|"F"|"G"|"K"|"M"|"D"|"BD"
subtype: Optional[int]  # 0-9; None for D/BD
lum_class: str          # "Ia"|"Ib"|"II"|"III"|"IV"|"V"|"VI"|"D"|"BD"
mass: float             # Solar masses
temperature: int        # Kelvin
diameter: float         # Solar diameters
luminosity: float       # Solar luminosities (Stefan-Boltzmann)
orbit_number: float     # Orbit# (0.0 for primary)
orbit_au: float
age_gyr: float
ms_lifespan_gyr: float
```

### `OrbitSlot` (traveller_orbit_gen.py)
```python
star_designation: str
orbit_number: float     # WBH Orbit# — non-linear with AU
orbit_au: float
slot_index: int
world_type: str         # "gas_giant"|"terrestrial"|"belt"|"empty"
is_habitable_zone: bool # |hz_deviation| <= 1.0
hz_deviation: float     # orbit_number - HZCO; negative = warmer
temperature_zone: str   # "boiling"|"hot"|"temperate"|"cold"|"frozen"
is_mainworld_candidate: bool
notes: str
detail: Optional[WorldDetail]  # set by attach_detail()
```

### `SystemOrbits` (traveller_orbit_gen.py)
```python
stellar_system: StarSystem
gas_giant_count: int; belt_count: int; terrestrial_count: int
total_worlds: int; empty_orbits: int
orbits: List[OrbitSlot]         # sorted by (star_designation, orbit_au)
mainworld_orbit: Optional[OrbitSlot]
star_mao: Dict[str, float]      # Minimum Allowable Orbit# per star
star_hzco: Dict[str, float]     # HZCO per star
star_hz_inner: Dict[str, float] # HZCO - 1.0 (clamped to MAO)
star_hz_outer: Dict[str, float] # HZCO + 1.0
```

### `TravellerSystem` (traveller_system_gen.py)
```python
stellar_system: StarSystem
system_orbits: SystemOrbits
mainworld: Optional[World]
mainworld_orbit: Optional[OrbitSlot]
# methods: .to_dict(), .to_json(), .to_html(detail_attached), .summary()
```

### `World` (traveller_world_gen.py)
```python
name: str; size: int; atmosphere: int; temperature: str
hydrographics: int; population: int; government: int
law_level: int; starport: str; tech_level: int
has_gas_giant: bool; gas_giant_count: int; belt_count: int
population_multiplier: int   # WBH "P" digit (1-9; 0 if uninhabited)
bases: List[str]             # "N"|"S"|"M"|"H"|"C"
trade_codes: List[str]       # e.g. ["Ag","Ni","Ri"]
travel_zone: str             # "Green"|"Amber"|"Red"
notes: List[str]
# methods: .uwp(), .to_dict(), .to_json(), .to_html(), .summary()
```

### `WorldDetail` (traveller_world_detail.py)
Uses `__slots__` for memory efficiency (not a dataclass).
```python
sah: str           # 3-char Size/Atmosphere/Hydrographics
population: int    # 0 = uninhabited
government: int; law_level: int; tech_level: int
spaceport: str     # Y/H/G/F for secondaries; "-" for gas giants
moons: list        # List[Moon]
# properties: .inhabited, .is_gas_giant, .profile
# methods: .to_dict()
```

### `Moon` (traveller_moon_gen.py)
```python
size_code: int | str    # int 0-15, "S" for size S, 0+is_ring for ring
is_ring: bool
is_gas_giant_moon: bool # moon is itself a small gas giant
detail: Optional[WorldDetail]  # populated by attach_detail()
# _ring_count: int  -- informal attr set by _consolidate() on ring entries
# properties: .size_str
# methods: .to_dict()
```

---

## HZ deviation sign convention

**Negative deviation** = orbit is closer to the star than the HZCO = **warmer**.
**Positive deviation** = orbit is further from the star than the HZCO = **cooler**.

This matches the WBH Habitable Zones Regions table where:
- deviation ≤ −1.1 → raw roll 12+ → Boiling
- deviation = 0.0  → raw roll 7  → Temperate (HZCO)
- deviation ≥ +1.1 → raw roll 2− → Frozen

The raw roll is passed to `generate_temperature_from_orbit()` in
`traveller_system_gen.py`, which applies atmosphere DMs and returns a
temperature category string.

---

## Orbit# vs AU — critical note

The WBH Orbit# scale is **non-linear** with respect to AU. The conversion
table is in `_orbit_to_au()` in `traveller_stellar_gen.py`. When drawing maps
or computing habitable zone display boundaries, always convert Orbit# to AU
first using this function. Never use Orbit# values directly as radial distances
on an AU-scaled diagram — this was the cause of an incorrect HZ shading bug
in a system map (outer HZ edge appeared to extend to the edge of the system).

---

## Profile string formats

| Body type | Format | Example |
|-----------|--------|---------|
| Mainworld | `{port}{SAH}{PGL}-{TL}` | `C473574-8` |
| Inhabited secondary | `{port}{SAH}{PGL}-{TL}` | `F473510-7` |
| Uninhabited terrestrial | `Y{SAH}000-0` | `Y473000-0` |
| Inhabited belt | `{port}000{PGL}-{TL}` | `G000121-8` |
| Uninhabited belt | `Y000000-0` | |
| Gas giant | SAH only | `GM9`, `GS4`, `GLB` |
| Inhabited moon (size 2+) | `{port}{SAH}{PGL}-{TL}` | `F532320-6` |
| Uninhabited moon (size 2+) | `Y{SAH}000-0` | `Y300000-0` |
| Size S moon | `YS00000-0` | |
| Size 0–1 moon | `Y{sz}00000-0` | `Y100000-0` |
| Ring | `R0{count}` | `R01`, `R03` |

Secondary spaceport codes (WBH scale, not the CRB starport scale):
Y = no spaceport, H = primitive, G = basic/unrefined fuel, F = good/unrefined.

---

## API endpoints

Nine HTTP endpoints in `function_app.py`:

### Mainworld (CRB only — fast, no orbital context)
| Method | Route | Description |
|--------|-------|-------------|
| GET/POST | `/api/world` | Generate one mainworld |
| GET | `/api/world/{name}` | Mainworld by URL name |
| POST | `/api/worlds` | Batch (up to `TRAVELLER_MAX_BATCH_SIZE`, default 20) |
| GET | `/api/world/{name}/card` | Standalone HTML card |

### System (WBH stellar + orbit + CRB mainworld)
| Method | Route | Description |
|--------|-------|-------------|
| GET/POST | `/api/system` | Full system JSON |
| GET | `/api/system/{name}` | Full system JSON by URL name |
| GET | `/api/system/{name}/card` | Standalone HTML system card |

The `detail` parameter (query string `?detail=true` or JSON body `{"detail": true}`)
triggers `attach_detail()` on system endpoints, adding secondary world SAH/social
profiles and satellite data for every orbit and moon.

All parameters: `name` (str, max 64 chars), `seed` (int), `detail` (bool),
`count` (int, batch only), `prefix` (str, max 32 chars, batch only).

Error codes: `INVALID_SEED`, `INVALID_COUNT`, `COUNT_TOO_LARGE`,
`INVALID_BODY`, `NAME_TOO_LONG`, `INTERNAL_ERROR`.

---

## Compliance audit results

A formal compliance audit was run against WBH rules across 5,000 generated
systems. All of the following were found and fixed:

### Orbit generation bugs (traveller_orbit_gen.py) — fixed earlier in session
1. **Step 3b cold-system baseline formula** — was `total_slots * 0.1`, correct
   formula uses `n_worlds` as whole Orbit# units. Post-fix: 0 violations.
2. **Step 5 max_spread denominator** — used constant `+1` instead of
   `n_total_stars`. Fixed.
3. **Step 6 outermost orbit clamping** — clamp applied after rather than
   before appending. Fixed.

### Secondary world / moon bugs (traveller_world_detail.py, traveller_moon_gen.py) — fixed in this session
4. **Moon size exceeds parent (WBH p.57)** — `D3-1` in `_size_terrestrial_moon()`
   could produce size 2 for a size-1 parent. Fixed: clamp `sz = min(sz, parent_size)`.
5. **r=6 branch sign error** — negative result should give size S, zero gives ring;
   both were producing a ring. Fixed in `_size_terrestrial_moon()`.
6. **Belt mainworlds generating moons** — `generate_moons(size_code=0, ...)` was
   not guarded; belts are diffuse debris fields. Fixed: early return `[]` when
   `size_code == 0`. Also fixed in `attach_detail()`: when `orbit.world_type == "belt"`,
   force `mw_size = 0` regardless of what the `World` object reports (the CRB
   generation doesn't know its host orbit type).
7. **Belt mainworld wrong physical profile** — a belt orbit selected as mainworld
   still ran full CRB size/atmosphere/hydrographics rolls, producing e.g. a size-7
   corrosive-atmosphere world. Fixed in `generate_mainworld_at_orbit()`: when
   `orbit.world_type == "belt"`, force size=0, atm=0, hydro=0. The social pipeline
   (population, government, law, TL, trade codes) runs normally, so `As` (Asteroid)
   trade code fires correctly.

**Post-fix audit: 0 violations across 5,000 systems.**

---

## Key design decisions

**Orbital temperature, not random.** All worlds (mainworld, secondaries, moons)
derive temperature from HZ deviation rather than an independent dice roll.
`generate_temperature_from_orbit()` in `traveller_system_gen.py` is the single
source of truth. Moons use their *parent planet's* HZ deviation, not their own
position (they share the parent's orbital distance from the star).

**Single RNG stream.** All generation code shares Python's global `random`
state. The seed is set once at the top of `generate_full_system()`. Adding
any new dice roll shifts all subsequent results for any given seed. Place new
rolls at the end of the pipeline to minimise seed disruption.

**`attach_detail()` is always a separate step.** It is expensive and not
always needed. Never call it automatically inside `generate_full_system()`.

**Secondary government defaults to dependent (Case 1).** The WBH offers
two procedures; independent government (Case 2) is not yet implemented.

**Belt mainworlds:** the orbit scorer can select a belt slot as the mainworld.
The `World` object from CRB generation is agnostic to orbit type, so the
physical override in `generate_mainworld_at_orbit()` is essential for
correctness.

---

## Output method status

All output methods were audited and updated. Current state:

| Method | Notes |
|--------|-------|
| `World.to_dict()` / `to_json()` | Complete. Conforms to `traveller_world_schema.json`. |
| `World.to_html()` | Mainworld-only card. Correct by design — no system context. |
| `World.summary()` | Text block. Complete. |
| `TravellerSystem.to_dict()` / `to_json()` | Complete. Includes `detail` on orbit entries when `attach_detail()` has run. |
| `TravellerSystem.to_html(detail_attached)` | System card with stellar table, orbital table (with moon sub-rows when `detail_attached=True`), mainworld panel. |
| `TravellerSystem.summary()` | Auto-detects whether `attach_detail()` has run; delegates to `system_body_table()` if so, `SystemOrbits.summary()` if not. |
| `SystemOrbits.summary()` | Shows profile column when detail is attached, `—` otherwise. |
| `OrbitSlot.to_dict()` | Includes `detail` key when `attach_detail()` has run. |
| `WorldDetail.to_dict()` | Includes `moons` as list of `Moon.to_dict()` objects. |
| `Moon.to_dict()` | Includes nested `detail` object when present. |

---

## Deferred / not yet implemented

These WBH features are explicitly out of scope for the current codebase.
Page references are to the WBH Sept 2023 edition.

| Feature | Pages | Notes |
|---------|-------|-------|
| Anomalous orbits (Step 7) | pp.49-50 | Random, eccentric, inclined, retrograde, trojan |
| Eccentricity (Step 9) | p.51 | Affects moon DMs and Hill spheres |
| Orbital periods | — | `P = √(AU³/M)` |
| Moon orbit adjacency DMs (3 of 4 conditions) | p.56 | Require eccentricity data |
| Moon orbit placement | pp.74-77 | Hill sphere, Roche limit, PD distances |
| Post-stellar special circumstances | pp.219+ | White dwarfs, neutron stars characterised but not detailed |
| Secondary world independent government (Case 2) | p.162 | Currently all use Case 1 (dependent) |
| Secondary world classifications | p.163 | Colony, Farming, Freeport, Mining Facility, etc. |
| World physical detail beyond SAH | pp.74-130 | Density, gravity, seismic stress, atmospheric composition |
| Belt physical detail | pp.131-133 | Span, composition, bulk, resource rating |

---

## Running locally

```bash
# Setup
cp local.settings.json.example local.settings.json
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run the Azure Functions host
func start

# Generate a system from the CLI
python traveller_system_gen.py --name Ardenne --seed 1000
python traveller_world_gen.py --name Cogri --seed 42 --json

# Run tests (pytest required: pip install pytest jsonschema)
pytest tests/ -v
```

---

## Typical usage patterns (Python)

```python
# Full system — no secondary detail (fast)
from traveller_system_gen import generate_full_system
system = generate_full_system(name="Ardenne", seed=1000)
print(system.summary())
print(system.to_json())

# Full system with secondary world and satellite detail
from traveller_world_detail import attach_detail, system_body_table
system = generate_full_system(name="Varanthos", seed=6056)
attach_detail(system)
print(system_body_table(system))          # text table with moon sub-rows
print(system.to_json())                   # full JSON hierarchy
html = system.to_html(detail_attached=True)  # standalone HTML card

# Mainworld only
from traveller_world_gen import generate_world
world = generate_world(name="Mora")
print(world.uwp())           # e.g. "C473574-8"
print(world.trade_codes)     # e.g. ["Ag", "Ni"]
print(world.to_html())       # standalone HTML card

# Accessing secondary world data after attach_detail()
for orbit in system.system_orbits.orbits:
    detail = getattr(orbit, "detail", None)
    if detail and detail.inhabited:
        print(f"  {orbit.orbit_number:.2f}: {detail.profile}  pop={detail.population}")
        for moon in detail.moons:
            if moon.detail and moon.detail.inhabited:
                print(f"    moon: {moon.detail.profile}")
```

---

## Session history summary

This project was built across four Claude.ai conversation sessions:

1. **Session 1** (2026-04-14): CRB mainworld generation, UWP, trade codes,
   JSON Schema, HTML card, Azure Functions (5 endpoints), test suite.

2. **Session 2** (2026-04-17): WBH stellar generation, orbit placement,
   system integration, orbital temperature, three orbit compliance bug fixes.

3. **Session 3** (2026-04-18): Secondary world SAH/social detail, moon
   generation quantity/sizing, moon SAH/social detail, compliance audit.

4. **Session 4** (2026-04-19): Belt population fix, belt mainworld fix,
   moon size clamping fix, JSON serialisation of all detail data, summary()
   method updates, four new system API endpoints, REST API documentation
   (bash + PowerShell), GitHub prep, ZIP archive.

All source books (CRB PDF, WBH PDF, FAQ PDF) were provided as project
knowledge and used to verify every rules implementation during development.
