@echo off
rem Create or update the monthly Cost Management budget.
rem Prerequisites: az login
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0set_azure_budget.ps1" %*
