@echo off
rem Run the Azure Functions app locally.
rem
rem Options:
rem   -NoSync      Skip module sync step
rem   -Port <N>    Bind to port N instead of the default (7071)
rem
rem Examples:
rem   scripts\run_local_azure
rem   scripts\run_local_azure -Port 7072
rem   scripts\run_local_azure -NoSync
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local_azure.ps1" %*
