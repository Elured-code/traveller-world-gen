"""
function_app.py
===============
Traveller World & System Generator — Azure Functions HTTP API (ASGI)

Wraps the FastAPI app from fastapi/app.py using AsgiFunctionApp so that
all FastAPI routes are served directly by Azure Functions.  The FastAPI
app is the authoritative implementation; this file is purely the adapter.

Authentication
--------------
Auth level is FUNCTION — callers must supply a function key via:
  ?code=<key>   or   x-functions-key: <key>

The full endpoint list is defined in fastapi/app.py.  See context/api-layer.md
for parameter reference and error codes.

Deployment
----------
The generator modules (traveller_*.py, html_render.py, etc.) and the
fastapi/ and templates/ directories must be present alongside this file.
The GitHub Actions workflow (.github/workflows/azure-deploy.yml) copies
them in from the repo root before publishing.

For local development, run scripts/prepare_azure.sh first, then:
  cd azure-api && func start
"""

import os
import sys

# fastapi/app.py imports 'helpers' as a top-level name (not 'fastapi.helpers').
# Insert fastapi/ onto sys.path to mirror PYTHONPATH=/app/fastapi in Docker.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "fastapi"))

import azure.functions as func  # pylint: disable=wrong-import-order
import app as _fastapi_module   # resolves to azure-api/fastapi/app.py  # pylint: disable=wrong-import-order

func_app = func.AsgiFunctionApp(
    app=_fastapi_module.app,
    http_auth_level=func.AuthLevel.ANONYMOUS,
)
