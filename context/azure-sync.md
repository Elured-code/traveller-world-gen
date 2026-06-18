# azure-sync.md — Azure API file synchronisation

**Last updated:** Session 134

Whenever a new Python module is created at the repo root it must be added to
**three places** before `func start` (local) or CI deploy (Azure) will work.
Missing a single entry produces a silent `ImportError` that the Azure Functions
host often surfaces as a 404 or startup banner rather than a traceback.

---

## Why files are gitignored in azure-api/

`azure-api/` is the deployment package for Azure Functions.  All generator
modules live at the repo root; they are **copied** into `azure-api/` at deploy
time so that `function_app.py` can import them.  Keeping copies inside
`azure-api/` committed would create permanent drift — the gitignored copies
are a deployment artefact, not a source of truth.

The `.gitignore` entry at the root covers:
```
azure-api/fastapi/
azure-api/templates/
azure-api/html_render.py
azure-api/system_map.py
azure-api/system_pipeline.py
azure-api/tables.py
azure-api/traveller_*.py
azure-api/world_codes.py
azure-api/traveller_world_schema.json
azure-api/_version.py
```

---

## Authoritative file list

This is the single source of truth.  **Keep all three locations below in sync
with this list.**

### Individual Python modules (copied flat into azure-api/)

| File | Purpose |
|------|---------|
| `_version.py` | Auto-generated version (compute_version.sh) |
| `html_render.py` | Jinja2 HTML rendering helpers |
| `system_map.py` | SVG system map generation |
| `system_pipeline.py` | Unified post-generation pipeline |
| `tables.py` | Shared lookup tables |
| `traveller_belt_physical.py` | Belt physical characteristics |
| `traveller_hydro_detail.py` | Hydrographic detail |
| `traveller_map_fetch.py` | TravellerMap API fetch |
| `traveller_moon_gen.py` | Moon generation |
| `traveller_orbit_gen.py` | Orbital mechanics |
| `traveller_stellar_gen.py` | Stellar generation |
| `traveller_system_gen.py` | System generation |
| `traveller_world_atmosphere_detail.py` | Atmosphere detail |
| `traveller_world_culture_detail.py` | Cultural characteristics |
| `traveller_world_detail.py` | World detail attachment |
| `traveller_world_gen.py` | Core world generation |
| `traveller_world_government_detail.py` | Government detail |
| `traveller_world_importance.py` | Importance + economic characteristics |
| `traveller_world_law_detail.py` | Law detail |
| `traveller_world_physical.py` | Physical characteristics |
| `traveller_world_population_detail.py` | Population detail |
| `traveller_world_schema.json` | JSON schema |
| `traveller_world_tech_detail.py` | Technology detail |
| `world_codes.py` | Shared codes and constants |

### Directories (copied recursively, destination cleared first)

| Source | Destination |
|--------|-------------|
| `fastapi/` | `azure-api/fastapi/` |
| `templates/` | `azure-api/templates/` |

---

## The three locations that must stay in sync

### 1. `scripts/prepare_azure.sh`  (local dev)

Run before `func start`:
```bash
bash scripts/prepare_azure.sh
```
This copies all modules listed above into `azure-api/` and runs
`compute_version.sh`.  It also does `rm -rf azure-api/fastapi` and
`rm -rf azure-api/templates` before re-copying those directories, ensuring
stale files don't linger.

### 2. `.github/workflows/azure-deploy.yml`  (CI deploy)

The "Assemble deployment package" step mirrors `prepare_azure.sh`.  The `cp`
command in that step must list every module individually.

### 3. This file — `context/azure-sync.md`

The authoritative list above is the reference.  When adding a new module,
update the table here first, then propagate to (1) and (2).

---

## Procedure: adding a new root-level module

1. Create and test the module at the repo root.
2. Add its filename to the table in this file.
3. Add it to the `cp` block in `scripts/prepare_azure.sh`.
4. Add it to the `cp` block in `.github/workflows/azure-deploy.yml`
   (the "Assemble deployment package" step).
5. Run `bash scripts/prepare_azure.sh` to sync locally.
6. Verify `func start` loads without errors (`func start` in `azure-api/`).
7. Commit both script changes alongside the new module.

**Never commit the copied file inside `azure-api/`** — the gitignore pattern
`azure-api/traveller_*.py` covers all generator modules, but if Git begins
tracking a file before the ignore was in place you must `git rm --cached` it.

---

## Verification

After running `prepare_azure.sh`, confirm the module is present:
```bash
ls azure-api/traveller_world_importance.py   # example
```

To confirm the function app loads cleanly without starting the full host:
```bash
cd azure-api
../.venv/bin/python -c "
import sys; sys.path.insert(0,'fastapi')
import function_app; print('OK')
"
```

A clean load prints `OK`.  An `ImportError` or missing-module error means
`prepare_azure.sh` is out of date.

---

## History of sync failures

| Session | Module missed | Effect |
|---------|---------------|--------|
| 133 | `traveller_world_culture_detail.py` (added Session 127) | CI deploy missing module for 6 sessions |
| 133 | `traveller_world_importance.py` (added Session 132) | CI deploy missing module for 1 session; local 404 on `func start` |
