# azure-sync.md — Azure API deployment packaging

**Last updated:** Session 134

All generation modules now live in the `src/traveller_gen/` Python package.
Deployment to `azure-api/` is done with `pip install --target` — no manual
file copying is required. The old file-by-file `cp` procedure was retired in
Session 134 (issue #156).

---

## How it works

`scripts/prepare_azure.sh` (local) and `.github/workflows/azure-deploy.yml`
(CI) both run:

```bash
pip install --quiet --target azure-api/ --no-deps .
```

This installs the `traveller_gen` package directory into `azure-api/` exactly
as it exists in `src/traveller_gen/`, including templates and the JSON schema.
`--no-deps` is intentional — Jinja2 and jsonschema are already declared in
`azure-api/requirements.txt` and installed separately.

`fastapi/` is still copied separately (it is not part of the Python package):

```bash
rm -rf azure-api/fastapi
cp -r fastapi azure-api/fastapi
```

---

## What lives in azure-api/ after bundling

The following are deployment artefacts (gitignored, not committed):

```
azure-api/traveller_gen/          # the installed package directory
azure-api/traveller_gen-*.dist-info/  # pip metadata
azure-api/fastapi/                # copied separately
```

`.gitignore` covers all three patterns:
```
azure-api/traveller_gen/
azure-api/traveller_gen-*.dist-info/
azure-api/fastapi/
```

---

## Running `prepare_azure.sh`

```bash
bash scripts/prepare_azure.sh
```

This script:
1. Calls `scripts/compute_version.sh` to regenerate `src/traveller_gen/_version.py`
2. Runs `pip install --target azure-api/ --no-deps .` to bundle the package
3. Copies `fastapi/` into `azure-api/fastapi/`

Run this before `func start` for local Azure Functions testing.

---

## Adding a new generation module

1. Create the module at `src/traveller_gen/new_module.py`.
2. Add relative imports (`from . import X`) for any intra-package dependencies.
3. Update `azure-api/function_app.py` to import from `traveller_gen.new_module`.
4. Run `bash scripts/prepare_azure.sh` to bundle locally.
5. Verify `func start` loads without errors.
6. No changes needed to `prepare_azure.sh` or the CI workflow — they install
   the whole package, so the new module is included automatically.
7. Add the module to CLAUDE.md routing table and `context/` if needed.

---

## Verification

After running `prepare_azure.sh`, confirm the package is installed:

```bash
ls azure-api/traveller_gen/new_module.py   # example
```

To confirm the function app imports cleanly:

```bash
cd azure-api
../.venv/bin/python -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'fastapi')
import function_app; print('OK')
"
```

A clean load prints `OK`.

---

## History

| Session | Change |
|---------|--------|
| 134 | Replaced file-by-file `cp` with `pip install --target`; retired the azure-sync file list |
| 133 | `traveller_world_culture_detail.py` and `traveller_world_importance.py` added to cp list (both had been missing) |
