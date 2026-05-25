#Requires -Version 5.1
<#
.SYNOPSIS
    Traveller World Generator - Quick Install (Windows)

.DESCRIPTION
    Creates a Python virtual environment, installs the GUI library (PySide6),
    and generates batch-file launchers for the desktop app and command-line tools.

    Requirements: Python 3.9 or later
    Download from: https://www.python.org/downloads/
    (Tick "Add Python to PATH" during installation.)

.EXAMPLE
    .\install.ps1

    If you see an execution-policy error, first run:
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    then re-run .\install.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info { param([string]$Msg) Write-Host "[install] $Msg" -ForegroundColor Green }
function Warn { param([string]$Msg) Write-Host "[warning] $Msg" -ForegroundColor Yellow }
function Fail { param([string]$Msg) Write-Host "[error]   $Msg" -ForegroundColor Red; exit 1 }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "Traveller World Generator - Installation" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Locate Python 3.9+
Info "Checking Python..."

$Python = $null
$PyVer  = $null

foreach ($cmd in @('python', 'python3', 'py')) {
    try {
        $output = & $cmd --version 2>&1
        if ($output -match 'Python (\d+)\.(\d+)') {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 9)) {
                $Python = $cmd
                $PyVer  = "$major.$minor"
                break
            }
        }
    } catch { continue }
}

if (-not $Python) {
    Warn "Python 3.9 or later was not found."
    Info "Attempting to install Python 3.11 via winget..."

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail ("winget is not available on this system.`n" +
              "         Download Python 3.11 from: https://www.python.org/downloads/`n" +
              "         Tick 'Add Python to PATH' during installation, then re-run this script.")
    }

    & winget install --id Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Fail ("winget failed to install Python.`n" +
              "         Download Python 3.11 from: https://www.python.org/downloads/`n" +
              "         Tick 'Add Python to PATH' during installation, then re-run this script.")
    }

    Info "Python installed. Refreshing PATH..."
    $machinePath   = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath      = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path      = "$machinePath;$userPath"

    foreach ($cmd in @('python', 'python3', 'py')) {
        try {
            $output = & $cmd --version 2>&1
            if ($output -match 'Python (\d+)\.(\d+)') {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 9)) {
                    $Python = $cmd
                    $PyVer  = "$major.$minor"
                    break
                }
            }
        } catch { continue }
    }

    if (-not $Python) {
        Fail ("Python was installed but cannot be found yet.`n" +
              "         Close this window, open a new PowerShell, and re-run install.ps1")
    }
}

Info "Found Python $PyVer  ($Python)"

# 2. Create virtual environment
$VenvDir = Join-Path $ScriptDir '.venv'

if (Test-Path $VenvDir) {
    Info "Virtual environment already exists - will update packages."
} else {
    Info "Creating virtual environment in .venv\ ..."
    & $Python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Fail "Could not create virtual environment." }
}

$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Fail "Python was not found in the virtual environment. Try deleting .venv\ and re-running."
}

# 3. Install dependencies
Info "Upgrading pip..."
& $VenvPython -m pip install --quiet --upgrade pip
if ($LASTEXITCODE -ne 0) { Fail "Failed to upgrade pip." }

Info "Installing backend dependencies (azure-functions, jsonschema)..."
& $VenvPython -m pip install --quiet -r (Join-Path $ScriptDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Fail "Failed to install backend dependencies." }

Info "Installing PySide6 (desktop GUI library) - this may take a few minutes..."
& $VenvPython -m pip install --quiet -r (Join-Path $ScriptDir 'gen-ui\requirements.txt')
if ($LASTEXITCODE -ne 0) {
    Fail "Failed to install PySide6. Check your internet connection and try again."
}


Info "Installing dev tools (pytest, pylint)..."
& $VenvPython -m pip install --quiet -r (Join-Path $ScriptDir 'requirements-dev.txt')
if ($LASTEXITCODE -ne 0) { Fail "Failed to install dev tools." }
Info "All dependencies installed."

# 4. Create VS Code settings
$VscodeDir     = Join-Path $ScriptDir '.vscode'
$VscodeSettings = Join-Path $VscodeDir 'settings.json'
if (-not (Test-Path $VscodeSettings)) {
    Info "Creating VS Code settings (.vscode\settings.json)..."
    if (-not (Test-Path $VscodeDir)) { New-Item -ItemType Directory $VscodeDir | Out-Null }
    @'
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe",
  "python.terminal.activateEnvironment": true,
  "python.terminal.activateEnvInCurrentTerminal": true,
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": [
    "tests"
  ],
  "python.testing.unittestEnabled": false,
  "python.analysis.venvPath": "${workspaceFolder}",
  "python.analysis.venv": ".venv",
  "python.analysis.extraPaths": [
    "${workspaceFolder}"
  ],
  "python.analysis.typeCheckingMode": "basic",
  "editor.formatOnSave": true,
  "editor.rulers": [
    88
  ],
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".pytest_cache": true
  },
  "[python]": {
    "editor.defaultFormatter": "ms-python.python"
  },
  "azureFunctions.deploySubpath": ".",
  "azureFunctions.scmDoBuildDuringDeployment": true,
  "azureFunctions.pythonVenv": ".venv",
  "azureFunctions.projectLanguage": "Python",
  "azureFunctions.projectRuntime": "~4",
  "debug.internalConsoleOptions": "neverOpen",
  "azureFunctions.projectLanguageModel": 2,
  "pylint.path": [
    "${workspaceFolder}/.venv/Scripts/pylint.exe"
  ],
  "pylint.interpreter": [
    "${workspaceFolder}/.venv/Scripts/python.exe"
  ],
  "pylint.args": [
    "--disable=duplicate-code,too-many-lines"
  ]
}
'@ | Set-Content $VscodeSettings -Encoding utf8
} else {
    Info "VS Code settings already exist - skipping."
}

# 5. Create launcher batch files
Info "Creating launcher scripts..."

# Desktop GUI
$guiBat = @'
@echo off
"%~dp0.venv\Scripts\python.exe" "%~dp0gen-ui\app.py"
'@
$guiBat | Set-Content (Join-Path $ScriptDir 'run-gui.bat') -Encoding ASCII

# World generator CLI
$worldBat = @'
@echo off
rem Generate one or more Traveller mainworlds.
rem
rem Options:
rem   --name NAME       World name (default: auto-numbered)
rem   --count N         Number of worlds to generate (default: 1)
rem   --seed N          RNG seed for reproducible results
rem   --json            Output as JSON instead of text
rem   --html            Output as an HTML card
rem
rem Examples:
rem   run-world
rem   run-world --name "New Terra" --count 3
rem   run-world --name Zhodane --seed 42 --json
"%~dp0.venv\Scripts\python.exe" "%~dp0traveller_world_gen.py" %*
'@
$worldBat | Set-Content (Join-Path $ScriptDir 'run-world.bat') -Encoding ASCII

# TravellerMap lookup CLI
$mapBat = @'
@echo off
rem Fetch a world from TravellerMap and generate a full star system.
rem Requires an internet connection.
rem
rem Options (--sector is always required):
rem   --sector SECTOR   Sector name, e.g. "Spinward Marches"
rem   --name NAME       World name within the sector
rem   --hex NNNN        4-digit hex position (alternative to --name)
rem   --seed N          RNG seed for reproducible results
rem   --detail          Include secondary world and moon profiles
rem   --json            Output as JSON
rem   --html            Output as an HTML card
rem
rem Examples:
rem   run-mapfetch --sector "Spinward Marches" --name Regina
rem   run-mapfetch --sector "Spinward Marches" --hex 1910 --detail
"%~dp0.venv\Scripts\python.exe" "%~dp0traveller_map_fetch.py" %*
'@
$mapBat | Set-Content (Join-Path $ScriptDir 'run-mapfetch.bat') -Encoding ASCII

# 6. Activate virtual environment
if ($env:VIRTUAL_ENV -ne $VenvDir) {
    Info "Activating virtual environment..."
    & "$VenvDir\Scripts\Activate.ps1"
} else {
    Info "Virtual environment already active."
}

# 7. Done
Write-Host ""
Info "Installation complete!"
Write-Host ""
Write-Host "  +----------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host "  |  Desktop app                                                   |" -ForegroundColor Cyan
Write-Host "  |    Double-click  run-gui.bat  in File Explorer                 |" -ForegroundColor Cyan
Write-Host "  |    or run from this window:  .\run-gui.bat                     |" -ForegroundColor Cyan
Write-Host "  |                                                                |" -ForegroundColor Cyan
Write-Host "  |  World generator (command line)                                |" -ForegroundColor Cyan
Write-Host "  |    run-world [--name NAME] [--count N] [--seed N]              |" -ForegroundColor Cyan
Write-Host "  |                                                                |" -ForegroundColor Cyan
Write-Host "  |  TravellerMap lookup (command line, needs internet)            |" -ForegroundColor Cyan
Write-Host "  |    run-mapfetch --sector SECTOR --name NAME                    |" -ForegroundColor Cyan
Write-Host "  +----------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Examples:" -ForegroundColor White
Write-Host "    .\run-world.bat" -ForegroundColor White
Write-Host '    .\run-world.bat --name "New Terra" --count 5' -ForegroundColor White
Write-Host '    .\run-mapfetch.bat --sector "Spinward Marches" --name Regina' -ForegroundColor White
Write-Host ""
Write-Host "  To activate the venv in a new terminal:" -ForegroundColor Yellow
Write-Host '    . .\install.ps1          # dot-source to activate in this session' -ForegroundColor Yellow
Write-Host '    # or manually:' -ForegroundColor Yellow
Write-Host '    .\.venv\Scripts\Activate.ps1' -ForegroundColor Yellow
Write-Host ""
