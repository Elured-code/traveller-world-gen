@echo off
rem Stop a locally running Azure Functions host.
rem
rem Options:
rem   -Port <N>   Only stop the func process listening on port N
rem
rem Examples:
rem   scripts\stop_local_azure
rem   scripts\stop_local_azure -Port 7072
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_local_azure.ps1" %*
