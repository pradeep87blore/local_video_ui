# Start desktop UI (Tkinter) — same as Launch.ps1 without starting ComfyUI
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Error "Run setup.ps1 first (.venv missing)." }
Set-Location $Root
Write-Host "[local_video_ui] Desktop prompt window"
& $Py "app_desktop.py"
