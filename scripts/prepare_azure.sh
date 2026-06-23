#!/usr/bin/env bash
# Assembles the azure-api/ deployment directory for local Azure Functions
# development (func start) and CI deploys.
#
# Previously: manually copied individual .py files (error-prone, required
# updating whenever a new module was added).
#
# Now: installs the traveller-gen package via pip --target so azure-api/
# receives a proper traveller_gen/ package directory.  Templates and the JSON
# schema are included as package data — no separate copy step needed.
#
# Usage: bash scripts/prepare_azure.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$REPO_ROOT/azure-api"

echo "Computing version ..."
bash "$REPO_ROOT/scripts/compute_version.sh"

echo "Installing traveller-gen package into $DEST ..."
"$REPO_ROOT/.venv/bin/pip" install \
  --quiet \
  --target "$DEST" \
  --no-deps \
  "$REPO_ROOT"

echo "Copying fastapi/ ..."
rm -rf "$DEST/fastapi"
cp -r "$REPO_ROOT/fastapi" "$DEST/fastapi"

echo "Done.  Run: cd azure-api && func start"
