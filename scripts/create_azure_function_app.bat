@echo off
rem Create Azure resources for the Traveller World Gen function app.
rem Prerequisites: az login
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_azure_function_app.ps1" %*
