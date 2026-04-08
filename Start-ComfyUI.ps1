# Start ComfyUI on 127.0.0.1:8188 using the shared venv Python
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$Comfy = Join-Path $Root "vendor\comfyui"
if (-not (Test-Path $Py)) { Write-Error "Run setup.ps1 first (.venv missing)." }
if (-not (Test-Path (Join-Path $Comfy "main.py"))) { Write-Error "ComfyUI not found at $Comfy" }

Set-Location $Comfy
Write-Host "[ComfyUI] Starting from $Comfy"
Write-Host "[ComfyUI] URL: http://127.0.0.1:8188"
& $Py "main.py" --listen "127.0.0.1" --port 8188
