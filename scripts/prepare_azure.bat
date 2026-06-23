@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare_azure.ps1" %*
