@echo off
REM Use Wan 2.2 repackaged weights (ti2v 5B + wan2.2 VAE) from Hugging Face — set before Python loads config.
set "LOCAL_VIDEO_UI_WAN_STACK=2.2"
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0Launch.ps1"
pause
