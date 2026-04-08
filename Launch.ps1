# One-click: open ComfyUI in a new window, wait until ready, run the thin UI here
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Error "Run setup.ps1 first (.venv missing)."
}

$ComfyScript = Join-Path $Root "Start-ComfyUI.ps1"
Write-Host "[Launch] Opening ComfyUI in a new PowerShell window..."
Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", $ComfyScript
)

Write-Host "[Launch] Waiting for http://127.0.0.1:8188 (up to 300s)..."
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

Write-Host "[Launch] Starting desktop prompt window (close this window to stop the UI; ComfyUI stays in its window)"
Set-Location $Root
& $Py "app_desktop.py"
