@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0compute_version.ps1" %*
