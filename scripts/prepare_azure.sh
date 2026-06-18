#!/usr/bin/env bash
# Copies generator modules and shared resources into azure-api/ for local
# Azure Functions development (func start).  Mirrors what the CI deploy
# workflow does before publishing.
#
# Usage: bash scripts/prepare_azure.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$REPO_ROOT/azure-api"

echo "Computing version ..."
bash "$REPO_ROOT/scripts/compute_version.sh"

echo "Copying generator modules to $DEST ..."
cp \
  "$REPO_ROOT/_version.py" \
  "$REPO_ROOT/html_render.py" \
  "$REPO_ROOT/system_map.py" \
  "$REPO_ROOT/system_pipeline.py" \
  "$REPO_ROOT/tables.py" \
  "$REPO_ROOT/traveller_belt_physical.py" \
  "$REPO_ROOT/traveller_hydro_detail.py" \
  "$REPO_ROOT/traveller_map_fetch.py" \
  "$REPO_ROOT/traveller_moon_gen.py" \
  "$REPO_ROOT/traveller_orbit_gen.py" \
  "$REPO_ROOT/traveller_stellar_gen.py" \
  "$REPO_ROOT/traveller_system_gen.py" \
  "$REPO_ROOT/traveller_world_atmosphere_detail.py" \
  "$REPO_ROOT/traveller_world_detail.py" \
  "$REPO_ROOT/traveller_world_gen.py" \
  "$REPO_ROOT/traveller_world_government_detail.py" \
  "$REPO_ROOT/traveller_world_law_detail.py" \
  "$REPO_ROOT/traveller_world_physical.py" \
  "$REPO_ROOT/traveller_world_population_detail.py" \
  "$REPO_ROOT/traveller_world_schema.json" \
  "$REPO_ROOT/traveller_world_tech_detail.py" \
  "$REPO_ROOT/traveller_world_culture_detail.py" \
  "$REPO_ROOT/traveller_world_importance.py" \
  "$REPO_ROOT/world_codes.py" \
  "$DEST/"

echo "Copying fastapi/ ..."
rm -rf "$DEST/fastapi"
cp -r "$REPO_ROOT/fastapi" "$DEST/fastapi"

echo "Copying templates/ ..."
rm -rf "$DEST/templates"
cp -r "$REPO_ROOT/templates" "$DEST/templates"

echo "Done.  Run: cd azure-api && func start"
