# Local video UI (ComfyUI + prompt window)

Single-folder Windows workflow: this repo contains the thin desktop UI; **ComfyUI itself is downloaded automatically** into `vendor/comfyui` the first time you run [`Launch.bat`](Launch.bat) (or [`Launch.ps1`](Launch.ps1)). Large **model weights** are not in git; they are fetched from Hugging Face when needed.

## Prerequisites

- **Windows 10/11**
- **Python 3.10+** on your PATH ([python.org](https://www.python.org/downloads/) — enable “Add python.exe to PATH”)
- **Git** ([git-scm.com](https://git-scm.com/download/win)) — used once to clone [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- **NVIDIA GPU + driver** recommended for reasonable speed (setup installs CUDA PyTorch wheels; CPU-only is not the target experience)

## First run

1. Clone this repository.
2. Double-click **`Launch.bat`** (or run `.\Launch.ps1` in PowerShell).

On the first run the script will:

1. Clone ComfyUI into **`vendor/comfyui`** (ignored by git; GPL-3.0, see below).
2. Create **`.venv`** and install PyTorch, ComfyUI dependencies, and this UI’s [`requirements.txt`](requirements.txt).
3. Download **Wan 2.1** repackaged weights (several GB) into `vendor/comfyui/models/` if they are missing.
4. Start ComfyUI in a separate window, wait until `http://127.0.0.1:8188` is reachable, then open the **desktop prompt** window.

Later runs skip cloning and pip installs unless you deleted `.venv`; model files are only re-downloaded if missing.

### Manual steps (optional)

- **Setup only** (no UI): `.\setup.ps1`
- **Models only**: `.\download_models.ps1` or `python download_models.py` (after venv exists)

## Configuration

| Variable | Purpose |
|----------|---------|
| `LOCAL_VIDEO_UI_COMFY_ROOT` | Override path to ComfyUI tree (default: `vendor/comfyui` under this project). |
| `LOCAL_VIDEO_UI_COMFY_HOST` / `LOCAL_VIDEO_UI_COMFY_PORT` | HTTP API host/port (default `127.0.0.1:8188`). |
| `LOCAL_VIDEO_UI_AUDIO=0` | Disable MusicGen background audio. |
| `LOCAL_VIDEO_UI_RESOURCE_LOG_INTERVAL_SEC` | Seconds between “PC resource consumption” log lines. |

Logs: `logs/local_video_ui.log`; each run also writes a folder under `vendor/comfyui/output/local_video_ui/`.

## ComfyUI license and updates

ComfyUI is **GPL-3.0**. Source is available from the [official repository](https://github.com/comfyanonymous/ComfyUI). This project does not modify ComfyUI; it clones it beside the UI.

To update ComfyUI after a first install:

```powershell
cd vendor\comfyui
git pull
```

Then restart the app.

## Troubleshooting

- **“Git is required”** — Install Git for Windows and retry.
- **PyTorch / CUDA install fails** — Install a matching NVIDIA driver; see [PyTorch get-started](https://pytorch.org/get-started/locally/). You can re-run `.\setup.ps1` after fixing the environment.
- **ComfyUI window shows errors** — Check that models finished downloading and that `vendor/comfyui` is intact.
