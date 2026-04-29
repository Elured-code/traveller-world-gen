# Traveller World Generator

A Python implementation of the star system and mainworld generation rules
from the **Traveller 2022 Core Rulebook** and **World Builder's Handbook**
(Mongoose Publishing), with a REST API built on Azure Functions.

All 13 mainworld generation steps are implemented in rulebook order, each
feeding into the next exactly as the rules describe. The stellar and orbit
generation modules implement the full WBH expanded procedure. Output is
available as a plain-text summary, structured JSON, or a self-contained
HTML display card.

> **Note:** This project requires the Traveller 2022 Core Rulebook and
> World Builder's Handbook (Sept 2023).
> The Traveller game in all forms is owned by Mongoose Publishing.
> Copyright 1977–2025 Mongoose Publishing. All rights reserved.
> This project is an unofficial fan work created under the Mongoose
> Publishing Fair Use Policy. It is not affiliated with or endorsed by
> Mongoose Publishing. No commercial use is intended or permitted.

---

## Features

- **Stellar generation** (WBH pp.14–29): primary star type, subtype, mass,
  temperature, diameter, luminosity, system age, multiple stars (Close/Near/Far/
  Companion), and non-primary star typing (Random/Lesser/Sibling/Twin)
- **Orbit placement** (WBH pp.36–51): world counts, MAO, HZCO, habitable zone,
  baseline number and orbit, spread, and mainworld candidate selection
- **Mainworld generation** (CRB pp.248–261): all 13 steps with temperature
  derived from orbital position rather than a random roll
- Complete UWP output, all 18 trade codes, all Amber zone triggers
- Verified TL era labels (Primitive → High Stellar) against pp. 6–7
- Three output formats: text summary, JSON, standalone HTML card
- **SVG system maps** — visual orbit diagrams with arc zones per star, log-scale AU radii, and orbit data tables
- REST API via Azure Functions (13 endpoints: 5 mainworld + 6 system + 2 TravellerMap, JSON + HTML + plain-text responses)
- TravellerMap integration — fetch canonical UWP + stellar data from travellermap.com and generate a full procedural system
- `World.from_dict()` deserialiser — reconstruct a World from a previous JSON response and feed it into a new system generation
- JSON Schema for the world output format (`traveller_world_schema.json`)
- GTK4 desktop UI (`gen-ui/app.py`) — full native desktop application: procedural mainworld and full system generation, TravellerMap lookup with disambiguation, in-app world card and stellar/orbit tables, attach detail (secondary world SAH + moon sub-rows), save to JSON/HTML/text, open in browser

---

## Project structure

```
traveller-world-gen/
│
│  Generation modules
├── traveller_stellar_gen.py        # WBH stellar generation (pp.14-29)
├── traveller_orbit_gen.py          # WBH orbit placement (pp.36-51)
├── traveller_system_gen.py         # Integration: full system + mainworld
├── traveller_world_gen.py          # CRB mainworld generation (pp.248-261)
├── traveller_world_detail.py       # Secondary world SAH/social + satellite detail
├── traveller_moon_gen.py           # Significant moon sizing and profiles
├── traveller_map_fetch.py          # TravellerMap integration: fetch UWP + stellar, reconstruct system
│
│  Visualisation
├── system_map.py                   # SVG star system maps: arc zones, orbit tables, log-AU scale
│
│  Schema
├── traveller_world_schema.json     # JSON Schema (draft 2020-12) for World.to_dict()
│
│  Azure Functions API
├── function_app.py                 # All HTTP endpoints (13 routes, v2 model)
├── shared/
│   └── helpers.py                  # Request parsing & response helpers
├── host.json                       # Azure Functions host configuration
├── requirements.txt                # Python dependencies
├── local.settings.json.example     # Local development settings template
│                                   # (copy to local.settings.json — not committed)
│
│  GTK4 Desktop UI
├── gen-ui/
│   ├── app.py                      # GTK4 desktop UI — fully working
│   ├── README.md                   # Setup, usage, and keyboard shortcut reference
│   └── requirements.txt            # Dependency notes (Homebrew) and HTML rendering constraints
│
│  Tests
├── tests/
│   ├── test_traveller_world_gen.py # Unit tests — mainworld generation
│   └── test_function_app.py        # Unit tests — API endpoints
├── conftest.py                     # pytest path configuration
├── pytest.ini                      # pytest settings
│
│  Documentation
├── docs/
│   ├── AZURE_DEPLOYMENT.md         # Full REST API reference (all 13 endpoints)
│   ├── developer-guide.md          # Architecture, module reference, compliance notes
│   └── VSCODE.md                   # VS Code + Claude shared environment setup
│
│  Examples
├── examples/                       # Generated sample SVG system maps
│
├── LICENSE                         # MIT Licence + Traveller IP notice
└── README.md                       # This file
```

---

## Quick start

### Prerequisites

- Python 3.11+
- No third-party packages required for the core generation modules

```bash
git clone https://github.com/your-username/traveller-world-gen.git
cd traveller-world-gen
```

### Generate a system from TravellerMap canonical data

Sector is always required — many world names exist in multiple sectors.

```bash
# Fetch canonical UWP + stellar data from travellermap.com (sector always required)
python traveller_map_fetch.py --name Regina --sector "Spinward Marches"

# With seed and all secondary world detail
python traveller_map_fetch.py --name Mora --sector "Spinward Marches" --seed 42 --detail

# By hex position within a sector
python traveller_map_fetch.py --sector "Spinward Marches" --hex 1910 --seed 7

# Text summary (default)
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --format text

# JSON output
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --json
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --format json

# Self-contained HTML card
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --html > regina.html
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --format html > regina.html
```

### Generate a complete star system

```bash
# Full system — stellar data, orbits, and mainworld (random, text summary)
python traveller_system_gen.py

# Named system with a fixed seed
python traveller_system_gen.py --name Ardenne --seed 1000

# Include all secondary world and moon profiles
python traveller_system_gen.py --name Ardenne --seed 1000 --detail

# Generate multiple systems (defaults to text output, one block per system)
python traveller_system_gen.py --count 3 --seed 1000

# JSON output
python traveller_system_gen.py --name Ardenne --seed 1000 --json
python traveller_system_gen.py --name Ardenne --seed 1000 --format json

# Text output (explicit; same as default)
python traveller_system_gen.py --name Ardenne --seed 1000 --format text

# Self-contained HTML card
python traveller_system_gen.py --name Ardenne --seed 1000 --html > ardenne.html
python traveller_system_gen.py --name Ardenne --seed 1000 --format html > ardenne.html

# HTML card with all secondary world and moon profiles
python traveller_system_gen.py --name Ardenne --seed 1000 --detail --html > ardenne.html
```

### Generate a mainworld only

```bash
# One random world (human-readable summary)
python traveller_world_gen.py

# Named world with a fixed seed
python traveller_world_gen.py --name Cogri --seed 42

# JSON output
python traveller_world_gen.py --name Cogri --seed 42 --json

# Self-contained HTML card
python traveller_world_gen.py --name Cogri --seed 42 --html > cogri.html

# Generate a subsector's worth (5 worlds)
python traveller_world_gen.py --count 5
```

### Generate an SVG system map

Draw a star system as a visual orbit diagram with arc zones (one per star) and an orbit table.

```bash
# Procedurally generated system (random seed, dark background)
python system_map.py --name Ardenne --out /tmp/ardenne_map.svg

# With a fixed seed for reproducibility
python system_map.py --name Ardenne --seed 1000 --out /tmp/ardenne_map.svg

# With white background (light theme) instead of dark
python system_map.py --name Ardenne --seed 1000 --white-bg --out /tmp/ardenne_light.svg

# For multi-star systems, increase canvas width so tables have room
python system_map.py --name Trinary --seed 5555 --width 2400 --out /tmp/trinary_map.svg

# Default: random seed, name "Unnamed", output to /tmp/traveller_system_map.svg, dark background
python system_map.py
```

The SVG shows:
- **Arc zones** — one stacked zone per star with orbit arcs scaled to fit the canvas
- **Companion stars** — displayed as dashed arcs in the primary star's zone for context
- **Orbit table** — a data table zone below with orbit slots listed per star
- **Mainworld** — highlighted in the arc zone and marked in the table

Open the SVG in any web browser or image viewer. The map includes all orbital data: world type, orbit#, AU, temperature zone, and notes.

**Example summary output:**

```
========================================================
  Cogri  —  B5525A9-7
========================================================
  Trade codes : Ni Po
  Bases       : S
  Travel zone : Amber
  Gas giant   : Yes
--------------------------------------------------------
  Starport    : B  (Good (Refined fuel, spacecraft shipyard, repair))
  Size        : 5  (8,000 km, 0.45G)
  Atmosphere  : 5  (Thin)
  Temperature : Cold
  Hydrograph. : 2  (A few small seas (16-25%))
  Population  : 5  (Hundreds of thousands)
  Government  : A  (Charismatic Dictator)
  Law Level   : 9
  Tech Level  : 7
========================================================
```

**Example JSON output:**

```json
{
  "name": "Cogri",
  "uwp": "B5525A9-7",
  "starport": {
    "code": "B",
    "description": "Good (Refined fuel, spacecraft shipyard, repair)"
  },
  "size": { "code": 5, "diameter_km": "8,000", "surface_gravity": "0.45G" },
  "atmosphere": { "code": 5, "name": "Thin", "survival_gear": "None" },
  "temperature": "Cold",
  "hydrographics": { "code": 2, "description": "A few small seas (16-25%)" },
  "population": { "code": 5, "range": "Hundreds of thousands" },
  "government": { "code": 10, "name": "Charismatic Dictator" },
  "law_level": 9,
  "tech_level": 7,
  "has_gas_giant": true,
  "bases": ["S"],
  "trade_codes": ["Ni", "Po"],
  "travel_zone": "Amber",
  "notes": []
}
```

---

## Using the Python API

### Full system generation

```python
from traveller_system_gen import generate_full_system

system = generate_full_system(name="Ardenne", seed=1000)
print(system.summary())           # full text: stars + orbits + mainworld
print(system.to_json())           # complete JSON
print(system.mainworld.uwp())     # e.g. "C473574-8"
print(system.mainworld_orbit.orbit_number)  # e.g. 3.0
```

### System from an existing mainworld

```python
from traveller_world_gen import World
from traveller_system_gen import generate_system_from_world

# Reconstruct a World from a previously generated (or API-returned) JSON dict
world = World.from_dict(world_dict)    # tolerates nested or flat code forms

# Generate a full star system around it — UWP and PBG are preserved exactly;
# stellar data and orbits are fresh procedural output;
# temperature is recalculated from the assigned orbital position
system = generate_system_from_world(world, seed=99)
print(system.mainworld.uwp())          # original UWP preserved
print(system.mainworld.temperature)    # recalculated from new orbit
print(system.mainworld_orbit.canonical_profile)  # canonical UWP stamped on orbit slot
```

### System from TravellerMap canonical data

```python
from traveller_map_fetch import generate_system_from_map

# By name — sector is always required
system = generate_system_from_map(name="Regina", sector="Spinward Marches", seed=42)
print(system.mainworld.uwp())     # canonical UWP, e.g. "A788899-C"
print(system.mainworld.name)      # "Regina"
print(system.summary())           # mainworld orbit row shows canonical UWP

# With all secondary world and moon profiles
system = generate_system_from_map(
    name="Mora", sector="Spinward Marches", seed=7, attach=True
)
print(system.to_html(detail_attached=True))

# By hex position (skips name search, more precise)
system = generate_system_from_map(sector="Spinward Marches", hex_pos="1910")
```

### Mainworld only

```python
from traveller_world_gen import generate_world

# Generate a random world
world = generate_world(name="Mora")

# Access characteristics directly
print(world.uwp())           # "A867A69-F"
print(world.tech_level)      # 15
print(world.trade_codes)     # ["Hi", "Ht", "In", "Ri"]
print(world.travel_zone)     # "Green"

# Serialise
text = world.summary()       # Human-readable text block
data = world.to_dict()       # Plain dict (schema-conformant)
json_str = world.to_json()   # JSON string (indent=2 by default)
html_str = world.to_html()   # Standalone HTML card

# Reproducible generation
import random
random.seed(42)
world = generate_world(name="Regina")
```

---

## REST API (Azure Functions)

The API exposes thirteen HTTP endpoints across three groups.

### Mainworld endpoints — CRB generation only

| Method | Route | Description |
|--------|-------|-------------|
| `GET`  | `/api/world` | Generate one world |
| `POST` | `/api/world` | Generate one world (parameters in JSON body) |
| `GET`  | `/api/world/{name}` | Generate one world; name from URL path |
| `POST` | `/api/worlds` | Batch generation (up to 20 worlds) |
| `GET`  | `/api/world/{name}/card` | Standalone HTML display card |

### System endpoints — WBH stellar + orbit + CRB mainworld

| Method | Route | Description |
|--------|-------|-------------|
| `GET`  | `/api/system` | Generate a full star system |
| `POST` | `/api/system` | Generate a full star system (parameters in JSON body) |
| `GET`  | `/api/system/{name}` | Generate a full star system; name from URL path |
| `GET`  | `/api/system/{name}/card` | Standalone HTML system card |
| `GET`  | `/api/system/full` | Complete system with all secondary worlds and moons |
| `POST` | `/api/system/full` | Complete system with all secondary worlds and moons (JSON body) |
| `POST` | `/api/system/from-world` | Full system around an existing mainworld JSON; UWP/PBG preserved |

### TravellerMap endpoints — canonical UWP + procedural orbital structure

| Method | Route | Description |
|--------|-------|-------------|
| `GET`  | `/api/map/system` | Fetch world from TravellerMap, generate full system |
| `POST` | `/api/map/system` | Same (parameters in JSON body) |
| `GET`  | `/api/map/system/{name}` | World name from URL path |

All JSON responses from mainworld endpoints conform to `traveller_world_schema.json`.
The `/card` endpoints return `text/html; charset=utf-8`.

### The `/api/system/full` endpoint

`/api/system/full` always attaches full secondary world and satellite detail —
no `detail` flag required. It also supports a `format` parameter for choosing
the response type:

| `format` value | Response type | Content-Type |
|----------------|---------------|--------------|
| `json` (default) | Complete TravellerSystem JSON | `application/json` |
| `html` | Self-contained HTML system card | `text/html` |
| `text` | Human-readable text summary | `text/plain` |

### The TravellerMap endpoints

`/api/map/system` fetches the canonical UWP and stellar classification string
from [travellermap.com](https://travellermap.com) and uses them as the basis for
full system generation. The mainworld UWP is exact canonical data; the orbital
structure (secondary world positions, moons) is procedurally generated.

**`sector` is always required** — many world names exist in multiple sectors.
Identify the world by `name` + `sector`, or by `sector` + `hex`.

Returns `400 MISSING_PARAM` if sector is omitted, `400 INVALID_HEX` if `hex`
is present but not a valid 4-digit hex position (e.g. `1910`), `404 NOT_FOUND`
if the world cannot be found on TravellerMap, or `502 UPSTREAM_ERROR` if
TravellerMap is unreachable. Supports the same `detail` and `format`
parameters as the system endpoints.

### The `detail` parameter

The other system endpoints accept an optional `detail` boolean (`?detail=true` or
`{"detail": true}` in the request body). When true, every orbit slot in the
response includes a `detail` object with its secondary world SAH profile
and social codes, and each significant moon carries its own nested `detail`
object with physical and social data.

Without `detail`, the system response contains only stellar data, orbital
structure, and the mainworld — no secondary world or satellite information.

### Quick start — local development

```bash
pip install -r requirements.txt
func start   # Azure Functions Core Tools v4 required
```

```bash
# Mainworld
curl "http://localhost:7071/api/world?name=Mora&seed=7"
curl "http://localhost:7071/api/world/Regina/card" -o world.html

# System — orbital structure only
curl "http://localhost:7071/api/system?name=Ardenne&seed=1000"

# System — with secondary worlds and satellites
curl "http://localhost:7071/api/system/Ardenne?seed=1000&detail=true"

# System HTML card with full detail
curl "http://localhost:7071/api/system/Ardenne/card?seed=1000&detail=true" \
     -o system.html

# Complete system — always includes all worlds and moons
curl "http://localhost:7071/api/system/full?name=Ardenne&seed=1000"
curl "http://localhost:7071/api/system/full?name=Ardenne&seed=1000&format=html" -o ardenne.html
curl "http://localhost:7071/api/system/full?name=Ardenne&seed=1000&format=text"

# TravellerMap — canonical UWP + procedural orbital structure (sector always required)
curl "http://localhost:7071/api/map/system?name=Regina&sector=Spinward+Marches&seed=42"
curl "http://localhost:7071/api/map/system/Mora?sector=Spinward+Marches&seed=7&detail=true"
curl "http://localhost:7071/api/map/system?sector=Spinward+Marches&hex=1910&format=html" \
     -o regina.html

# System from existing mainworld JSON — UWP/PBG preserved; fresh stellar + orbital generation
WORLD=$(curl -s "http://localhost:7071/api/world?name=Cogri&seed=42")
curl -X POST "http://localhost:7071/api/system/from-world" \
     -H "Content-Type: application/json" \
     -d "$WORLD"

# Batch of worlds
curl -X POST "http://localhost:7071/api/worlds" \
     -H "Content-Type: application/json" \
     -d '{"count": 5, "prefix": "Spinward-", "seed": 1}'
```

For the full API reference including all parameters, response schemas,
error codes, authentication, and deployment instructions see
[`docs/AZURE_DEPLOYMENT.md`](docs/AZURE_DEPLOYMENT.md).

### Deployment

```bash
# Create resources (one-time)
az group create --name rg-traveller --location australiaeast
az storage account create --name straveller --resource-group rg-traveller --sku Standard_LRS
az functionapp create \
    --resource-group rg-traveller \
    --consumption-plan-location australiaeast \
    --runtime python --runtime-version 3.11 \
    --functions-version 4 \
    --name traveller-world-gen \
    --storage-account straveller \
    --os-type Linux

# Deploy
func azure functionapp publish traveller-world-gen
```

Authenticate deployed requests with a function key:

```bash
curl "https://traveller-world-gen.azurewebsites.net/api/system/Mora?detail=true&code=<key>"
```

### Environment variables (App Settings)

| Variable | Default | Description |
|----------|---------|-------------|
| `TRAVELLER_MAX_BATCH_SIZE` | `20` | Maximum worlds per batch request (accepted range: 1–1000) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | _(empty)_ | Application Insights telemetry |

---

## Running the tests

The test suite runs with pytest and requires no live Azure runtime — the
`azure-functions` SDK is stubbed automatically if not installed.

```bash
pip install pytest jsonschema
pytest tests/ -v
```

### What is tested

**`test_traveller_world_gen.py`** (414 tests, 27 classes)

- All dice helper functions and clamp behaviour
- Traveller hex digit conversion (0–9, A–G)
- Every generation step in isolation with mocked dice
- All 18 trade code criteria (positive and negative cases)
- All Amber zone triggers and boundary values
- Base generation per starport class, including highport and corsair DMs
- `World.to_dict()` — structure, types, and all sub-objects
- `World.to_json()` — round-trip fidelity, indent modes
- `World.to_html()` — HTML structure, all TL era labels (regression tests
  for the Pre-Stellar/Early Stellar boundary), survival gear danger
  highlighting, HTML escaping
- JSON Schema validation against `traveller_world_schema.json`
  (requires `pip install jsonschema`)
- Integration tests: range bounds, uninhabited world invariants,
  seed reproducibility
- `TestGasGiantOrbitSlot` — `gg_sah` field on `OrbitSlot`, `_gg_diameter()`
  helper, satellite size constraint, satellite note in mainworld record

**`test_function_app.py`** (98 tests, 15 classes)

- All five HTTP endpoints: 200 responses, parameter parsing, content types
- All error codes: invalid seed, name too long, bad JSON body,
  count too large, internal error mocking
- Schema validation of all JSON responses
- Seed determinism across endpoints
- Batch sequencing consistency

---

## Generation rules implemented

### Core Rulebook (CRB pp. 248–261) — mainworld generation

All 13 steps follow the Traveller 2022 Core Rulebook exactly.

| Step | Characteristic | Formula |
|------|---------------|---------|
| 1 | Size | 2D−2 |
| 2 | Atmosphere | 2D−7 + Size (min 0; forced 0 for Size 0–1) |
| 3 | Temperature | 2D + Atmosphere DM |
| 4 | Hydrographics | 2D−7 + Atmosphere + DMs (size, temp, atm type) |
| 5 | Population | 2D−2 |
| 6 | Government | 2D−7 + Population (0 if Pop = 0) |
| 7 | Law Level | 2D−7 + Government (0 if Pop = 0) |
| 8 | Starport | 2D + Population DM → A/B/C/D/E/X |
| 9 | Tech Level | 1D + Starport/Size/Atm/Hydro/Pop/Gov DMs |
| 10 | Bases | 2D per type per starport class (Highport & Corsair DMs applied) |
| 11 | Gas Giant | 2D ≤ 9 → present |
| 12 | Trade Codes | Table lookup (all 18 codes) |
| 13 | Travel Zone | Amber if Atm ≥ 10, Gov 0/7/10, or Law 0/9+ |

When a mainworld is generated in orbital context (system endpoints), step 3 is
replaced by `generate_temperature_from_orbit()`, which derives temperature from
the world's HZ deviation rather than a random roll. When the mainworld orbit is a
gas giant, the mainworld is generated as a satellite: size is clamped to
`[1, gg_diameter−1]` (WBH p.57) and a note is added to the world record.

---

### World Builder's Handbook (WBH Sept 2023) — stellar and system generation

#### Stellar generation (pp. 14–29)

| Procedure | Details |
|-----------|---------|
| Primary star type | Spectral class (O B A F G K M) and luminosity class (Ia Ib II III IV V VI) rolled from WBH tables; Brown Dwarfs and White Dwarfs handled |
| Star properties | Mass, temperature, diameter, and luminosity interpolated from WBH lookup tables by spectral type and subtype (0–9) |
| System age | Rolled for primary; constrained by main-sequence lifespan; shared across all stars |
| Multiple stars | Close, Near, and Far secondaries; tight Companion pairs (e.g. Aa/Ab) |
| Non-primary typing | Random, Lesser, Sibling, or Twin procedure; mass ordering enforced (`candidate.mass < parent.mass`) |
| Non-primary properties | Same interpolation tables as primary |

#### Orbit placement (pp. 36–51)

| Step | Procedure | Details |
|------|-----------|---------|
| World counts | Gas giants, belts, terrestrials | 2D rolls with DMs for luminosity class |
| Empty orbits | Step 4 | 2D roll; result > 9 → that many empty slots added |
| MAO | Minimum Allowable Orbit# | Interpolated from WBH table by spectral type, subtype, and luminosity class |
| HZCO | Habitable Zone Centre Orbit# | `√(combined luminosity) × 3.0` |
| Baseline number | Step 3 | 2D + DMs for luminosity class, companion presence, world count |
| Baseline orbit | Step 3a/3b/3c | 3a: HZ world present; 3b: cold system (all worlds beyond HZ); 3c: hot system (all worlds inside HZ) |
| Spread | Step 5 | `(baseline_orbit − MAO) / baseline_num`; floored and capped by available range |
| Slot placement | Step 6 | `MAO + spread + (2D−7)×spread/10` per slot; additive gap check |
| World type assignment | Step 8 | Pool of gas giants → belts → terrestrials placed into slots; remainder as terrestrial |
| Mainworld selection | Step 9 | Scored by HZ proximity, temperature zone, world type, and star role |

Multiple-star systems allocate worlds to each star proportionally by available
orbital range. Primary star's `max_o` is reduced to `companion.orbit_number − 1.0`
when a Close/Near/Far secondary is present.

#### Secondary world detail (pp. 55–77, 162–163)

| Procedure | Details |
|-----------|---------|
| SAH profile | Size, Atmosphere, Hydrographics rolled for every non-mainworld orbit slot and significant moon |
| Population cap | `mainworld.population − 1D` rolled once per system; applied as a ceiling to all secondary worlds and moons |
| TL viability check | `minimal_sustainable_TL(atmosphere) > mainworld_TL` → uninhabited regardless of population roll |
| Government | Dependent procedure (WBH Case 1): 1D on Secondary World Government table |
| Law Level | 1D−3 + Government |
| Tech Level | 1D−1 + Population DM |
| Spaceport | Y/H/G/F scale (not the CRB A–X starport scale) |
| Gas giants | Never directly inhabited; moons may be |
| Belt SAH | Fixed at `000`; atmosphere 0 used for TL viability check (TL ≥ 8 required) |

#### Moon generation (pp. 55–57)

| Procedure | Details |
|-----------|---------|
| Quantity | Size 1–2: 1D−5; Size 3–9: 2D−8; Size A–F: 2D−6; Small GG: 3D−7; Medium/Large GG: 4D−6; DM−1 per die if Orbit# < 1.0 |
| Result = 0 | One significant ring (R) instead of moons |
| Terrestrial moon sizing | 1D picks range: 1–3 → size S; 4–5 → D3−1 (0=ring); 6 → (parent−1) − 1D |
| Gas giant moon sizing | 1D picks range: 1–3 → size S; 4–5 → D3−1; 6 → special table (1D: 1–3→1D, 4–5→2D−2, 6→2D+4) |
| Twin/near-twin check | If moon size = parent−2: roll 2D; 2 → near-twin (parent−1), 12 → twin (parent) |
| Moon size cap | Moon cannot exceed parent size |
| Ring consolidation | Multiple rings on one planet collapsed to a single R0N entry |
| Moon SAH and social | Full secondary world procedure using parent orbit's HZ deviation |

#### Not yet implemented

The following WBH procedures are explicitly out of scope:

| Feature | WBH pages |
|---------|-----------|
| Anomalous orbits (random, eccentric, inclined, retrograde, trojan) | pp. 49–50 |
| Orbital eccentricity | p. 51 |
| Orbital periods | — |
| Moon orbit placement (Hill sphere, Roche limit, PD distances) | pp. 74–77 |
| Moon orbit adjacency DMs (3 of 4 conditions require eccentricity data) | p. 56 |
| Secondary world independent government (Case 2) | p. 162 |
| Secondary world classifications (Colony, Freeport, Mining, etc.) | p. 163 |
| World physical detail beyond SAH (density, gravity, seismic stress, etc.) | pp. 74–130 |
| Belt physical detail (span, composition, bulk, resource rating) | pp. 131–133 |
| Post-stellar special circumstances (neutron stars, black holes, pulsars) | pp. 219+ |

---

## JSON Schema

`traveller_world_schema.json` is a JSON Schema draft 2020-12 document
describing the complete output of `World.to_dict()` / `World.to_json()`.

Key constraints:
- `"additionalProperties": false` throughout
- UWP validated by regex `^[ABCDEX][0-9A-G]{6}-[0-9A-G]$`
- `starport.code` — enum of `A B C D E X`
- `bases` items — enum of `C H M N S`
- `trade_codes` items — enum of all 18 valid codes
- `temperature` — enum of 5 valid categories
- `travel_zone` — enum of `Green Amber Red`
- All numeric codes have explicit `minimum` / `maximum` constraints

---

## AI assistance disclosure

This project was developed with the assistance of
[Claude](https://claude.ai) (Anthropic), an AI assistant.

Claude contributed to the architecture, implementation, tests, and this
README across an interactive development session in which rulebook pages
were provided as source material. All generation steps, lookup tables, and
descriptions were verified against the Traveller 2022 Core Rulebook and
World Builder's Handbook during the session.

The human author reviewed, directed, and is responsible for the published code.

---

## Licence

This project is released under the [MIT Licence](LICENSE).

**Traveller IP notice:** This software implements rules and procedures from
the Traveller roleplaying game. Any use of this software in connection with
the Traveller intellectual property is subject to Mongoose Publishing's
[Fair Use Policy](https://www.mongoosepublishing.com/pages/traveller-licensing),
which prohibits commercial use. You may not use this software commercially
in connection with the Traveller IP without an appropriate licence from
Mongoose Publishing.

The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977–2025 Mongoose Publishing. All rights reserved.

This project is an unofficial fan work and is not affiliated with or
endorsed by Mongoose Publishing.
