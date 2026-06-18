#Requires -Version 5.1
<#
.SYNOPSIS
    Run the Azure Functions app locally using Azure Functions Core Tools.

.DESCRIPTION
    Steps:
      1. Sync generator modules from repo root into azure-api/ (prepare_azure.ps1)
      2. Install Python dependencies into azure-api/.python_packages/ if needed
      3. Start func host in azure-api/

    Prerequisites:
      - Azure Functions Core Tools v4  (winget install Microsoft.Azure.FunctionsCoreTools)
      - Python 3.11 on PATH

.PARAMETER NoSync
    Skip the prepare_azure.ps1 sync step (use when modules are already up-to-date).

.PARAMETER Port
    Bind the func host to this port instead of the default (7071).

.EXAMPLE
    .\scripts\run_local_azure.ps1

.EXAMPLE
    .\scripts\run_local_azure.ps1 -NoSync -Port 7072
#>

param(
    [switch]$NoSync,
    [int]$Port = 0
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir
$AzureDir  = Join-Path $RepoRoot 'azure-api'

# Step 1 — sync modules
if (-not $NoSync) {
    Write-Host "==> Syncing modules to azure-api/ ..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptDir 'prepare_azure.ps1')
} else {
    Write-Host "==> Skipping module sync (-NoSync)"
}

# Step 2 — install Python dependencies if requirements.txt is newer than the marker
$Pkgs   = Join-Path $AzureDir '.python_packages\lib\site-packages'
$Marker = Join-Path $AzureDir '.python_packages\.installed_at'
$Req    = Join-Path $AzureDir 'requirements.txt'

$NeedsInstall = (-not (Test-Path $Pkgs))
if (-not $NeedsInstall -and (Test-Path $Marker)) {
    $NeedsInstall = (Get-Item $Req).LastWriteTime -gt (Get-Item $Marker).LastWriteTime
} elseif (-not (Test-Path $Marker)) {
    $NeedsInstall = $true
}

if ($NeedsInstall) {
    Write-Host "==> Installing Python dependencies ..."
    pip install --target $Pkgs --upgrade -r $Req
    New-Item $Marker -ItemType File -Force | Out-Null
} else {
    Write-Host "==> Python dependencies up-to-date (delete '$Pkgs' to force reinstall)"
}

# Step 3 — start the Functions host
Write-Host "==> Starting Azure Functions host in $AzureDir ..."
Set-Location $AzureDir
if ($Port -gt 0) {
    func start --port $Port
} else {
    func start
}
