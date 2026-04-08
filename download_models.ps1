# Download Wan 2.1 repackaged weights into ..\comfy_ui\models
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Error "Run setup.ps1 first (.venv missing)."
}
& $Py (Join-Path $Root "download_models.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
