"""
Extract preview PNGs from the final MP4 using FFmpeg (one frame every N seconds of video time).
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from audio_track import _ffmpeg_exe

import config

LOG = logging.getLogger(__name__)


def try_extract_preview_frames(
    video_mp4: Path,
    run_folder: Path,
    interval_sec: float | None = None,
) -> str:
    """
    Writes preview_0001.png, preview_0002.png, ... into run_folder.
    Returns a one-line status for generation.log (never raises).
    """
    ival = float(interval_sec if interval_sec is not None else config.PREVIEW_FRAME_INTERVAL_SEC)
    if ival <= 0:
        return "Preview frames skipped (invalid interval)."

    try:
        ffmpeg = _ffmpeg_exe()
    except RuntimeError as e:
        return f"Preview frames skipped ({e})"

    out_pattern = str(run_folder / "preview_%04d.png")
    # Output frame rate = 1/interval Hz => one still every `interval` seconds along the timeline
    vf = f"fps={1.0 / ival}"

    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_mp4),
        "-vf",
        vf,
        out_pattern,
    ]
    kwargs: dict = {
        "args": cmd,
        "capture_output": True,
        "text": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        r = subprocess.run(**kwargs)
    except OSError as e:
        return f"Preview frames skipped ({type(e).__name__}: {e})."

    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        return f"Preview frames failed (ffmpeg exit {r.returncode}): {err[:200]}"

    paths = sorted(run_folder.glob("preview_*.png"))
    if not paths:
        return "Preview frames: ffmpeg ran but no PNGs were written (very short clip?)."

    LOG.info("Wrote %d preview frame(s) under %s", len(paths), run_folder)
    return (
        f"Saved {len(paths)} preview PNG(s) in this folder ({ival:g}s apart): "
        + ", ".join(p.name for p in paths[:12])
        + (" …" if len(paths) > 12 else "")
    )
