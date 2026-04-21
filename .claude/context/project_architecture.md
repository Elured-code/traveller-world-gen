---
name: Project architecture overview
description: High-level structure of traveller-world-gen — Azure Functions, modules, CLI entry points
type: project
originSessionId: 6212b077-103f-442a-86d1-e3929dce3ad5
---
Python Azure Functions v2 (decorator-based, single `function_app.py` registration) + CLI scripts for Traveller RPG world generation.

### Key files
- `function_app.py` — all HTTP endpoint handlers (12 endpoints)
- `shared/helpers.py` — parse/validate params, build JSON responses, error code constants
- `traveller_map_fetch.py` — TravellerMap API integration; also a CLI (`python traveller_map_fetch.py`)
- World generation modules in project root (star system, worlds, orbits, etc.)

### Endpoint categories
- `/api/world/*` — procedural world generation
- `/api/system/*` — procedural star system generation
- `/api/map/system` and `/api/map/system/{name}` — TravellerMap canonical data + procedural orbits

### Response format
All endpoints support `?format=json` (default), `?format=html`, `?format=text` and optional `?seed=<int>` for reproducibility.

### Error response shape
```json
{"error": {"code": "MACHINE_CODE", "message": "Human readable"}}
```
Error codes in `shared/helpers.py`: `ERR_INVALID_SEED`, `ERR_INVALID_COUNT`, `ERR_COUNT_TOO_LARGE`, `ERR_INVALID_BODY`, `ERR_NAME_TOO_LONG`, `ERR_MISSING_PARAM`, `ERR_NOT_FOUND`, `ERR_UPSTREAM`, `ERR_INTERNAL`.
