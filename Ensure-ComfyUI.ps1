# Clone ComfyUI into vendor\comfyui if missing (GPL-3.0 — see README).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Comfy = Join-Path $Root "vendor\comfyui"
$MainPy = Join-Path $Comfy "main.py"

if (Test-Path $MainPy) {
    return
}

Write-Host "[EnsureComfy] ComfyUI not found at $Comfy — cloning official repository …"
$VendorDir = Join-Path $Root "vendor"
if (-not (Test-Path $VendorDir)) {
    New-Item -ItemType Directory -Path $VendorDir | Out-Null
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git is required to download ComfyUI. Install Git for Windows (https://git-scm.com/download/win) or clone https://github.com/comfyanonymous/ComfyUI into: $Comfy"
}

Push-Location $VendorDir
try {
    & git clone --depth 1 "https://github.com/comfyanonymous/ComfyUI.git" "comfyui"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "git clone ComfyUI failed (exit $LASTEXITCODE)."
    }
} finally {
    Pop-Location
}

if (-not (Test-Path $MainPy)) {
    Write-Error "ComfyUI main.py still missing after clone."
}

Write-Host "[EnsureComfy] ComfyUI is ready at $Comfy"
