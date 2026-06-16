@echo off
rem Start the Traveller World Generator FastAPI server.
rem
rem The server listens on http://localhost:8000 by default.
rem
rem Options (passed through to uvicorn):
rem   --host HOST   Bind address (default: 127.0.0.1)
rem   --port PORT   Port number   (default: 8000)
rem   --reload      Auto-reload on source changes (development only)
rem
rem Examples:
rem   run-fastapi
rem   run-fastapi --host 0.0.0.0 --port 8080
cd /d "%~dp0fastapi"
"%~dp0.venv\Scripts\uvicorn.exe" app:app --host 127.0.0.1 --port 8000 %*
