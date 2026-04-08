# Prerequisites: Python 3.10+ on PATH; Git (for first-time ComfyUI clone). Run: .\setup.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Comfy = Join-Path $Root "vendor\comfyui"
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "[local_video_ui] Root: $Root"
& (Join-Path $Root "Ensure-ComfyUI.ps1")

$pyExe = $null
$pyPre = @()
# Prefer `python` on PATH — the Windows `py` launcher can exist but have no -3.11/-3.12 runtimes registered.
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyExe = "python"
    $pyPre = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($v in @("-3.12", "-3.11", "-3.10")) {
        $p = Start-Process -FilePath "py" -ArgumentList @($v, "--version") -Wait -NoNewWindow -PassThru
        if ($p.ExitCode -eq 0) { $pyExe = "py"; $pyPre = @($v); break }
    }
}
if (-not $pyExe) {
    Write-Error "Python not found. Install Python 3.10+ from https://www.python.org/downloads/ (check 'Add to PATH') and retry."
}

Write-Host "[local_video_ui] Using: $pyExe $($pyPre -join ' ')"
& $pyExe @pyPre --version
if ($LASTEXITCODE -ne 0) { Write-Error "Python invocation failed" }

Push-Location $Root
try {
    if (-not (Test-Path $VenvPy)) {
        Write-Host "[local_video_ui] Creating virtual environment .venv ..."
        & $pyExe @pyPre -m venv .venv
        if ($LASTEXITCODE -ne 0) { Write-Error "venv creation failed" }
    }

    # Use `python -m pip` so pip can upgrade itself on Windows (avoids "please run python -m pip" errors).
    Write-Host "[local_video_ui] Upgrading pip ..."
    & $VenvPy -m pip install --upgrade pip wheel
    if ($LASTEXITCODE -ne 0) { Write-Error "pip upgrade failed" }

    Write-Host "[local_video_ui] Installing PyTorch (CUDA 12.8 wheel). If this fails, see https://pytorch.org/get-started/locally/"
    & $VenvPy -m pip install torch torchvision torchaudio --index-url "https://download.pytorch.org/whl/cu128"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "cu128 install failed; trying cu126 ..."
        & $VenvPy -m pip install torch torchvision torchaudio --index-url "https://download.pytorch.org/whl/cu126"
        if ($LASTEXITCODE -ne 0) { Write-Error "PyTorch install failed. Install a CUDA build matching your driver, then re-run." }
    }

    $ComfyReq = Join-Path $Comfy "requirements.txt"
    Write-Host "[local_video_ui] Installing ComfyUI requirements from $ComfyReq"
    & $VenvPy -m pip install -r $ComfyReq
    if ($LASTEXITCODE -ne 0) { Write-Error "ComfyUI requirements install failed" }

    $UiReq = Join-Path $Root "requirements.txt"
    Write-Host "[local_video_ui] Installing thin UI requirements from $UiReq"
    & $VenvPy -m pip install -r $UiReq
    if ($LASTEXITCODE -ne 0) { Write-Error "UI requirements install failed" }

    Write-Host ""
    Write-Host "Setup finished OK."
    Write-Host "Next: run .\Launch.ps1 or Launch.bat (will download models on first run if needed, then open the UI)."
    Write-Host ""
} finally {
    Pop-Location
}
