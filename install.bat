@echo off
setlocal enabledelayedexpansion

echo.
echo Traveller World Generator - Installation
echo =========================================
echo.

rem -- 1. Locate Python 3.9+ ----------------------------------------------------

echo [install] Checking Python...

set PYTHON=
set PY_VER=

rem Try the py launcher with specific versions first (most reliable on Windows)
for %%V in (3.13 3.12 3.11 3.10 3.9) do (
    if "!PYTHON!"=="" (
        py -%%V --version >nul 2>&1
        if not errorlevel 1 (
            set PYTHON=py -%%V
            set PY_VER=%%V
        )
    )
)

rem Fall back to python / python3 commands and verify version
if "!PYTHON!"=="" (
    for %%C in (python python3) do (
        if "!PYTHON!"=="" (
            %%C -c "import sys; exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>&1
            if not errorlevel 1 (
                set PYTHON=%%C
                for /f "tokens=2" %%V in ('%%C --version 2^>^&1') do set PY_VER=%%V
            )
        )
    )
)

if not "!PYTHON!"=="" goto :python_found

rem -- Python not found: try winget install ------------------------------------

echo [warning] Python 3.9 or later was not found.
echo [install] Attempting to install Python 3.11 via winget...

winget --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [error]   winget is not available on this system.
    echo           Download Python 3.11 from: https://www.python.org/downloads/
    echo           Tick "Add Python to PATH", complete the install, then re-run install.bat
    exit /b 1
)

winget install --id Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
    echo [error]   winget failed to install Python.
    echo           Download Python 3.11 from: https://www.python.org/downloads/
    exit /b 1
)

echo [install] Python installed. Refreshing PATH...

rem Merge system and user PATH from registry so the new install is visible
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USR_PATH=%%B"
set "PATH=!SYS_PATH!;!USR_PATH!"

rem Re-check after install
for %%V in (3.13 3.12 3.11 3.10 3.9) do (
    if "!PYTHON!"=="" (
        py -%%V --version >nul 2>&1
        if not errorlevel 1 (
            set PYTHON=py -%%V
            set PY_VER=%%V
        )
    )
)

if "!PYTHON!"=="" (
    echo [error]   Python was installed but cannot be found yet.
    echo           Close this window, open a new Command Prompt, and re-run install.bat
    exit /b 1
)

:python_found
echo [install] Found Python !PY_VER!  ^(!PYTHON!^)

rem -- 2. Create virtual environment --------------------------------------------

set VENV_DIR=%~dp0.venv
set VENV_PYTHON=%~dp0.venv\Scripts\python.exe

if exist "!VENV_DIR!\" (
    echo [install] Virtual environment already exists - will update packages.
) else (
    echo [install] Creating virtual environment in .venv\ ...
    !PYTHON! -m venv "!VENV_DIR!"
    if errorlevel 1 (
        echo [error]   Could not create virtual environment.
        exit /b 1
    )
)

if not exist "!VENV_PYTHON!" (
    echo [error]   Python not found in the virtual environment.
    echo           Delete the .venv folder and re-run install.bat
    exit /b 1
)

rem -- 3. Install PySide6 -------------------------------------------------------

echo [install] Upgrading pip...
"!VENV_PYTHON!" -m pip install --quiet --upgrade pip
if errorlevel 1 (
    echo [error]   Failed to upgrade pip.
    exit /b 1
)

echo [install] Installing PySide6 (desktop GUI library) - this may take a few minutes...
"!VENV_PYTHON!" -m pip install --quiet "PySide6>=6.4.0"
if errorlevel 1 (
    echo [error]   Failed to install PySide6. Check your internet connection and try again.
    exit /b 1
)
echo [install] PySide6 installed.

rem -- 4. Create launcher batch files -------------------------------------------

echo [install] Creating launcher scripts...

(
    echo @echo off
    echo "%%~dp0.venv\Scripts\python.exe" "%%~dp0gen-ui\app.py"
) > "%~dp0run-gui.bat"

(
    echo @echo off
    echo rem Generate one or more Traveller mainworlds.
    echo rem Options:
    echo rem   --name NAME    World name ^(default: auto-numbered^)
    echo rem   --count N      Number of worlds to generate ^(default: 1^)
    echo rem   --seed N       RNG seed for reproducible results
    echo rem   --json         Output as JSON instead of text
    echo rem   --html         Output as an HTML card
    echo "%%~dp0.venv\Scripts\python.exe" "%%~dp0traveller_world_gen.py" %%*
) > "%~dp0run-world.bat"

(
    echo @echo off
    echo rem Fetch a world from TravellerMap and generate a full star system.
    echo rem Requires an internet connection. --sector is always required.
    echo rem Options:
    echo rem   --sector SECTOR  Sector name, e.g. "Spinward Marches"
    echo rem   --name NAME      World name within the sector
    echo rem   --hex NNNN       4-digit hex position ^(alternative to --name^)
    echo rem   --seed N         RNG seed
    echo rem   --detail         Include secondary world and moon profiles
    echo rem   --json           Output as JSON
    echo rem   --html           Output as an HTML card
    echo "%%~dp0.venv\Scripts\python.exe" "%%~dp0traveller_map_fetch.py" %%*
) > "%~dp0run-mapfetch.bat"

rem -- 5. Done ------------------------------------------------------------------

echo.
echo [install] Installation complete!
echo.
echo   +------------------------------------------------------------------+
echo   ^|  Desktop app                                                     ^|
echo   ^|    Double-click  run-gui.bat  in File Explorer                   ^|
echo   ^|    or run from this window:  run-gui.bat                         ^|
echo   ^|                                                                  ^|
echo   ^|  World generator  ^(command line^)                                 ^|
echo   ^|    run-world [--name NAME] [--count N] [--seed N]                ^|
echo   ^|                                                                  ^|
echo   ^|  TravellerMap lookup  ^(command line, needs internet^)              ^|
echo   ^|    run-mapfetch --sector SECTOR --name NAME                      ^|
echo   +------------------------------------------------------------------+
echo.
echo   Examples:
echo     run-world
echo     run-world --name "New Terra" --count 5
echo     run-mapfetch --sector "Spinward Marches" --name Regina
echo.

endlocal
