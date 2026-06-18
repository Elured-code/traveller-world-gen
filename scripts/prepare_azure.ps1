#Requires -Version 5.1
<#
.SYNOPSIS
    Copy generator modules into azure-api/ for local Azure Functions development.

.DESCRIPTION
    Mirrors what the CI deploy workflow does before publishing.
    Run this before 'func start' to ensure azure-api/ is up-to-date.

.EXAMPLE
    .\scripts\prepare_azure.ps1
#>

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir
$Dest      = Join-Path $RepoRoot 'azure-api'

Write-Host "Computing version ..."
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptDir 'compute_version.ps1')

Write-Host "Copying generator modules to $Dest ..."
$Modules = @(
    '_version.py',
    'html_render.py',
    'system_map.py',
    'system_pipeline.py',
    'tables.py',
    'traveller_belt_physical.py',
    'traveller_hydro_detail.py',
    'traveller_map_fetch.py',
    'traveller_moon_gen.py',
    'traveller_orbit_gen.py',
    'traveller_stellar_gen.py',
    'traveller_system_gen.py',
    'traveller_world_atmosphere_detail.py',
    'traveller_world_culture_detail.py',
    'traveller_world_detail.py',
    'traveller_world_gen.py',
    'traveller_world_government_detail.py',
    'traveller_world_importance.py',
    'traveller_world_law_detail.py',
    'traveller_world_physical.py',
    'traveller_world_population_detail.py',
    'traveller_world_schema.json',
    'traveller_world_tech_detail.py',
    'world_codes.py'
)
foreach ($Module in $Modules) {
    Copy-Item (Join-Path $RepoRoot $Module) $Dest -Force
}

Write-Host "Copying fastapi/ ..."
$FastApiDest = Join-Path $Dest 'fastapi'
if (Test-Path $FastApiDest) { Remove-Item $FastApiDest -Recurse -Force }
Copy-Item (Join-Path $RepoRoot 'fastapi') $FastApiDest -Recurse

Write-Host "Copying templates/ ..."
$TemplatesDest = Join-Path $Dest 'templates'
if (Test-Path $TemplatesDest) { Remove-Item $TemplatesDest -Recurse -Force }
Copy-Item (Join-Path $RepoRoot 'templates') $TemplatesDest -Recurse

Write-Host "Done.  Run: Set-Location azure-api; func start"
