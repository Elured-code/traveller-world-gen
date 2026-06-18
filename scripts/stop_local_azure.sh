#!/usr/bin/env bash
# Stop a locally running Azure Functions host started by run_local_azure.sh.
#
# The func host spawns a Python worker child process.  Sending SIGTERM to
# the parent alone leaves the worker running and blocks a clean exit, so
# this script kills the entire process group via SIGTERM then SIGKILL.
#
# Usage:
#   bash scripts/stop_local_azure.sh [--port <port>]
#
#   --port N   Only stop the func process listening on port N (default: any func process).

set -euo pipefail

TIMEOUT=8
PORT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) PORT="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# ── Find the func host PID ────────────────────────────────────────────────────
if [[ -n "$PORT" ]]; then
    PID=$(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -z "$PID" ]]; then
        echo "No process listening on port $PORT."
        exit 0
    fi
    PROC_NAME=$(ps -p "$PID" -o comm= 2>/dev/null || true)
    if [[ "$PROC_NAME" != *func* && "$PROC_NAME" != *dotnet* ]]; then
        echo "Process on port $PORT (PID $PID, '$PROC_NAME') does not look like a func host — aborting."
        exit 1
    fi
else
    PID=$(pgrep -x func 2>/dev/null || true)
    if [[ -z "$PID" ]]; then
        echo "No func host process found."
        exit 0
    fi
fi

echo "Stopping func host (PID $PID) ..."

# ── Kill the process group so the Python worker child exits too ───────────────
PGID=$(ps -o pgid= -p "$PID" 2>/dev/null | tr -d ' ' || true)
if [[ -n "$PGID" && "$PGID" != "0" ]]; then
    kill -TERM -"$PGID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null || true
else
    kill -TERM "$PID" 2>/dev/null || true
fi

# Wait for the main process to exit.
ELAPSED=0
while kill -0 "$PID" 2>/dev/null; do
    if [[ $ELAPSED -ge $TIMEOUT ]]; then
        echo "Process group did not exit after ${TIMEOUT}s — sending SIGKILL."
        if [[ -n "$PGID" && "$PGID" != "0" ]]; then
            kill -KILL -"$PGID" 2>/dev/null || kill -KILL "$PID" 2>/dev/null || true
        else
            kill -KILL "$PID" 2>/dev/null || true
        fi
        break
    fi
    sleep 1
    ELAPSED=$(( ELAPSED + 1 ))
done

echo "func host stopped."
