# Optional: browser UI at http://127.0.0.1:7860 (same backend as app_desktop.py)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Error "Run setup.ps1 first (.venv missing)." }
Set-Location $Root
Write-Host '[local_video_ui] Gradio: http://127.0.0.1:7860'
& $Py "app.py"
