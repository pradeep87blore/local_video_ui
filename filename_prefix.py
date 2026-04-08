"""
Prompt → safe folder names; per-run output directory under ComfyUI output.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def slugify_prompt(text: str, max_len: int = 60) -> str:
    """Turn prompt into a single-line filesystem-safe slug (for folder names)."""
    t = " ".join(text.strip().split())
    if not t:
        return "video"
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", t)
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"[^a-zA-Z0-9._-]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("._-")
    if not t:
        return "video"
    if len(t) > max_len:
        t = t[:max_len].rstrip("._-")
    return t or "video"


def snap_hunyuan_length(frames: int) -> int:
    """Match EmptyHunyuanLatentVideo: length ≥ 1, step 4 → 1, 5, 9, 13, …"""
    frames = max(1, min(int(frames), 4096))
    k = round((frames - 1) / 4.0)
    return int(1 + 4 * max(0, k))


def duration_seconds_to_length_frames(seconds: float, fps: float) -> int:
    target = max(1, int(round(float(seconds) * float(fps))))
    return snap_hunyuan_length(target)


def prepare_run_output_folder(comfy_root: Path, positive_prompt: str) -> tuple[str, Path]:
    """
    Create output/local_video_ui/<unique_folder>/ and return:
    - ComfyUI filename_prefix (no extension), e.g. local_video_ui/<folder>/video
    - Absolute Path to that run folder (video + logs live here).
    """
    safe = slugify_prompt(positive_prompt)
    ts = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    base_name = f"{ts}_{safe}"
    # Windows path segment length safety
    if len(base_name) > 180:
        base_name = base_name[:180].rstrip("._-")

    root_out = comfy_root / "output" / "local_video_ui"
    root_out.mkdir(parents=True, exist_ok=True)

    folder_name = base_name
    n = 0
    while (root_out / folder_name).exists():
        n += 1
        folder_name = f"{base_name}_{n}"

    run_folder = (root_out / folder_name).resolve()
    run_folder.mkdir(parents=True, exist_ok=True)

    filename_prefix = f"local_video_ui/{folder_name}/video"
    return filename_prefix, run_folder
