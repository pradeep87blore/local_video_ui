# One-click: ensure ComfyUI + venv + models, start ComfyUI, wait, run desktop UI
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $Root ".venv\Scripts\python.exe"

Set-Location $Root
& (Join-Path $Root "Ensure-ComfyUI.ps1")

if (-not (Test-Path $Py)) {
    Write-Host '[Launch] Virtual environment missing - running full setup (may take several minutes) ...'
    & (Join-Path $Root "setup.ps1")
    if (-not (Test-Path $Py)) {
        Write-Error "Setup did not create .venv. Fix errors above and retry."
    }
}

Write-Host '[Launch] Checking Wan model files under vendor\comfyui\models ...'
& $Py (Join-Path $Root "check_models.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host '[Launch] Downloading model weights (several GB; first run only) ...'
    & $Py (Join-Path $Root "download_models.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Model download failed. Check network / Hugging Face access and retry."
    }
}

$ComfyScript = Join-Path $Root "Start-ComfyUI.ps1"
Write-Host '[Launch] Opening ComfyUI in a new PowerShell window ...'
Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", $ComfyScript
)

Write-Host '[Launch] Waiting for http://127.0.0.1:8188 (up to 300s) ...'
$deadline = (Get-Date).AddSeconds(300)
$ok = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8188/system_stats" -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}
if (-not $ok) {
    Write-Error "ComfyUI did not respond on port 8188 in time. Check the ComfyUI window for errors."
}

Write-Host '[Launch] Starting desktop prompt window (close this window to stop the UI; ComfyUI stays in its window)'
Set-Location $Root
& $Py "app_desktop.py"
