#!/usr/bin/env bash
# Start the Traveller World Generator FastAPI server.
#
# The server listens on http://localhost:8000 by default.
#
# Options (passed through to uvicorn):
#   --host HOST   Bind address (default: 127.0.0.1)
#   --port PORT   Port number   (default: 8000)
#   --reload      Auto-reload on source changes (development only)
#
# Examples:
#   bash run-fastapi.sh
#   bash run-fastapi.sh --host 0.0.0.0 --port 8080
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/fastapi"
exec "$SCRIPT_DIR/.venv/bin/uvicorn" app:app --host 127.0.0.1 --port 8000 "$@"
