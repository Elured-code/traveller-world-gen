---
name: TravellerMap integration status
description: State of the TravellerMap API integration — endpoints, field mapping, canonical vs procedural data
type: project
originSessionId: 6212b077-103f-442a-86d1-e3929dce3ad5
---
TravellerMap integration is complete and pylint-clean (10.00/10).

**Why:** Many Traveller world names repeat across sectors (e.g. "Regina"), so sector is always required for TravellerMap lookups to avoid ambiguity.

**How to apply:** Any future work touching `traveller_map_fetch.py` or `function_app.py` map endpoints must keep sector required.

### Endpoints added to `function_app.py`
- GET/POST `/api/map/system` — sector required, name or hex required
- GET `/api/map/system/{name}` — sector required as query param

### Field name mapping (`traveller_map_fetch.py`)
TravellerMap API returns inconsistent capitalisation across versions. `_raw_field()` handles this with case-insensitive multi-alias lookup:
- UWP: `"UWP"`, `"Uwp"`
- Stars: `"Stars"`, `"Stellar"`, `"Star"`
- PBG: `"PBG"`, `"Pbg"`
- Bases: `"Bases"`, `"Base"`
- Remarks: `"Remarks"`, `"Remark"`
- Zone: `"Zone"`, `"TravelCode"`

### Canonical vs procedural data reconciliation
`generate_orbits()` always produces its own gas/belt counts from dice rolls. After `reconstruct_world()` sets canonical PBG values, the pipeline overwrites `orbits.gas_giant_count`, `orbits.belt_count`, and recalculates `orbits.total_worlds` to keep them consistent.

Temperature is NOT in the UWP — it is always derived from orbital position after placement.

### Files changed in this work
- `function_app.py` — added `_map_system_response()`, two endpoint handlers, updated imports
- `shared/helpers.py` — added `ERR_MISSING_PARAM`, `MAX_SECTOR_LENGTH`, `parse_sector()`
- `traveller_map_fetch.py` — added `_raw_field()`, `_world_sector_name()`, rewrote `_fetch_world_json()`, updated `fetch_world_data()` and `generate_system_from_map()`
- `README.md`, `docs/AZURE_DEPLOYMENT.md`, `docs/developer-guide.md` — all updated to reflect sector-required, new endpoints, CLI flags
