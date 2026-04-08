"""
Paths and model filenames for the thin UI. Override with env LOCAL_VIDEO_UI_COMFY_ROOT.
"""
from __future__ import annotations

import os
from pathlib import Path


def _default_comfy_root() -> Path:
    env = os.environ.get("LOCAL_VIDEO_UI_COMFY_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    # Bundled layout: local_video_ui/vendor/comfyui (see Ensure-ComfyUI.ps1 / Launch.ps1)
    return Path(__file__).resolve().parent / "vendor" / "comfyui"


COMFY_ROOT: Path = _default_comfy_root()

# ComfyUI HTTP API
COMFY_HOST = os.environ.get("LOCAL_VIDEO_UI_COMFY_HOST", "127.0.0.1")
COMFY_PORT = int(os.environ.get("LOCAL_VIDEO_UI_COMFY_PORT", "8188"))

# Official Comfy-Org repackaged Wan 2.1 (see ComfyUI_examples/wan)
HF_REPO = "Comfy-Org/Wan_2.1_ComfyUI_repackaged"
MODEL_FILES: list[tuple[str, str, str]] = [
    # (hf path under repo, comfy subdir under models/, local filename)
    (
        "split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors",
        "diffusion_models",
        "wan2.1_t2v_1.3B_fp16.safetensors",
    ),
    (
        "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "text_encoders",
        "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    ),
    (
        "split_files/vae/wan_2.1_vae.safetensors",
        "vae",
        "wan_2.1_vae.safetensors",
    ),
]

# Default negative prompt (English; user only types the positive in the UI)
DEFAULT_NEGATIVE_PROMPT = (
    "worst quality, low quality, blurry, jpeg artifacts, watermark, text, logo, "
    "static image, ugly, deformed, bad anatomy"
)

# Wan T2V latent defaults (match ComfyUI official example; length = frame count)
VIDEO_WIDTH = 832
VIDEO_HEIGHT = 480
VIDEO_LENGTH = 33

# UI: target duration in seconds (mapped to frame count; uses VIDEO_FPS below)
MIN_VIDEO_SECONDS = 0.25
MAX_VIDEO_SECONDS = 30.0

# Sampling (match official example workflow)
SAMPLER_STEPS = 30
SAMPLER_CFG = 6.0
SAMPLER_NAME = "uni_pc"
SAMPLER_SCHEDULER = "simple"
MODEL_SAMPLING_SHIFT = 8.0

# Output (default prefix if not building from prompt)
OUTPUT_FILENAME_PREFIX = "local_video_ui/video"
VIDEO_FPS = 24.0

# Recompute default duration from fps + default frame count
DEFAULT_VIDEO_SECONDS = VIDEO_LENGTH / VIDEO_FPS

# Background audio (MusicGen + FFmpeg mux). Set LOCAL_VIDEO_UI_AUDIO=0 to disable globally.
AUDIO_ENABLE = os.environ.get("LOCAL_VIDEO_UI_AUDIO", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
AUDIO_MODEL_ID = os.environ.get("LOCAL_VIDEO_UI_AUDIO_MODEL", "facebook/musicgen-small").strip()
AUDIO_DEVICE = os.environ.get("LOCAL_VIDEO_UI_AUDIO_DEVICE", "cpu").strip().lower()
AUDIO_GUIDANCE_SCALE = float(os.environ.get("LOCAL_VIDEO_UI_AUDIO_GUIDANCE", "3.0"))

# Optional PNG previews from final MP4 (FFmpeg); one frame every N seconds of video time
PREVIEW_FRAME_INTERVAL_SEC = float(os.environ.get("LOCAL_VIDEO_UI_PREVIEW_INTERVAL_SEC", "15"))
