@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0Launch.ps1"
pause
