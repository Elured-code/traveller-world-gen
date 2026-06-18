#Requires -Version 5.1
<#
.SYNOPSIS
    Stop a locally running Azure Functions host.

.DESCRIPTION
    Terminates the func host process and its Python worker child by stopping
    the full process tree.  Waits up to 8 seconds for a clean exit before
    force-killing.

.PARAMETER Port
    Only stop the func process listening on this port.
    Without this parameter, the first 'func' process found is stopped.

.EXAMPLE
    .\scripts\stop_local_azure.ps1

.EXAMPLE
    .\scripts\stop_local_azure.ps1 -Port 7072
#>

param([int]$Port = 0)

$Timeout = 8

# ── Find the func host PID ────────────────────────────────────────────────────
if ($Port -gt 0) {
    $Conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    if (-not $Conn) {
        Write-Host "No process listening on port $Port."
        exit 0
    }
    $TargetPid = $Conn.OwningProcess
    $ProcName  = (Get-Process -Id $TargetPid -ErrorAction SilentlyContinue)?.Name
    if ($ProcName -notmatch 'func|dotnet') {
        Write-Host "Process on port $Port (PID $TargetPid, '$ProcName') does not look like a func host — aborting."
        exit 1
    }
} else {
    $FuncProc = Get-Process -Name 'func' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $FuncProc) {
        Write-Host "No func host process found."
        exit 0
    }
    $TargetPid = $FuncProc.Id
}

Write-Host "Stopping func host (PID $TargetPid) ..."

# ── Stop the process tree (func host + Python worker child) ───────────────────
function Stop-ProcessTree {
    param([int]$Pid_)
    $Children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $Pid_" -ErrorAction SilentlyContinue
    foreach ($Child in $Children) { Stop-ProcessTree -Pid_ $Child.ProcessId }
    Stop-Process -Id $Pid_ -Force -ErrorAction SilentlyContinue
}

# Ask nicely first — send WM_CLOSE to the main window
$MainProc = Get-Process -Id $TargetPid -ErrorAction SilentlyContinue
if ($MainProc) { $MainProc.CloseMainWindow() | Out-Null }

$Elapsed = 0
while ((Get-Process -Id $TargetPid -ErrorAction SilentlyContinue) -and $Elapsed -lt $Timeout) {
    Start-Sleep -Seconds 1
    $Elapsed++
}

if (Get-Process -Id $TargetPid -ErrorAction SilentlyContinue) {
    Write-Host "Process did not exit after ${Timeout}s — force killing process tree."
    Stop-ProcessTree -Pid_ $TargetPid
}

Write-Host "func host stopped."
