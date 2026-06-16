#Requires -Version 5.1
<#
.SYNOPSIS
    Start the Traveller World Generator FastAPI server.

.DESCRIPTION
    Starts uvicorn serving app:app from the fastapi/ subdirectory.
    The server listens on http://localhost:8000 by default.

    Any extra arguments are forwarded to uvicorn, for example:
        .\run-fastapi.ps1 --host 0.0.0.0 --port 8080
        .\run-fastapi.ps1 --reload

.EXAMPLE
    .\run-fastapi.ps1

.EXAMPLE
    .\run-fastapi.ps1 --host 0.0.0.0 --port 8080
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Uvicorn   = Join-Path $ScriptDir '.venv\Scripts\uvicorn.exe'
$FastApiDir = Join-Path $ScriptDir 'fastapi'

if (-not (Test-Path $Uvicorn)) {
    Write-Host "[error] uvicorn not found at $Uvicorn" -ForegroundColor Red
    Write-Host "        Run install.ps1 first to create the virtual environment." -ForegroundColor Yellow
    exit 1
}

Set-Location $FastApiDir
& $Uvicorn app:app --host 127.0.0.1 --port 8000 @args
