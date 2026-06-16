# Traveller World & System Generator — Azure Functions Deployment

This document covers provisioning, deploying, and operating the Traveller World
& System Generator on Azure Functions. The Azure deployment wraps the FastAPI
application using `AsgiFunctionApp`, so every FastAPI route — including the
interactive API documentation at `/docs` and `/redoc` — is available through
the function app URL.

---

## Contents

1. [Architecture overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [One-time Azure resource provisioning](#3-one-time-azure-resource-provisioning)
4. [GitHub Actions CI/CD](#4-github-actions-cicd)
5. [Local development with Azure Functions Core Tools](#5-local-development-with-azure-functions-core-tools)
6. [Verifying the deployment](#6-verifying-the-deployment)
7. [Environment variables and application settings](#7-environment-variables-and-application-settings)
8. [Authentication](#8-authentication)
9. [API documentation](#9-api-documentation)
10. [Endpoint reference](#10-endpoint-reference)
11. [Error responses](#11-error-responses)

---

## 1. Architecture overview

```
Client
  │
  └──► Azure Functions (Consumption plan, Linux, Python 3.11)
           │
           └──► azure-api/function_app.py
                    AsgiFunctionApp wraps fastapi/app.py
                         │
                         └──► FastAPI application
                                  All routes, rate limiting (SlowAPI),
                                  security headers, and API docs
```

`azure-api/function_app.py` is a thin adapter — it imports the FastAPI `app`
object from `fastapi/app.py` and passes it to `AsgiFunctionApp`. All route
logic lives in `fastapi/app.py`, which is the authoritative implementation
shared by both the Azure Functions deployment and the standalone Docker/uvicorn
deployment.

Generator modules (`traveller_*.py`, `system_pipeline.py`, etc.) are kept in
the repository root and are copied into `azure-api/` at deploy time by the CI
workflow (or by `scripts/prepare_azure.sh` for local development). They are not
committed inside `azure-api/` to avoid duplication.

---

## 2. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Azure CLI | latest | `az login` before running any `az` commands |
| Azure Functions Core Tools | v4 | For local development only |
| Python | 3.11 | Same version as the function app runtime |
| GitHub repository | — | Secrets must be configured (see section 4) |

Install Azure CLI: <https://learn.microsoft.com/cli/azure/install-azure-cli>

Install Azure Functions Core Tools:

```bash
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```

---

## 3. One-time Azure resource provisioning

Run `scripts/create_azure_function_app.sh` to create all required Azure
resources in a single step. Edit the configuration variables at the top of the
script if you want a different resource group name, region, or app name.

```bash
az login
bash scripts/create_azure_function_app.sh
```

The script creates:

| Resource | Name (default) | Purpose |
|----------|---------------|---------|
| Resource group | `traveller-world-gen` | Container for all resources |
| Storage account | `travellerworldgen` | Required by Azure Functions runtime |
| User-assigned managed identity | `traveller-world-gen-uami` | Grants the function app access to storage |
| Application Insights | `traveller-world-gen` | Telemetry and logging |
| Function App | `traveller-world-gen` | Consumption plan, Linux, Python 3.11 |

Application settings configured by the script:

| Setting | Value |
|---------|-------|
| `RATE_LIMIT_PER_MINUTE` | `100/minute` |
| `TRAVELLER_MAX_BATCH_SIZE` | `20` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | populated from the new resource |
| `WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT` | `1` |

The script also enables basic auth publishing credentials (required for
publish-profile-based GitHub Actions deployment) and prints the commands needed
to retrieve the publish profile.

### After the script completes

Retrieve the publish profile XML and store it as a GitHub secret:

```bash
az webapp deployment list-publishing-profiles \
    --name traveller-world-gen \
    --resource-group traveller-world-gen \
    --xml
```

Copy the XML output and add it as a GitHub repository secret named
`AZURE_FUNCTIONAPP_PUBLISH_PROFILE` (Settings → Secrets and variables →
Actions → New repository secret).

Also add a second secret:

| Secret name | Value |
|-------------|-------|
| `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` | Publish profile XML from the command above |
| `AZURE_FUNCTIONAPP_NAME` | `traveller-world-gen` (or your chosen app name) |

---

## 4. GitHub Actions CI/CD

The workflow file is `.github/workflows/azure-deploy.yml`. It triggers
automatically on every push to `main` and can also be triggered manually from
the Actions UI.

### What the workflow does

1. **Checkout** — full git history (`fetch-depth: 0`) is required for the
   version script to count schema-touching commits.
2. **Compute version** — runs `scripts/compute_version.sh ${{ github.run_number }}`
   to generate `_version.py` with `major.minor.patch+build.N`. The version is
   derived from the branch name (`main` → reads `VERSION` file) and the count
   of commits that have touched `traveller_world_schema.json`.
3. **Assemble deployment package** — copies all generator modules, `fastapi/`,
   `templates/`, and `_version.py` into `azure-api/` so that `function_app.py`
   can import them. These files are `.gitignore`d inside `azure-api/` and only
   exist there at deploy time.
4. **Install dependencies** — `pip install --target azure-api/.python_packages/lib/site-packages`
   pre-installs all packages listed in `azure-api/requirements.txt` into the
   deployment package so the function app does not perform a remote build.
5. **Deploy** — `azure/functions-action@v1` publishes `azure-api/` to the
   function app using the publish profile secret.

### Triggering a manual deployment

Actions → Deploy to Azure Functions → Run workflow → Run workflow (on `main`).

An optional `functionapp_name` input overrides the `AZURE_FUNCTIONAPP_NAME`
secret for one-off deployments to a different app.

---

## 5. Local development with Azure Functions Core Tools

Use `scripts/prepare_azure.sh` to mirror what the CI workflow does locally,
then start the function runtime.

```bash
# 1. Install dependencies
pip install -r azure-api/requirements.txt

# 2. Create local settings (only needed once)
cp azure-api/local.settings.json.example azure-api/local.settings.json

# 3. Assemble the deployment package locally
bash scripts/prepare_azure.sh

# 4. Start the function runtime
cd azure-api && func start
```

```powershell
pip install -r azure-api/requirements.txt
Copy-Item azure-api/local.settings.json.example azure-api/local.settings.json
bash scripts/prepare_azure.sh
Set-Location azure-api; func start
```

The local API is available at `http://localhost:7071`. Authentication is not
enforced locally — omit the `?code=` parameter.

`scripts/prepare_azure.sh` runs `scripts/compute_version.sh` first (generating
`_version.py`), then copies the generator modules and `fastapi/` and
`templates/` directories into `azure-api/`. Re-run it whenever you change any
generator module, the FastAPI app, or the templates.

### Example requests against the local runtime

```bash
curl "http://localhost:7071/api/world?name=Cogri&seed=42"
curl "http://localhost:7071/api/system/Mora?seed=7&detail=true"
curl "http://localhost:7071/api/system/full?name=Ardenne&seed=1000&format=html" -o ardenne.html
curl "http://localhost:7071/api/map/system?name=Regina&sector=Spinward+Marches&seed=42"
```

---

## 6. Verifying the deployment

After deployment completes, retrieve your function key and smoke-test the API:

```bash
# Get function keys
az functionapp keys list \
    --name traveller-world-gen \
    --resource-group traveller-world-gen

# Smoke tests
BASE="https://traveller-world-gen.azurewebsites.net"
KEY="<your-function-key>"

curl "$BASE/api/world?name=Mora&seed=7&code=$KEY"
curl "$BASE/api/system/Ardenne?seed=1000&detail=true&code=$KEY"
curl "$BASE/api/system/full?name=Ardenne&seed=1000&format=html&code=$KEY" -o ardenne.html
curl "$BASE/api/map/system?name=Regina&sector=Spinward+Marches&seed=42&code=$KEY"
```

```powershell
$BASE = "https://traveller-world-gen.azurewebsites.net"
$KEY  = "<your-function-key>"

Invoke-RestMethod "$BASE/api/world?name=Mora&seed=7&code=$KEY"
Invoke-RestMethod "$BASE/api/system/Ardenne?seed=1000&detail=true&code=$KEY"
Invoke-WebRequest "$BASE/api/system/full?name=Ardenne&seed=1000&format=html&code=$KEY" -OutFile ardenne.html
```

Check the application version:

```bash
curl "$BASE/api/version?code=$KEY"
```

---

## 7. Environment variables and application settings

Configure in Azure Portal → Function App → Settings → Environment variables, or
with `az functionapp config appsettings set`.

| Variable | Default | Description |
|----------|---------|-------------|
| `TRAVELLER_MAX_BATCH_SIZE` | `20` | Maximum worlds per `/api/worlds` batch. Accepted range 1–1000; values outside this range fall back to the default. |
| `RATE_LIMIT_PER_MINUTE` | `100/minute` | SlowAPI rate limit applied per client IP. Format: `N/minute`. |
| `WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT` | _(unlimited)_ | Caps Consumption plan scale-out. Set to `1` to prevent cost runaway from burst traffic. |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | _(empty)_ | Enables Application Insights telemetry. Populated automatically by `scripts/create_azure_function_app.sh`. |

### HTTP concurrency limits

`azure-api/host.json` sets concurrency limits that apply without any additional
configuration:

| Setting | Value | Effect |
|---------|-------|--------|
| `maxConcurrentRequests` | `10` | Maximum parallel requests per instance. Excess are queued. |
| `maxOutstandingRequests` | `50` | Maximum queued requests. Beyond this, callers receive `429 Too Many Requests` immediately. |

With `WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT=1` the effective global ceiling
is 10 concurrent + 50 queued requests.

---

## 8. Authentication

The function app runs with `AuthLevel.ANONYMOUS` — no function key is required.
This matches the FastAPI standalone deployment and allows the web UI and
interactive API docs to work without credentials.

To retrieve the host key if you change `http_auth_level` to `FUNCTION`:

```bash
az functionapp keys list \
    --name traveller-world-gen \
    --resource-group traveller-world-gen
```

Supply the key as a query parameter or header:

```
?code=<key>
x-functions-key: <key>
```

---

## 9. API documentation

Because the Azure deployment wraps the FastAPI app via `AsgiFunctionApp`, the
auto-generated interactive API docs are available at the same base URL:

| URL | Interface |
|-----|-----------|
| `https://<app>.azurewebsites.net/docs` | Swagger UI — interactive, try-it-now |
| `https://<app>.azurewebsites.net/redoc` | ReDoc — read-only reference |
| `https://<app>.azurewebsites.net/openapi.json` | Raw OpenAPI schema (JSON) |

These pages require an internet connection to `cdn.jsdelivr.net` to load their
CSS and JavaScript assets. The Content Security Policy in `fastapi/app.py`
already permits this domain.

---

## 10. Endpoint reference

### Endpoint summary

**Mainworld endpoints** — CRB 13-step generation, no stellar data.

| Method | Route | Description |
|--------|-------|-------------|
| `GET/POST` | `/api/world` | Generate one mainworld |
| `GET` | `/api/world/{name}` | Generate one mainworld; name from URL path |
| `POST` | `/api/worlds` | Batch generation (up to `TRAVELLER_MAX_BATCH_SIZE` worlds) |
| `GET` | `/api/world/{name}/card` | Standalone HTML display card |

**System endpoints** — WBH stellar + orbit + CRB mainworld.

| Method | Route | Description |
|--------|-------|-------------|
| `GET/POST` | `/api/system` | Generate a full star system |
| `GET` | `/api/system/{name}` | Generate a full star system; name from URL path |
| `GET` | `/api/system/{name}/card` | Standalone HTML system card |
| `GET/POST` | `/api/system/full` | Complete system — all secondary worlds and moons; detail always on |
| `POST` | `/api/system/from-world` | Full system around an existing mainworld JSON; UWP and PBG preserved |

**TravellerMap endpoints** — canonical UWP + procedural orbital structure.

| Method | Route | Description |
|--------|-------|-------------|
| `GET/POST` | `/api/map/system` | Fetch world from TravellerMap, generate full system |
| `GET` | `/api/map/system/{name}` | World name from URL path; `sector` still required as query param |
| `GET/POST` | `/api/map/system/full` | TravellerMap fetch + full detail pipeline |
| `GET` | `/api/map/system/svg` | TravellerMap fetch + SVG system map |

**Utility endpoints**

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/version` | Returns `{"version": "1.5.27+build.N"}` |
| `GET` | `/` | Web UI (HTML) |

---

### Parameters

#### Common parameters

| Parameter | Endpoints | Type | Description |
|-----------|-----------|------|-------------|
| `name` | All except `/worlds` | string | World name (max 64 chars). Defaults to `World-1`. |
| `seed` | All | integer | RNG seed for deterministic output. Omit for a random result. |

#### Mainworld-only parameters

| Parameter | Endpoint | Type | Description |
|-----------|----------|------|-------------|
| `count` | `/worlds` | integer | Worlds to generate (1–`TRAVELLER_MAX_BATCH_SIZE`, default 1). |
| `prefix` | `/worlds` | string | Name prefix, e.g. `Spinward-` → `Spinward-1`, `Spinward-2`, … (max 32 chars). |

#### System parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `detail` | `false` | Attach secondary world SAH/social profiles and satellite data. Adds ~10–50 ms. |
| `runaway_greenhouse` | `false` | Apply the optional runaway greenhouse check (WBH p.79). May override atmosphere, temperature, and hydrographics. |
| `independent_government` | `false` | Secondary worlds use Case 2 government when `detail=true`. |
| `optional_biomass_rule` | `false` | Raise oxygenated biomass 0→1 when `detail=true` (WBH p.131). |
| `optional_inhospitable_rule` | `false` | Roll once for all non-HZ secondaries; only a natural 12 grants a biomass roll. |
| `format` | `json` | Output format for endpoints that support it: `json`, `html`, or `text`. |
| `orbital_eccentricity` | `false` | Include orbital eccentricity in generation. |
| `orbital_inclination` | `false` | Include orbital inclination in generation. |

#### TravellerMap parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `sector` | **Always** | Sector name, e.g. `Spinward Marches`. Required on all `/api/map/*` endpoints. |
| `name` | One of name/hex | World name to search. |
| `hex` | One of name/hex | 4-digit hex position, e.g. `1910`. |

**Accepted boolean values:** `true`, `1`, `yes` (case-insensitive) or JSON `true`.

**Parameter priority** (highest to lowest): URL path → query string → JSON body.

---

### Example requests

```bash
BASE="https://traveller-world-gen.azurewebsites.net"
# Omit ?code= if auth level is ANONYMOUS (the default)

# Mainworld
curl "$BASE/api/world?name=Cogri&seed=42"
curl "$BASE/api/world/Mora?seed=7"
curl "$BASE/api/world/Jae-Tellona/card" -o world.html
curl -X POST "$BASE/api/worlds" \
     -H "Content-Type: application/json" \
     -d '{"count": 5, "prefix": "Spinward-", "seed": 1}'

# System — orbital structure only
curl "$BASE/api/system?name=Ardenne&seed=1000"
curl "$BASE/api/system/Mora?seed=7"

# System — with secondary world and satellite detail
curl "$BASE/api/system?name=Ardenne&seed=1000&detail=true"
curl -X POST "$BASE/api/system" \
     -H "Content-Type: application/json" \
     -d '{"name": "Varanthos", "seed": 6056, "detail": true}'

# Complete system — always includes all worlds and moons
curl "$BASE/api/system/full?name=Ardenne&seed=1000"
curl "$BASE/api/system/full?name=Ardenne&seed=1000&format=html" -o ardenne-full.html
curl "$BASE/api/system/full?name=Ardenne&seed=1000&format=text"

# TravellerMap — canonical UWP + procedural orbital structure (sector always required)
curl "$BASE/api/map/system?name=Regina&sector=Spinward+Marches&seed=42"
curl "$BASE/api/map/system/Mora?sector=Spinward+Marches&seed=7&detail=true"
curl "$BASE/api/map/system?sector=Spinward+Marches&hex=1910&format=html" -o regina.html

# System from existing mainworld — UWP/PBG preserved
WORLD=$(curl -s "$BASE/api/world?name=Cogri&seed=42")
curl -X POST "$BASE/api/system/from-world?seed=99" \
     -H "Content-Type: application/json" \
     -d "$WORLD"

# Version check
curl "$BASE/api/version"
```

```powershell
$BASE = "https://traveller-world-gen.azurewebsites.net"

# Mainworld
Invoke-RestMethod "$BASE/api/world?name=Cogri&seed=42"
Invoke-RestMethod "$BASE/api/world/Mora?seed=7"
Invoke-WebRequest "$BASE/api/world/Jae-Tellona/card" -OutFile world.html
Invoke-RestMethod -Method Post "$BASE/api/worlds" `
    -ContentType "application/json" `
    -Body '{"count": 5, "prefix": "Spinward-", "seed": 1}'

# System
Invoke-RestMethod "$BASE/api/system?name=Ardenne&seed=1000&detail=true"
Invoke-WebRequest "$BASE/api/system/full?name=Ardenne&seed=1000&format=html" `
    -OutFile ardenne-full.html

# TravellerMap
Invoke-RestMethod "$BASE/api/map/system?name=Regina&sector=Spinward+Marches&seed=42"
Invoke-WebRequest "$BASE/api/map/system?sector=Spinward+Marches&hex=1910&format=html" `
    -OutFile regina.html

# System from existing mainworld
$world = Invoke-RestMethod "$BASE/api/world?name=Cogri&seed=42"
Invoke-RestMethod -Method Post "$BASE/api/system/from-world?seed=99" `
    -ContentType "application/json" `
    -Body ($world | ConvertTo-Json -Depth 10)
```

---

## 11. Error responses

All error responses use `Content-Type: application/json`:

```json
{
  "error": {
    "code": "INVALID_SEED",
    "message": "'seed' must be an integer, got 'abc'."
  }
}
```

| Code | HTTP | Trigger |
|------|------|---------|
| `INVALID_SEED` | 400 | `seed` is not a valid integer |
| `INVALID_COUNT` | 400 | `count` is not a positive integer |
| `COUNT_TOO_LARGE` | 422 | `count` exceeds `TRAVELLER_MAX_BATCH_SIZE` |
| `INVALID_BODY` | 400 | Request body is not valid JSON or a field is invalid |
| `INVALID_HEX` | 400 | `hex` is not a valid 4-digit hex position (map endpoints only) |
| `NAME_TOO_LONG` | 400 | World name exceeds 64 characters |
| `MISSING_PARAM` | 400 | `sector` is absent (map endpoints only) |
| `NOT_FOUND` | 404 | World not found on TravellerMap (map endpoints only) |
| `UPSTREAM_ERROR` | 502 | TravellerMap unreachable or returned an error (map endpoints only) |
| `INTERNAL_ERROR` | 500 | Unexpected server-side failure |
