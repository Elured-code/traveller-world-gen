# common.md — Project baseline

Read this file at the start of every session. It covers project identity,
repository layout, code quality standards, the test suite, CI, and licence.

---

## What this project is

A Python implementation of Traveller RPG star system and world generation,
exposed as a REST API via Azure Functions. Two source books are implemented:

- **CRB** — Traveller 2022 Core Rulebook (Mongoose Publishing), pp. 248–261:
  mainworld generation (all 13 steps).
- **WBH** — World Builder's Handbook, Sept 2023 (Mongoose Publishing):
  stellar generation, orbit placement, secondary world SAH/social, moon
  generation.

**Branch:** `feature/updates`  
**Main branch:** `main`  
**Virtual environment:** `.venv` (Python 3.11) — includes PySide6 for the Qt desktop UI

---

## Repository layout

```
traveller-world-gen/
├── traveller_stellar_gen.py     # WBH pp.14-29: stars, multiples, age
├── traveller_orbit_gen.py       # WBH pp.36-51: orbits, MAO, HZCO, spread
├── traveller_system_gen.py      # Integration: stellar + orbits + mainworld
├── traveller_world_gen.py       # CRB pp.248-261: mainworld, UWP, trade codes
├── traveller_world_physical.py  # WBH pp.74-77, 103-107: diameter, density, gravity, axial tilt, day length, tidal lock
├── traveller_hydro_detail.py    # WBH p.93: hydrographic detail — surface liquid percentage
├── traveller_world_detail.py    # Secondary world SAH/social + satellite detail; belt physical attached here
├── traveller_belt_physical.py   # WBH pp.131-133: belt span, composition, bulk, resource rating, significant bodies
├── traveller_moon_gen.py        # Moon quantity, sizing, rings, SAH/social
├── traveller_map_fetch.py       # TravellerMap integration; also a CLI
├── traveller_world_schema.json  # JSON Schema (draft 2020-12) for World.to_dict()
├── system_map.py                # SVG system map: per-star arc zones, log-AU scale, orbit table
│
├── function_app.py              # Azure Functions v2 — all 13 HTTP endpoints
├── shared/
│   └── helpers.py               # Request parsing, response builders, error codes
│
├── gen-ui/
│   ├── app.py                   # PySide6 (Qt6) desktop UI — fully working
│   ├── README.md
│   └── requirements.txt         # PySide6>=6.4.0; bundled Qt, no system libs required
│
├── tests/
│   ├── test_traveller_world_gen.py  # mainworld generation
│   ├── test_world_physical.py       # physical characteristics and tidal lock
│   ├── test_belt_physical.py        # belt physical detail
│   ├── test_hydro_detail.py         # 29 tests — hydrographic detail
│   └── test_function_app.py         # API endpoints
├── conftest.py                  # pytest path setup + azure.functions stub
│
├── context/                     # AI context files (this directory)
├── docs/
│   ├── AZURE_DEPLOYMENT.md      # Full REST API reference (bash + PowerShell)
│   ├── developer-guide.md       # Human-facing architecture and API reference
│   └── VSCODE.md
├── CLAUDE.md                    # Router — which context files to read
└── README.md
```

---

## Code quality standards

### Pylint

Target: **10.00/10 per file**. **Always run one file at a time** — never
pass multiple files in a single invocation:

```bash
.venv/bin/pylint traveller_stellar_gen.py
```

Multi-file runs trigger R0801 (duplicate-code) false positives due to shared
HTML boilerplate in `traveller_system_gen.py` and `traveller_world_gen.py`.
The code is intentionally separate (different data structures); only the
per-file score matters. Multi-file runs also trigger `too-many-lines` at
file-level thresholds that single-file runs do not hit.

Common suppressions used in this codebase:

| Suppression | Where |
|-------------|-------|
| `too-many-arguments,too-many-positional-arguments` | Helpers with 5+ params |
| `too-many-locals` | Complex generation functions |
| `too-many-instance-attributes` | Dataclasses (on class line, not decorator) |
| `too-many-branches,too-many-statements,too-many-return-statements` | Rule-table dispatch functions |
| `import-outside-toplevel` | `import argparse` / `import sys` inside `main()` |
| `missing-function-docstring` | `main()` alongside `too-many-return-statements` |
| `broad-exception-caught` | All endpoint handlers (deliberate) |
| `locally-disabled,suppressed-message` | Module-level disable comment — silences I0011/I0020 noise |
| `too-many-lines` | `traveller_system_gen.py` (file exceeded 1000 lines in Session 37) |

### Pylance (VS Code)

Type checking mode: `"basic"` (set in `.vscode/settings.json`). All
`reportArgumentType`, `reportUndefinedVariable`, and `reportAttributeAccessIssue`
errors must be resolved. Key patterns:

- `Optional[str]` / `Optional[int]` on parameters that accept `None`
- `from __future__ import annotations` makes all annotations lazy — quoted
  forward references are redundant when this import is present
- `field(default=X, init=False)` on dataclass attributes not accepted by
  `__init__` (e.g. `Moon._ring_count`) — avoids `reportAttributeAccessIssue`

---

## Test suite

990 tests total; all must pass before committing.

```bash
# All tests
.venv/bin/pytest tests/ -q

# Mainworld generation only
.venv/bin/pytest tests/test_traveller_world_gen.py -v

# API layer only
.venv/bin/pytest tests/test_function_app.py -v
```

The Azure Functions SDK is stubbed automatically by `conftest.py` — no live
Azure runtime needed.

---

## CI — dependency vulnerability scan

`.github/workflows/dependency-audit.yml` runs `pip-audit` on every branch push
and on PRs targeting `main`. Audits `requirements.txt` and
`gen-ui/requirements.txt` separately. Hard-fails on any vulnerability. Uploads
a JSON report artifact (30-day retention).

---

## Licence and IP constraints

**MIT Licence** governs the code. Use in connection with the Traveller IP is
additionally governed by **Mongoose Publishing's Fair Use Policy** — no
commercial use.

Every Python source file must contain the standardised IP notice in its module
docstring:

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
