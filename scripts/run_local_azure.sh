#!/usr/bin/env bash
# Run the Azure Functions app locally using Azure Functions Core Tools.
#
# Steps:
#   1. Sync generator modules from the repo root into azure-api/ (prepare_azure.sh)
#   2. Install Python dependencies into azure-api/.python_packages/ if needed
#   3. Start func host in azure-api/
#
# Prerequisites:
#   - Azure Functions Core Tools v4  (brew install azure-functions-core-tools@4)
#   - Python 3.11 on PATH
#
# Usage:
#   bash scripts/run_local_azure.sh [--no-sync] [--port <port>]
#
#   --no-sync  Skip the prepare_azure.sh sync step (use when modules are
#              already up-to-date to speed up startup).
#   --port N   Bind to port N instead of the default (7071).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AZURE_DIR="$REPO_ROOT/azure-api"
SYNC=true
PORT=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-sync) SYNC=false; shift ;;
        --port)    PORT="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# Step 1 — sync modules
if $SYNC; then
    echo "==> Syncing modules to azure-api/ ..."
    bash "$REPO_ROOT/scripts/prepare_azure.sh"
else
    echo "==> Skipping module sync (--no-sync)"
fi

# Step 2 — install Python dependencies if requirements.txt is newer than the
# marker file, or if .python_packages/ doesn't exist yet.
PKGS="$AZURE_DIR/.python_packages/lib/site-packages"
MARKER="$AZURE_DIR/.python_packages/.installed_at"
REQ="$AZURE_DIR/requirements.txt"

if [[ ! -d "$PKGS" ]] || [[ "$REQ" -nt "$MARKER" ]]; then
    echo "==> Installing Python dependencies ..."
    pip install \
        --target "$PKGS" \
        --upgrade \
        -r "$REQ"
    touch "$MARKER"
else
    echo "==> Python dependencies up-to-date (use 'rm -rf $PKGS' to force reinstall)"
fi

# Step 3 — start the Functions host
echo "==> Starting Azure Functions host in $AZURE_DIR ..."
cd "$AZURE_DIR"
if [[ -n "$PORT" ]]; then
    func start --port "$PORT"
else
    func start
fi
