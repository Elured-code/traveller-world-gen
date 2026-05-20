# api-layer.md — function_app.py and shared/helpers.py

Read this when working on Azure Functions endpoints, request parsing, error
codes, or response formatting.

---

## Endpoints

All 13 endpoints are in `function_app.py`. Auth level: `FUNCTION` (key required).

### Mainworld endpoints (CRB — fast)

| Method | Route | Description |
|--------|-------|-------------|
| GET/POST | `/api/world` | Generate one mainworld |
| GET | `/api/world/{name}` | Mainworld by URL path name |
| POST | `/api/worlds` | Batch (up to `TRAVELLER_MAX_BATCH_SIZE`, default 20) |
| GET | `/api/world/{name}/card` | Standalone HTML card |

### System endpoints (WBH stellar + orbit + CRB mainworld)

| Method | Route | Description |
|--------|-------|-------------|
| GET/POST | `/api/system` | Full star system |
| GET | `/api/system/{name}` | Full system by URL path name |
| GET | `/api/system/{name}/card` | Standalone HTML system card |
| GET/POST | `/api/system/full` | Complete system — `attach_detail()` always called; selectable `format` |
| POST | `/api/system/from-world` | Full system around an existing mainworld JSON; UWP/PBG preserved |

### TravellerMap endpoints (canonical UWP + procedural orbits)

| Method | Route | Description |
|--------|-------|-------------|
| GET/POST | `/api/map/system` | Fetch from TravellerMap, generate full system |
| GET | `/api/map/system/{name}` | Same; name from URL path |

**`sector` is always required** on all TravellerMap endpoints. Many world names
exist in multiple sectors. Returns `400 MISSING_PARAM` if absent.

---

## Common parameters

| Parameter | Notes |
|-----------|-------|
| `name` | World name, max 64 chars |
| `seed` | Integer RNG seed for deterministic output |
| `detail` | Boolean; triggers `attach_detail()` on system endpoints |
| `format` | `json` (default) \| `html` \| `text` |
| `sector` | Required on map endpoints |
| `hex` | 4-digit hex position e.g. `1910`, must match `[0-9A-Fa-f]{4}` |

---

## API error codes

| Code | HTTP | Trigger |
|------|------|---------|
| `INVALID_SEED` | 400 | `seed` not a valid integer |
| `INVALID_COUNT` | 400 | `count` not a positive integer |
| `COUNT_TOO_LARGE` | 422 | `count` exceeds `TRAVELLER_MAX_BATCH_SIZE` |
| `INVALID_BODY` | 400 | Malformed JSON or invalid field |
| `INVALID_HEX` | 400 | `hex` present but not a valid 4-digit hex position |
| `NAME_TOO_LONG` | 400 | Name exceeds 64 characters |
| `MISSING_PARAM` | 400 | Required parameter absent (`sector` on map endpoints) |
| `NOT_FOUND` | 404 | World not found on TravellerMap |
| `UPSTREAM_ERROR` | 502 | TravellerMap unreachable |
| `INTERNAL_ERROR` | 500 | Unexpected server-side failure |

Error response shape:
```json
{"error": {"code": "MACHINE_CODE", "message": "Human readable description."}}
```

---

## `shared/helpers.py` — parameter parsing reference

| Helper | Returns | Notes |
|--------|---------|-------|
| `parse_name(req, route_name)` | `(str\|None, err\|None)` | Max 64 chars; priority: path → query → body |
| `parse_seed(req)` | `(int\|None, err\|None)` | Query or body |
| `parse_sector(req)` | `(str\|None, err\|None)` | Max 64 chars; query or body |
| `parse_hex_pos(req, body)` | `(str\|None, err\|None)` | Must match `[0-9A-Fa-f]{4}`; returns `INVALID_HEX` if wrong format |
| `parse_world_json(req)` | `(dict\|None, err\|None)` | Body must contain `uwp` or characteristic sub-fields; returns `INVALID_BODY` if absent/malformed |
| `parse_count(req)` | `(int, err\|None)` | 1 to `max_batch_size()` |
| `parse_detail(req)` | `bool` | Accepts `true`, `1`, `yes` (case-insensitive) |
| `parse_orbital_eccentricity(req)` | `bool` | Accepts `true`, `1`, `yes`; gates eccentricity rolls (WBH p.27) |
| `parse_orbital_inclination(req)` | `bool` | Accepts `true`, `1`, `yes`; gates inclination rolls (WBH p.28) |
| `parse_format(req)` | `str` | `"json"` \| `"html"` \| `"text"` |
| `max_batch_size()` | `int` | Reads `TRAVELLER_MAX_BATCH_SIZE` env var; bounds-checked 1–1000; default 20 |
| `apply_seed(seed)` | `None` | Calls `random.seed(seed)` if seed is not None |
| `ok(body, status_code)` | `HttpResponse` | JSON 200 (or custom) response |
| `error(message, code, status_code)` | `HttpResponse` | JSON error response |

---

## Per-endpoint behaviour notes

**`/api/system/full`** — Calls `generate_full_system()` then unconditionally
calls `attach_detail()`. No `detail` parameter is accepted or needed. The
`format` parameter controls serialisation: `to_dict()` for JSON,
`to_html(detail_attached=True)` for HTML, `summary()` for text.

**`/api/map/system`** — Delegates to `generate_system_from_map()`. Catches:
`LookupError` (→ 404 `NOT_FOUND`), `urllib.error.URLError` (→ 502
`UPSTREAM_ERROR`), general `Exception` (→ 500 `INTERNAL_ERROR`). The
`URLError` handler logs the upstream detail server-side but returns only a
generic message to the caller. Supports `detail`, `format`,
`orbital_eccentricity`, and `orbital_inclination` identically to system
endpoints. (Prior to Session 47 / issue #63, the orbital flags were silently
ignored on both map endpoints.)

**`/api/system/from-world`** — Calls `parse_world_json()` to validate the body,
reconstructs `World` via `World.from_dict()`, then calls
`generate_system_from_world()`. PBG counts from the world are reconciled into
the generated `SystemOrbits`. The mainworld orbit slot receives
`canonical_profile = world.uwp()`. Temperature is recalculated from orbital HZ
deviation — temperature in the input JSON is discarded. Returns `400
INVALID_BODY` if body is missing or malformed.

**Mainworld JSON responses** conform to `traveller_world_schema.json`. The
`/card` endpoints return `text/html; charset=utf-8`. The full/map/from-world
endpoints with `format=text` return `text/plain; charset=utf-8`.

---

## `TRAVELLER_MAX_BATCH_SIZE` environment variable

Controls the maximum batch size for `/api/worlds`. Read by `max_batch_size()` in
`shared/helpers.py`. Falls back to `DEFAULT_MAX_BATCH = 20` on parse failure.
The returned value is bounds-checked to `1–1000`; values outside that range are
silently replaced with the default.
