# Traveller World Generator — Developer Guide

A technical reference for developers working on the `traveller-world-gen` codebase. Covers architecture, data flow, module APIs, known compliance decisions, and deferred features.

---

## Contents

1. [Project overview](#1-project-overview)
2. [Repository layout](#2-repository-layout)
3. [Architecture and data flow](#3-architecture-and-data-flow)
4. [Module reference](#4-module-reference)
   - [traveller_stellar_gen.py](#41-traveller_stellar_genpy)
   - [traveller_orbit_gen.py](#42-traveller_orbit_genpy)
   - [traveller_system_gen.py](#43-traveller_system_genpy)
   - [traveller_world_gen.py](#44-traveller_world_genpy)
   - [traveller_world_detail.py](#45-traveller_world_detailpy)
   - [traveller_moon_gen.py](#46-traveller_moon_genpy)
   - [function_app.py and shared/helpers.py](#47-function_apppy-and-sharedhelperspy)
   - [traveller_map_fetch.py](#48-traveller_map_fetchpy)
   - [system_map.py](#49-system_mappy)
5. [Key design decisions](#5-key-design-decisions)
6. [Compliance audit history](#6-compliance-audit-history)
7. [Deferred and out-of-scope features](#7-deferred-and-out-of-scope-features)
8. [Reproducibility and seeding](#8-reproducibility-and-seeding)
9. [Profile string formats](#9-profile-string-formats)
10. [Running and testing](#10-running-and-testing)
11. [Licence and IP constraints](#11-licence-and-ip-constraints)

---

## 1. Project overview

This project implements the star system and world generation procedures from two source books:

- **CRB** — Traveller 2022 Core Rulebook (Mongoose Publishing), pp. 248–261: mainworld generation.
- **WBH** — World Builder's Handbook, Sept 2023 edition (Mongoose Publishing): stellar generation, orbit placement, secondary world physical and social characteristics, moon generation.

Generation is procedural and dice-driven, using Python's `random` module. Every result is reproducible given the same seed. The output is a fully-populated `TravellerSystem` object with nested stellar, orbital, world, and satellite data, serialisable to JSON.

---

## 2. Repository layout

```
traveller-world-gen/
├── traveller_stellar_gen.py    # Stars: type, mass, luminosity, multiples, age
├── traveller_orbit_gen.py      # Orbit placement: MAO, HZCO, spread, world slots
├── traveller_system_gen.py     # Integration: stellar + orbits + mainworld
├── traveller_world_gen.py      # Mainworld: all 13 CRB steps, UWP, trade codes
├── traveller_world_detail.py   # Secondary worlds and satellites: SAH + social
├── traveller_moon_gen.py       # Moon quantity, sizing, and SAH/social detail
├── traveller_map_fetch.py      # TravellerMap integration: fetch, parse UWP + stellar, reconstruct system
├── traveller_world_schema.json # JSON Schema (draft 2020-12) for World.to_dict()
├── system_map.py               # SVG star system map: per-star arc zones, log-AU radial scale, orbit table
│
├── function_app.py             # Azure Functions HTTP endpoints (13 routes)
├── shared/
│   └── helpers.py              # Request parsing, response builders, error codes
├── gen-ui/
│   ├── app.py                  # PySide6 (Qt6) desktop UI — fully working
│   ├── README.md               # Setup, usage, and keyboard shortcut reference
│   └── requirements.txt        # Dependency list (PySide6>=6.4.0; bundled Qt, no system libs required)
│
├── tests/
│   ├── test_traveller_world_gen.py   # Unit tests — mainworld generation
│   └── test_function_app.py          # Unit tests — API layer
│
├── LICENSE                     # MIT Licence + Traveller IP notice
├── README.md                   # End-user documentation
└── docs/
    └── developer-guide.md      # This file
```

---

## 3. Architecture and data flow

The pipeline runs in one direction. Each stage consumes the output of the previous one; nothing feeds back upstream.

```
generate_stellar_data()          →  StarSystem
       ↓
generate_orbits(stellar_system)  →  SystemOrbits
       ↓
generate_full_system(name, seed) →  TravellerSystem
       ↓
attach_detail(system)            →  populates orbit.detail (WorldDetail)
                                    and moon.detail (WorldDetail) on all slots
```

For TravellerMap-seeded systems, the pipeline starts differently:

```
_name_to_hex(name, sector)         →  hex position  (via /api/search — skipped if hex given)
       ↓
GET /data/{sector}/{hex}           →  MapWorldData  (canonical UWP + PBG + stellar string)
       ↓
reconstruct_star_system(stars_str) →  StarSystem   (canonical types, random orbits)
reconstruct_world(map_data)        →  World        (canonical UWP, no dice)
       ↓
generate_orbits(stellar)           →  SystemOrbits (procedural)
PBG reconciliation                 →  overrides gas/belt counts with canonical values
canonical_profile stamped          →  mainworld orbit slot gets canonical UWP
       ↓
generate_temperature_from_orbit()  →  injects temperature from orbital position
       ↓
TravellerSystem (assembled)
       ↓
attach_detail(system)              →  optional secondary detail
```

`generate_full_system()` in `traveller_system_gen.py` is the main entry point for most callers. It calls the stellar and orbit generators internally, then constructs the mainworld using `generate_mainworld_at_orbit()`. Calling `attach_detail()` afterwards populates secondary world and moon data; this is a separate step because it is expensive and not always needed.

For systems built from an existing mainworld JSON, a separate path is provided:

```
World.from_dict(world_dict)        →  World  (UWP/PBG preserved, no dice)
       ↓
generate_system_from_world(world, seed)
       ↓
generate_stellar_data()            →  StarSystem  (fresh procedural)
generate_orbits()                  →  SystemOrbits (fresh procedural)
PBG reconciliation                 →  overrides orbit gas/belt counts with world values
canonical_profile stamped          →  mainworld orbit slot gets world.uwp()
generate_temperature_from_orbit()  →  temperature recalculated from new orbital HZ deviation
       ↓
TravellerSystem  (assembled)
       ↓  (optional)
attach_detail()
```

**RNG state is global.** All modules use `random.seed()` / `random.randint()` directly. The seed is set once at the top of `generate_full_system()` when a seed is provided, and every subsequent roll in the pipeline consumes from that same RNG sequence. This means the order of calls matters: adding or removing any roll anywhere in the pipeline will shift all subsequent results for a given seed.

---

## 4. Module reference

### 4.1 `traveller_stellar_gen.py`

Implements WBH pp. 14–29.

**Key public API:**

```python
system: StarSystem = generate_stellar_data()
```

This is the only public entry point. It generates a complete stellar system, including all secondary and companion stars.

**Key dataclasses:**

```python
@dataclass
class Star:
    designation: str        # e.g. "A", "Aa", "Ab", "B", "Ca"
    role: str               # "primary" | "companion" | "close" | "near" | "far"
    spectral_type: str      # "O","B","A","F","G","K","M","D","BD"
    subtype: Optional[int]  # 0–9; None for white dwarfs (D) and brown dwarfs (BD)
    lum_class: str          # "Ia","Ib","II","III","IV","V","VI","D","BD"
    mass: float             # Solar masses
    temperature: int        # Kelvin
    diameter: float         # Solar diameters
    luminosity: float       # Solar luminosities (Stefan-Boltzmann derived)
    orbit_number: float     # Orbit# of this star around the primary (0.0 for primary)
    orbit_au: float         # AU equivalent
    age_gyr: float          # System age in Gyr (same for all stars)
    ms_lifespan_gyr: float  # Main sequence lifespan in Gyr

@dataclass
class StarSystem:
    stars: List[Star]       # Index 0 is always the primary
    # properties: .primary, .age_gyr
```

**Companion vs secondary stars:** Companion stars share the same `orbit_number` as their parent and have `role="companion"`. Their designation is the parent's designation plus a lowercase letter (e.g., parent `"A"` → companion `"Aa"`, `"Ab"`). Close/Near/Far secondary stars have `role` set to their separation type and a separate `orbit_number`.

**Mass ordering invariant:** The primary star is always the most massive. Non-primary star types are determined by comparing `candidate.mass > parent.mass`, not by spectral letter alone (M0 V = 0.50 M☉ vs M7 V = 0.12 M☉ — same letter, very different mass). This was a compliance bug fixed during development.

**Internal functions of note:**

- `_star_properties(spectral, subtype, lum_class)` — interpolates mass, temperature, and diameter from lookup tables.
- `_determine_non_primary_type(parent, role)` — determines type (Random/Lesser/Sibling/Twin) and generates the star.
- `_orbit_to_au(orbit_num)` — converts Orbit# to AU using the WBH table. This function is imported by `traveller_orbit_gen.py`.

---

### 4.2 `traveller_orbit_gen.py`

Implements WBH pp. 36–51.

**Key public API:**

```python
orbits: SystemOrbits = generate_orbits(system: StarSystem)
mao: float = get_mao(star: Star)
hzco: float = get_hzco(star: Star, combined_lum: Optional[float])
```

**Key dataclasses:**

```python
@dataclass
class OrbitSlot:
    star_designation: str
    orbit_number: float
    orbit_au: float
    slot_index: int
    world_type: str         # "gas_giant" | "terrestrial" | "belt" | "empty"
    is_habitable_zone: bool # True if |hz_deviation| <= 1.0
    hz_deviation: float     # orbit_number - HZCO; negative = warmer, positive = cooler
    temperature_zone: str   # "boiling"|"hot"|"temperate"|"cold"|"frozen"
    is_mainworld_candidate: bool  # True for the selected mainworld orbit
    notes: str
    canonical_profile: str  # set by generate_system_from_map() — canonical UWP of the
                            # mainworld placed here; takes display priority over detail.profile
    gg_sah: str             # gas giant SAH rolled at orbit-gen time (e.g. "GM9");
                            # empty string for non-gas-giant slots
    detail: Optional[WorldDetail] = field(default=None, init=False)
                            # populated by attach_detail(); None until then

@dataclass
class SystemOrbits:
    stellar_system: StarSystem
    gas_giant_count: int
    belt_count: int
    terrestrial_count: int
    total_worlds: int
    empty_orbits: int
    orbits: List[OrbitSlot]           # sorted by (star_designation, orbit_au)
    mainworld_orbit: Optional[OrbitSlot]
    star_mao: Dict[str, float]        # MAO per star designation
    star_hzco: Dict[str, float]       # HZCO per star designation
    star_hz_inner: Dict[str, float]   # HZCO - 1.0, clamped to MAO
    star_hz_outer: Dict[str, float]   # HZCO + 1.0, clamped to max_o
```

**HZ deviation sign convention:** Negative deviation means the orbit is *closer* to the star than the HZCO (warmer). Positive deviation means *further* from the star (cooler). This matches the WBH Habitable Zones Regions table where negative deviation → higher raw roll → hotter temperature.

**Orbit# vs AU:** Orbit# is the WBH's logarithmic orbital scale. The relationship to AU is non-linear — see `_orbit_to_au()` in `traveller_stellar_gen.py` for the lookup table. When drawing maps or computing habitable zone boundaries for display, always convert Orbit# to AU first and build the radius scale from AU values, not Orbit# values. Using Orbit# values directly as if they were AU will produce incorrect habitable zone placement on any log-radial map.

**Mainworld selection scoring:** The best candidate is the world with the lowest score on `(type_penalty + hz_penalty + temperature_penalty + star_penalty, abs(hz_deviation))`. Terrestrial worlds score better than gas giants; habitable zone worlds score better than non-HZ; temperate > cold/hot > frozen > boiling; primary star worlds score better than secondary star worlds.

---

### 4.3 `traveller_system_gen.py`

The integration layer. Imports from all three other generation modules.

**Key public API:**

```python
system: TravellerSystem = generate_full_system(name: str = "Unknown", seed: int = None)

system: TravellerSystem = generate_system_from_world(world: World, seed: int = None)
# Generates fresh stellar data and orbits around an existing World object.
# Preserves UWP and PBG; recalculates temperature from the assigned orbital position.
# Stamps canonical_profile on the mainworld orbit slot (same as TravellerMap path).
```

**Key dataclass:**

```python
@dataclass
class TravellerSystem:
    stellar_system: StarSystem
    system_orbits: SystemOrbits
    mainworld: Optional[World]
    mainworld_orbit: Optional[OrbitSlot]
    # methods: .to_dict(), .to_json(), .summary(), .to_html(detail_attached)
```

**Gas giant mainworld (WBH p.57):** When the selected mainworld orbit is a gas giant, `generate_mainworld_at_orbit()` generates the mainworld as a satellite of that giant rather than the giant itself. The helper `_gg_diameter(gg_sah: str) -> int` decodes the eHex diameter digit from the gas giant's `gg_sah` string (e.g. `"GM9"` → 9 Terran diameters). The satellite's size is clamped to `min(max(generate_size(), 1), gg_diameter - 1)`. A note recording the host giant's SAH and orbital position is appended to `world.notes`. The `gg_sah` value used here was rolled at orbit-gen time and stored in `OrbitSlot.gg_sah`, so there is no second SAH roll.

**Temperature integration (WBH p.46–47):** This module implements the critical link between orbital position and world temperature. Rather than rolling temperature randomly as in the standalone CRB procedure, `generate_temperature_from_orbit()` converts an orbit's HZ deviation to the raw 2D roll that the CRB temperature table expects, then applies atmosphere DMs. The mapping:

| Raw 2D roll | HZ deviation     | Zone      |
|-------------|------------------|-----------|
| 2–          | +1.1 or more     | Frozen    |
| 3           | +1.00            | Cold      |
| 4           | +0.50            | Cold      |
| 5           | +0.20 to +0.49   | Temperate |
| 6–9         | −0.20 to +0.19   | Temperate |
| 10          | −0.50 to −0.21   | Hot       |
| 11          | −1.00            | Hot       |
| 12+         | −1.1 or less     | Boiling   |

`hz_deviation_to_raw_roll(deviation)` performs this mapping. `generate_temperature_from_orbit(atmosphere, hz_deviation, hzco, orbit)` then applies the atmosphere DM from the CRB temperature table and returns the final temperature category string.

This same function is used for all secondary worlds and moons — their temperature is always derived from their parent orbit's HZ deviation, never rolled independently.

---

### 4.4 `traveller_world_gen.py`

Implements CRB pp. 248–261. The mainworld generator. Can also run standalone.

**Key public API:**

```python
world: World = generate_world(name: str = "Unknown")
```

Individual step functions are also public and used by `traveller_system_gen.py`:

```python
size: int       = generate_size()
atm: int        = generate_atmosphere(size)
temp: str       = generate_temperature(atmosphere)      # standalone (random roll)
hydro: int      = generate_hydrographics(size, atm, temp)
pop: int        = generate_population()
gov: int        = generate_government(population)
law: int        = generate_law_level(government)
port: str       = generate_starport(population)
tl: int         = generate_tech_level(starport, size, atm, hydro, pop, gov)
bases: List[str]= generate_bases(starport, tl, pop, law)
codes: List[str]= assign_trade_codes(size, atm, hydro, pop, gov, law, tl)
zone: str       = assign_travel_zone(atm, gov, law)
```

When called from `generate_mainworld_at_orbit()` in `traveller_system_gen.py`, `generate_temperature` is bypassed and the orbit-derived temperature is injected instead.

**World dataclass fields:**

```python
@dataclass
class World:
    name: str; size: int; atmosphere: int; temperature: str
    hydrographics: int; population: int; government: int
    law_level: int; starport: str; tech_level: int
    has_gas_giant: bool; gas_giant_count: int; belt_count: int
    population_multiplier: int  # WBH "P" digit (1–9); 0 if uninhabited
    bases: List[str]            # e.g. ["N","S","H"]
    trade_codes: List[str]      # e.g. ["Ag","Ni","Ri"]
    travel_zone: str            # "Green" | "Amber" | "Red"
    notes: List[str]
    # methods: .uwp(), .summary(), .to_dict(), .to_json(), .to_html()
```

**`World.from_dict(d)`** reconstructs a `World` from the dict produced by `to_dict()`. It handles both the nested form (`starport: {code: "A", ...}`) and flat forms where the value is the code directly. Missing fields receive safe defaults. Used by `generate_system_from_world()` and the `/api/system/from-world` endpoint.

**eHex encoding:** Traveller uses a base-17 encoding for UWP digits above 9: 10=A, 11=B … 16=G. The `to_hex(value)` helper handles this throughout. Size S (sub-size-1) moons use the string `"S"` in code but this does not appear in standard UWP strings.

**JSON Schema:** `traveller_world_schema.json` validates the output of `World.to_dict()`. It uses `"additionalProperties": false` throughout and validates UWP strings against `^[ABCDEX][0-9A-G]{6}-[0-9A-G]$`.

---

### 4.5 `traveller_world_detail.py`

Generates SAH (Size/Atmosphere/Hydrographics) profiles and full social data for every non-mainworld body in the system — orbital secondaries, belts, and significant moons.

**Key public API:**

```python
# Main entry points
attach_detail(system: TravellerSystem) -> None
    # Populates orbit.detail (WorldDetail) on every OrbitSlot,
    # and moon.detail (WorldDetail) on every Moon in orbit.detail.moons.

table: str = system_body_table(system: TravellerSystem) -> str
    # Returns a formatted text table of all orbits and their moon sub-rows.

# Lower-level (used internally and testable)
detail_map: dict = generate_system_detail(system: TravellerSystem)
    # Returns {"{desig}-{slot_index}": WorldDetail} without attaching to slots.
```

**WorldDetail class:**

`WorldDetail` is not a dataclass; it uses `__slots__` for memory efficiency.

```python
class WorldDetail:
    sah: str            # 3-char physical profile; "000" for belts, "S00" for size S moons
    population: int     # 0 = uninhabited
    government: int
    law_level: int
    tech_level: int
    spaceport: str      # Y/H/G/F for secondaries; "-" default
    moons: list         # List[Moon], populated by attach_detail()
    trade_codes: list   # List[str]; empty for gas giants and rings

    # computed properties:
    .inhabited -> bool
    .is_gas_giant -> bool   # True if sah starts with GS/GM/GL
    .profile -> str         # display string (see section 9)
```

**Population cap:** A system-wide secondary population cap is rolled once per system as `mainworld.population - 1D`. If the result is ≤ 0, no secondaries or moons are inhabited. This cap is shared across all secondary worlds and moons in the same system.

**Tech Level viability:** After any population roll, the minimal sustainable TL for that atmosphere code is checked against the mainworld TL. If `minimal_tl(atm) > mainworld_tl`, the world is set uninhabited regardless of the population roll. This enforces the WBH rule that colonists cannot survive without adequate technology:

| Atmosphere | Minimal TL | Rationale |
|------------|-----------|-----------|
| 0, 1       | 8         | Vacc suits required |
| 2, 3       | 5         | Filter mask + cold gear |
| 4, 5       | 3         | Filter mask |
| 6–9        | 0         | No special equipment |
| A+         | 8         | Hostile environment suit |

**Gas giants** are never directly inhabited. Their moons can be. The gas giant's SAH is read from `orbit.gg_sah` when available (set at orbit-gen time by `_gg_sah_roll()`), so the diameter seen in the detail table is consistent with the satellite size constraint applied when the mainworld was generated. If `orbit.gg_sah` is empty (legacy data), a fresh SAH is rolled as a fallback.

**Belts** use atmosphere 0 for the TL viability check, so they are only inhabited when the mainworld TL ≥ 8.

---

### 4.6 `traveller_moon_gen.py`

Implements WBH pp. 55–57.

**Key public API:**

```python
moons: List[Moon] = generate_moons(
    size_code: int | str,   # planet size (int 1–15, or "S")
    orbit_number: float,    # orbital Orbit# for DM check
    is_gas_giant: bool = False,
    gg_category: str = "M", # "S", "M", or "L"
    gg_diameter: int = 8,   # Terran diameters, for moon size capping
) -> List[Moon]

display: str = moons_str(moons: List[Moon]) -> str
    # Returns compact string e.g. "R01, S, S, 3, 5"
```

**Moon dataclass:**

```python
@dataclass
class Moon:
    size_code: int | str    # int 0–F, or "S"; 0 means ring when is_ring=True
    is_ring: bool = False
    is_gas_giant_moon: bool = False  # moon is itself a small gas giant
    detail: Optional[WorldDetail] = None  # populated by attach_detail()
    _ring_count: int    # field(default=1, init=False) — set by _consolidate()

    # properties: .size_str, __repr__
```

**Quantity DM:** The only DM currently applied is `DM-1 per dice` when `orbit_number < 1.0`. Other adjacency conditions (companion-induced MAO, Close/Near star exclusion zone proximity) require eccentricity data that is not yet generated, so they are omitted.

**Ring consolidation:** Multiple rings rolled for a single planet are merged into one `Moon(is_ring=True)` with `_ring_count` set to the total. The display string for two rings is `R02`. `_ring_count` is declared as `field(default=1, init=False)` in the dataclass so it is a known field for type checkers, even though it is not accepted by `__init__`.

**Moon detail generation** (`_moon_detail()` in `traveller_world_detail.py`): Uses the **parent planet's HZ deviation**, not the moon's own position, because moons share their parent's orbital distance from the star. Size S and size 0–1 moons automatically receive atmosphere 0 and hydrographics 0 (too small to retain atmosphere). Size 2+ moons go through the full `generate_atmosphere` / `generate_hydrographics` pipeline.

---

### 4.7 `function_app.py` and `shared/helpers.py`

The Azure Functions REST API layer. Not required for local use of the generation modules.

**Endpoints:**

| Method | Route | Description |
|--------|-------|-------------|
| GET/POST | `/api/world` | Generate one mainworld |
| GET | `/api/world/{name}` | Generate one mainworld, name from URL |
| GET | `/api/world/{name}/card` | Standalone HTML mainworld card |
| POST | `/api/worlds` | Batch mainworlds (up to 20) |
| GET/POST | `/api/system` | Full star system (optional `detail`) |
| GET | `/api/system/{name}` | Full star system, name from URL (optional `detail`) |
| GET | `/api/system/{name}/card` | Standalone HTML system card (optional `detail`) |
| GET/POST | `/api/system/full` | Complete system — all secondary worlds and moons always attached; selectable `format` |
| GET/POST | `/api/map/system` | TravellerMap world — canonical UWP; procedural orbits |
| GET | `/api/map/system/{name}` | Same; name from URL |
| POST | `/api/system/from-world` | Full system around an existing mainworld JSON; UWP/PBG preserved |

Mainworld JSON responses conform to `traveller_world_schema.json`. The `/card` endpoints return `text/html; charset=utf-8`. `/api/system/full`, `/api/map/system`, and `/api/system/from-world` with `format=text` return `text/plain; charset=utf-8`.

**`parse_format(req)` helper** (`shared/helpers.py`): Extracts the `format` parameter from query string or JSON body. Returns one of `"json"` (default), `"html"`, or `"text"`. Used by `/api/system/full`, the map endpoints, and `/api/system/from-world`.

**`parse_hex_pos(req, body=None)` helper** (`shared/helpers.py`): Extracts and validates the optional `hex` query/body parameter. Accepts a 4-digit hex position matching `[0-9A-Fa-f]{4}` (e.g. `"1910"`). Returns `(hex_str, None)` if valid or absent; returns `(None, error_response)` with error code `INVALID_HEX` if the value is present but wrongly formatted. Used by both map/system endpoints.

**`parse_world_json(req)` helper** (`shared/helpers.py`): Extracts and validates a mainworld JSON object from the request body. The body must be a dict containing at minimum `uwp` or the characteristic sub-fields (`size`, `atmosphere`, `hydrographics`, `population`). Returns `(dict, None)` if valid; `(None, error_response)` with code `INVALID_BODY` if the body is absent, not JSON, or missing required fields. Used exclusively by `/api/system/from-world`.

**`max_batch_size()` helper** (`shared/helpers.py`): Reads `TRAVELLER_MAX_BATCH_SIZE` from the environment and returns it as an integer, falling back to `DEFAULT_MAX_BATCH = 20` on parse failure. The returned value is bounds-checked to `1–1000`; values outside that range are silently replaced with the default.

**`/api/system/full` behaviour:** Calls `generate_full_system()` then unconditionally calls `attach_detail()`. No `detail` parameter is accepted or needed. The `format` parameter then controls serialisation: `to_dict()` for JSON, `to_html(detail_attached=True)` for HTML, `summary()` for text.

**`/api/map/system` behaviour:** Delegates to `generate_system_from_map()` in `traveller_map_fetch.py`. Catches `LookupError` (→ 404 `NOT_FOUND`), `urllib.error.URLError` (→ 502 `UPSTREAM_ERROR`), and general `Exception` (→ 500 `INTERNAL_ERROR`). The `URLError` handler logs the upstream detail server-side but returns only a generic message to the caller. Supports `detail` and `format` identically to the system endpoints.

**`/api/system/from-world` behaviour:** Calls `parse_world_json()` to validate the body, reconstructs a `World` via `World.from_dict()`, then calls `generate_system_from_world()`. PBG counts from the world are reconciled into the generated `SystemOrbits`. The mainworld orbit slot receives `canonical_profile = world.uwp()`. Temperature is recalculated from orbital HZ deviation — the temperature in the input JSON is discarded. Supports `detail` and `format` identically to the system endpoints. Returns `400 INVALID_BODY` if the body is missing or malformed.

---

### 4.8 `traveller_map_fetch.py`

Fetches canonical world data from the public TravellerMap REST API and uses it
to seed a full system generation. Uses only Python stdlib (`urllib.request`) —
no new dependencies.

**Key public API:**

```python
system: TravellerSystem = generate_system_from_map(
    name: Optional[str] = None,
    sector: Optional[str] = None,
    hex_pos: Optional[str] = None,
    seed: Optional[int] = None,
    attach: bool = False,
) -> TravellerSystem
```

Raises `LookupError` if the world is not found on TravellerMap.
Raises `AmbiguousWorldError` if a name search matches more than one world in the same sector.
Raises `urllib.error.URLError` if the API is unreachable.

**Key dataclasses and functions:**

```python
class AmbiguousWorldError(Exception):
    # Raised when a name search matches more than one world in the same sector.
    # Attributes:
    name: str
    sector: str
    candidates: list  # list of (world_name: str, hex_pos: str) tuples

@dataclass
class MapWorldData:
    name: str
    sector: str
    hex_pos: str
    uwp: str          # canonical, e.g. "A867A69-F"
    bases: str
    remarks: str
    zone: str
    pbg: str
    stars_str: str    # canonical stellar string, e.g. "G2 V M7 V"

def fetch_world_data(name, sector, hex_pos) -> MapWorldData
def parse_uwp(uwp_str) -> dict           # maps to size/atm/hydro/etc. ints
def parse_stellar_string(stars_str)      # -> List[Tuple[spectral, subtype, lum_class]]
def reconstruct_star_system(stars_str)   # -> StarSystem (canonical types, random orbits)
def reconstruct_world(map_data)          # -> World (canonical UWP, placeholder temperature)
```

**TravellerMap API access:**

World data is fetched in two steps:

1. If `name` is given: `GET /api/search?q={name}` — searches by name, returns minimal data
   including `HexX`/`HexY` coordinates. Filtered to the requested sector. Raises
   `LookupError` if the name is not found.
2. `GET /data/{sector}/{hex}` — fetches the full world record (`UWP`, `PBG`, `Bases`,
   `Remarks`, `Zone`, `Stellar`). This is the authoritative source of all canonical data.

If `hex_pos` is provided directly (bypassing name search), step 1 is skipped.
`sector` is always required for both steps.

**Duplicate world names within a sector:** The Spinward Marches alone has seven pairs of worlds sharing a name (e.g. Aramis at 2540 and 3110). `_name_to_hex()` raises `AmbiguousWorldError` (carrying a `candidates` list of `(name, hex)` tuples) when a name search returns more than one exact match. Callers that supply `hex_pos` directly bypass this entirely. The gen-ui shows a modal disambiguation dialog and re-calls with the selected hex position.

**Pipeline inside `generate_system_from_map()`:**

1. `fetch_world_data()` — two-step HTTP fetch (search → `/data/{sector}/{hex}`), returns `MapWorldData`
2. `random.seed(seed)` if provided
3. `reconstruct_star_system(stars_str)` — primary star at orbit 0; secondary orbits assigned heuristically (close→near→far) with random orbit numbers
4. `generate_orbits(stellar)` — full WBH procedural orbital layout
5. `reconstruct_world(map_data)` — canonical UWP digits extracted via eHex decoding; no dice rolled; gas/belt counts from PBG override the procedural counts in `SystemOrbits`
6. Stamp the best mainworld orbit slot: `mw_orbit.canonical_profile = world.uwp()` and correct `mw_orbit.world_type` to `"terrestrial"` or `"belt"` based on the canonical size digit
7. `generate_temperature_from_orbit()` — canonical temperature derived from orbital position (temperature is not in the UWP)
8. Assemble `TravellerSystem`
9. `attach_detail()` if `attach=True`

**Uninhabited mainworlds:** Worlds with population = 0 (social string `000`) are handled
correctly. `reconstruct_world()` sets `population = 0` from the UWP. The canonical UWP
is preserved in all output paths — `canonical_profile` takes display priority over
`WorldDetail.profile`, which would incorrectly render an uninhabited mainworld as
`Y{sah}000-0` rather than the true UWP.

**Stellar string parsing:** Handles `G2 V`, `D`, `BD`, multi-star strings separated by spaces, and all WBH luminosity classes (`Ia Ib II III IV V VI`). Brown dwarfs (`BD`) and white dwarfs (`D`) get `subtype=None`.

**CLI:**

`--sector` is always required.

```bash
# By name + sector
python traveller_map_fetch.py --name Regina --sector "Spinward Marches"

# By hex position (bypasses name search)
python traveller_map_fetch.py --sector "Spinward Marches" --hex 1910

# With seed and all secondary world detail
python traveller_map_fetch.py --name Mora --sector "Spinward Marches" --seed 42 --detail

# Output formats
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --html > regina.html
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --format json
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --format text

# Uninhabited worlds are handled correctly
python traveller_map_fetch.py --name Tavonni --sector "Spinward Marches" --detail
```

---

### 4.9 `system_map.py`

Generates an SVG diagram of a complete star system. The canvas has two zones stacked vertically:

- **Arc zones** — one per star that has orbit slots. Each zone uses its own log-AU radial scale so the star's orbits fill the available width. Arcs are right-facing semicircles; the sweep angle per orbit is set so every arc reaches the same top and bottom y-coordinate within its zone. Companion-star dashed arcs are rendered inside the primary zone for context.
- **Table zone** — one column per star, listing orbit slots in orbit-number order. Column count grows with the stellar system; use `--width` to avoid cramping on multi-star systems.

**Key public API:**

```python
svg_str, canvas_height = build_svg(
    system: TravellerSystem,
    canvas_w: int = 1600,
    palette: ColourPalette = PALETTE_DARK,
) -> tuple[str, int]

save_output(svg_str: str, path: str) -> None
```

`build_svg()` calls `attach_detail()` internally (it needs world types and SAH codes to colour-code the arcs). The returned SVG string is self-contained and can be written to a file or embedded in HTML.

**Colour palettes:**

```python
@dataclass(frozen=True)
class ColourPalette:
    bg, gg, inh, uninh, belt, star_pri, star_sec,
    mainworld, text, dim, axis, leader: str

PALETTE_DARK   # dark background (default)
PALETTE_LIGHT  # white background (--white-bg flag)
```

**CLI:**

```bash
# Random system, dark background, written to /tmp/traveller_system_map.svg
python system_map.py

# Named system with seed, white background, custom output path
python system_map.py --name Ardenne --seed 1000 --white-bg --out ardenne.svg

# Wider canvas for multi-star systems
python system_map.py --seed 42 --width 2400

# Open in default viewer after writing (macOS/Linux)
python system_map.py --name Mora --seed 7
```

---

## 5. Key design decisions

**Orbital temperature over random temperature.** All worlds — mainworld, secondary worlds, and moons — derive their temperature from orbital HZ deviation rather than an independent dice roll. This ensures physical consistency: a world's temperature matches where it actually sits relative to its star. The `generate_temperature_from_orbit()` function in `traveller_system_gen.py` is the single source of truth for this conversion.

**Single RNG stream.** Python's `random` module state is global. All generation code shares one stream. This keeps the seeding model simple but means any change to the number of dice rolls in any module will shift all subsequent rolls for every affected seed. When adding new generation steps, place them at the end of the pipeline to minimise seed disruption.

**`attach_detail()` is a separate step.** Secondary world and moon generation is expensive — O(total moons) additional RNG calls. `generate_full_system()` does not call it automatically. Code that only needs the mainworld UWP should not call `attach_detail()`.

**Orbit# scale is not linear with AU.** The WBH Orbit# table maps orbital positions to a scale that is approximately logarithmic in AU. Orbit# 1.0 ≈ 0.400 AU; Orbit# 2.0 ≈ 0.700 AU; Orbit# 3.0 ≈ 1.000 AU. When computing habitable zone boundaries for display, always convert Orbit# values to AU using `_orbit_to_au()`, then build radius scales from AU. Do not use Orbit# values directly as radial distances.

**Secondary world government defaults to dependent (Case 1).** The WBH provides two government procedures for secondary worlds: dependent (roll 1D on the Secondary World Government table) and independent (roll 2D-7 + Population). The current implementation uses the dependent (Case 1) table for all secondary worlds. This is the most common case and keeps the social generation self-contained without requiring Referee input about political independence.

**Gas giant SAH is rolled at orbit-gen time.** `_gg_sah_roll()` in `traveller_orbit_gen.py` rolls and stores the gas giant SAH (GS/GM/GL + diameter digit) in `OrbitSlot.gg_sah` during `generate_orbits()`. This solves two problems: (1) `generate_mainworld_at_orbit()` needs the gas giant diameter to constrain satellite size, but importing `traveller_world_detail` would create a circular import; (2) the SAH value must be the same whether it is accessed for satellite sizing (in system_gen) or for the detail table (in world_detail), so it must be rolled once and shared. Inlining the roll in orbit_gen avoids the circular import and ensures consistency. The RNG sequence shifts for any system that contains a gas giant — an unavoidable consequence of inserting new dice rolls earlier in the pipeline.

---

## 6. Compliance audit history

The bugs below were found during development and testing and corrected. Each entry notes the severity, root cause, and post-fix verification.

**Step 3b — cold system baseline formula (high severity).** The original code computed `baseline_orbit = anchor + abs(baseline_num) + total_slots * 0.1 + var`. The WBH formula is `HZCO − baseline_number + Total Worlds + (2D−7)/10`, which adds Total Worlds as whole Orbit# units. Multiplying by 0.1 compressed an 8-world system's outward shift from 8.0 Orbit# down to 0.8 Orbit#. Post-fix: 97.8% → 0% genuine violations. Fixed in `generate_orbits()`, Step 3b branch.

**Step 5 — maximum spread denominator (low severity).** The original code used `max_spread = avail / max(total_slots + 1, 1)`. The WBH formula divides by `(Primary's Allocated Orbits + Total Stars)`. The constant `+1` was a stand-in for the star count. Fixed to use `n_worlds + n_total_stars`.

**Step 6 — outermost orbit exceeds max_o (low severity).** The clamp `current = min(current, max_o)` was applied at the start of each loop iteration, but after the spacing-fallback branch could push `current` above `max_o`. Fixed by clamping before appending and also clamping the fallback path. Post-fix: 0 violations in 10,000 systems.

**Non-primary star mass ordering (separate fix).** Early versions compared non-primary star types using only the spectral letter (e.g., both M0 V and M7 V are "M"), but mass varies significantly within a spectral type. Fixed to compare `candidate.mass > parent.mass` directly.

**Orbit spread range — inner-system clustering (medium severity).** Two interacting bugs caused all worlds to cluster near the inner system regardless of the star type or system size.

*Bug 1 — missing minimum spread:* When `baseline_num` is close to `total_slots` (as in the normal Step 3a path), the formula `spread = (baseline_orbit - mao) / baseline_num` collapses to approximately `HZCO / total_slots`. For a G-type star with 8 worlds this gives spread ≈ 0.4, placing every world within Orbit# 3.5 (≈ 1.5 AU) regardless of the available range.

*Bug 2 — multiplicative gap check:* The slot-spacing fallback `if current <= slots[-1] * 1.1` triggered continuously for any orbit number above `spread / 0.1` (e.g., beyond Orbit# 4 with spread 0.4), halving the effective spacing on every outer step.

Fixed by adding `min_spread = avail / max(total_slots * 2, 1)` as a floor so that worlds always span at least half the available range, and by changing the gap check to additive: `if current - slots[-1] < spread * 0.4`. Post-fix: single-star systems routinely place worlds from ≈ 0.5 AU to 20+ AU; binary systems are correctly limited by their companion orbit geometry.

**Sub-Orbit#1 deviation scaling amplifies temperature errors for dim stars (high severity).** `hz_deviation_to_raw_roll()` in `traveller_system_gen.py` and `_temp_zone()` in `traveller_orbit_gen.py` both applied a scaling formula `eff_dev = hz_deviation / min(hzco, orbit)` for positions below Orbit#1. This was intended to scale deviations that occur on a compressed sub-AU orbit scale. However, `is_habitable_zone` used the unscaled deviation (`|dev| <= 1.0`), so worlds were classified as being in the HZ based on unscaled deviation, yet had their temperature computed from an inflated deviation. For dim M-type stars where HZCO rounds to approximately 0.000, the denominator collapsed to 0.01, amplifying deviations by up to 50×. Statistical test over 2,000 systems confirmed 22% of HZ mainworlds were assigned Frozen temperatures — 0% is the correct result for worlds at exactly the HZCO. Fix: the scaling was removed from both functions. The WBH HZ Regions table (p.46) is defined in terms of orbit# deviation directly, with no secondary scaling. Post-fix: 0% frozen-in-HZ from orbital position; HZ mainworld distribution is approximately 50% Temperate, 30% Cold, 20% Hot after atmosphere DMs.

**Gas giant mainworld generates terrestrial UWP instead of satellite UWP (medium severity).** `generate_mainworld_at_orbit()` had a `"belt"` branch but no `"gas_giant"` branch. When the selected mainworld orbit was a gas giant, generation fell through to the terrestrial path, rolling size 0–10 freely — including sizes 8–10 that are impossible for any moon, and with no relation to the host giant's size. Statistical analysis over 1,000 systems confirmed 13.8% were affected. Fix: `_gg_sah_roll()` was inlined in `traveller_orbit_gen.py` to roll and store the gas giant SAH in `OrbitSlot.gg_sah` during `generate_orbits()`. A new gas giant branch in `generate_mainworld_at_orbit()` treats the mainworld as a satellite: size is clamped to `[1, gg_diameter − 1]` (WBH p.57), with normal atmosphere/temperature/hydrographics generation and a satellite note appended to the world. `traveller_world_detail.py` reuses `orbit.gg_sah` rather than re-rolling. The RNG sequence shifts for all systems containing a gas giant (unavoidable new dice at orbit-gen time).

**Ag trade code applied to unpopulated worlds (medium severity).** `assign_trade_codes()` in `traveller_world_gen.py` checked `4 <= size <= 9` (a spurious size criterion not present in CRB p.260), `4 <= atmosphere <= 8` (upper bound off by one), and `5 <= hydrographics <= 7` (range shifted vs. CRB). The population criterion `5 <= population <= 7` was missing entirely, allowing uninhabited worlds (population 0) and underpopulated or overpopulated worlds to receive the Ag code. Fix (Session 15): replaced the check with the correct CRB p.260 criteria — `4 <= atmosphere <= 9`, `4 <= hydrographics <= 8`, `5 <= population <= 7`. Six boundary tests added. No RNG sequence change — `assign_trade_codes()` is deterministic given its arguments and calls no dice rolls.

---

## 7. Deferred and out-of-scope features

The following WBH features are explicitly noted as not yet implemented. Page references are to the WBH Sept 2023 edition.

**Anomalous orbits (Step 7, WBH p.49–50).** Random, eccentric, inclined, retrograde, and trojan orbits. These add terrestrial planet count to the system after normal orbit placement. Not implemented in `traveller_orbit_gen.py`.

**Eccentricity (Step 9, WBH p.51).** Orbital eccentricity for planets. This would affect the moon quantity DM for planets near exclusion zones (currently only the `orbit_number < 1.0` DM is applied), and would affect Hill sphere calculations for moons. Not implemented.

**Orbital periods.** `P = √(AU³ / M)` for single-star systems. Not computed or stored.

**Moon orbit adjacency DMs.** Three of the four DM conditions for moon quantity (WBH p.56) require knowledge of whether an orbit slot is adjacent to a companion-induced MAO, a Close/Near star unavailability zone, or the outermost slot of a Far star. These require eccentricity data and spread values that are not currently passed through to `traveller_moon_gen.py`. Only the `orbit_number < 1.0` condition is implemented.

**Post-stellar special circumstances (WBH p.219+).** White dwarfs, neutron stars, black holes, and pulsars are detected and labelled during stellar generation but not physically characterised (no mass, radius, or magnetic field generation).

**Secondary world independent government (Case 2).** Secondary worlds with `Government != 6` can be independent, with government rolled as `2D-7 + Population`. Currently all secondary worlds use the dependent (Case 1) table.

**Secondary world classifications** (WBH p.163). Colony, Farming, Freeport, Military Base, Mining Facility, Penal Colony, Research Base — trade codes for secondary worlds based on their characteristics and relationship to the mainworld. Not implemented.

**World physical detail beyond SAH** (WBH pp. 74–130). Precise diameter, density, gravity, mass, escape velocity, axial tilt, day length, seismic stress, tidal heating, atmospheric composition, hydrographic composition, native life ratings. The codebase stops at the SAH level.

**Moon orbit placement** (WBH pp. 74–77). Hill sphere calculation, Roche limit, Moon Orbit Range, and orbital distances in planetary diameters. Moons are sized and detailed but not given orbital positions within their parent's system.

**Belt physical detail** (WBH pp. 131–133). Belt span, composition percentages, bulk, resource rating, and significant belt bodies (Size 1 and S). Belts currently have a fixed SAH of `000`.

---

## 8. Reproducibility and seeding

All generation is reproducible if the same seed is provided to `generate_full_system()`.

```python
from traveller_system_gen import generate_full_system

system = generate_full_system(name="Ardenne", seed=1000)
# Calling with seed=1000 again always produces the same result.
```

Seed is set with `random.seed(seed)` at the top of `generate_full_system()`. All subsequent calls to `random.randint()` or `random.randrange()` across all modules draw from that same sequence.

If calling generation modules individually (e.g., `generate_stellar_data()` directly), set the seed yourself with `random.seed(seed)` before the call.

Adding any dice roll anywhere in the pipeline will shift all results for seeds that pass through the modified code path. This is unavoidable given the shared global RNG. If seed stability across releases is important, the safest strategy is to add new rolls at the very end of the pipeline (e.g., in `attach_detail()` after all existing rolls), so that the mainworld UWP is unaffected.

---

## 9. Profile string formats

Different world types use different profile formats. The format is stored in `WorldDetail.profile` and displayed by `system_body_table()`.

| Body type | Format | Example | Notes |
|-----------|--------|---------|-------|
| Mainworld | `{port}{SAH}{PGL}-{TL}` | `C473574-8` | Standard CRB UWP |
| Inhabited terrestrial | `{port}{SAH}{PGL}-{TL}` | `F473510-7` | No dash between SAH and PGL |
| Uninhabited terrestrial | `Y{SAH}000-0` | `Y473000-0` | Y = no spaceport; 000 = social codes |
| Inhabited belt | `{port}000{PGL}-{TL}` | `G000121-8` | SAH always 000 |
| Uninhabited belt | `Y000000-0` | `Y000000-0` | |
| Gas giant | `{SAH}` only | `GM9` `GS4` `GLB` | No port or social codes |
| Inhabited moon (size 2+) | `{port}{SAH}{PGL}-{TL}` | `F532320-6` | Same as terrestrial |
| Uninhabited moon (size 2+) | `Y{SAH}000-0` | `Y473000-0` | |
| Size S moon | `YS00000-0` | `YS00000-0` | Auto vacuum |
| Size 0–1 moon | `Y{size}00000-0` | `Y100000-0` | Auto vacuum |
| Ring | `R0{count}` | `R01` `R03` | No physical profile |
| Empty orbital slot | `---` | `---` | |

**Port codes for secondaries** use the spaceport scale (Y/H/G/F), not the standard starport scale (A–X):

| Code | Equivalent starport | Facilities |
|------|---------------------|-----------|
| Y | X | No spaceport |
| H | E | Primitive installation |
| G | D | Basic facility, unrefined fuel |
| F | C | Good facility, unrefined fuel, minor repair |

**Gas giant SAH:** `G{category}{diameter}` where category is S/M/L and diameter is eHex-encoded Terran diameters (2–18). Example: `GL9` = Large gas giant, 9× Terra's diameter.

---

## 10. Running and testing

### Generating systems locally

```bash
# Full system (stellar + orbits + mainworld) — text summary
python traveller_system_gen.py --name Ardenne --seed 1000

# With all secondary world and satellite profiles
python traveller_system_gen.py --name Ardenne --seed 1000 --detail

# JSON output with all profiles
python traveller_system_gen.py --name Ardenne --seed 1000 --detail --json

# Self-contained HTML card (implies --detail)
python traveller_system_gen.py --name Ardenne --seed 1000 --html > ardenne.html

# Explicit format flag
python traveller_system_gen.py --name Ardenne --seed 1000 --format html > ardenne.html
python traveller_system_gen.py --name Ardenne --seed 1000 --format json

# Mainworld only
python traveller_world_gen.py --name Cogri --seed 42 --json

# Moon generation detail (legacy entry point)
python traveller_world_detail.py --name Varanthos --seed 6056

# SVG star system map (dark background by default)
python system_map.py --name Ardenne --seed 1000 --out ardenne.svg

# White background (for printing / light-theme display)
python system_map.py --name Ardenne --seed 1000 --white-bg --out ardenne-light.svg

# Wider canvas for multi-star systems
python system_map.py --seed 42 --width 2400 --out multi-star.svg
```

### Running the tests

```bash
pip install pytest jsonschema

# All tests
pytest tests/ -v

# Mainworld generation only
pytest tests/test_traveller_world_gen.py -v

# API layer only
pytest tests/test_function_app.py -v
```

The Azure Functions SDK is stubbed automatically by `conftest.py` if not installed. The test suite does not require a live Azure runtime.

### Local API server

```bash
pip install -r requirements.txt
func start   # requires Azure Functions Core Tools v4
```

### CI — dependency vulnerability scan

`.github/workflows/dependency-audit.yml` runs `pip-audit` on every branch push and on pull requests targeting `main`. It audits `requirements.txt` and `gen-ui/requirements.txt` separately (two named steps) and hard-fails the workflow if any vulnerability is found. A JSON report artifact is always uploaded (30-day retention) so findings are readable without re-running locally.

To make the audit a required check that blocks merges: Settings → Branches → branch protection rule for `main` → Require status checks → add `pip-audit`.

---

## 11. Licence and IP constraints

The software is released under the **MIT Licence**. See `LICENSE` for the full text.

The MIT Licence governs the *code*. Use of the code in connection with the Traveller IP is additionally governed by **Mongoose Publishing's Fair Use Policy**, which prohibits commercial use. The policy permits non-commercial fan tools, software, and GitHub repositories of this kind.

Key constraints:

- **No commercial use** with the Traveller IP without an appropriate licence from Mongoose Publishing.
- **No reproduction of rulebook text.** The code implements the rules algorithmically; it does not copy table text or descriptions from the source books.
- The Traveller game in all forms is owned by Mongoose Publishing. Copyright 1977–2025 Mongoose Publishing. All rights reserved.
- This is an unofficial fan work and is not affiliated with or endorsed by Mongoose Publishing.

The Mongoose licensing page is at `https://www.mongoosepublishing.com/pages/traveller-licensing`.

Every Python source file includes a standardised licence block in its module docstring:

```
Licence
-------
MIT Licence — see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.
```
