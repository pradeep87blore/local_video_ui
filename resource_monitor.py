"""
Background thread: periodically log CPU, RAM, and (when available) NVIDIA GPU stats.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable

LOG = logging.getLogger("local_video_ui.resources")

# Common prefix for grep / log viewers
LOG_PREFIX = "PC resource consumption:"


def _interval_sec() -> float:
    raw = os.environ.get("LOCAL_VIDEO_UI_RESOURCE_LOG_INTERVAL_SEC", "60").strip()
    try:
        v = float(raw)
    except ValueError:
        v = 60.0
    return max(5.0, v)


def _gpu_line() -> str | None:
    """NVIDIA via nvidia-smi (no extra Python deps). Returns None if unavailable."""
    try:
        kwargs: dict = {
            "args": [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            "capture_output": True,
            "text": True,
            "timeout": 8,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(**kwargs)
        if r.returncode != 0 or not (r.stdout or "").strip():
            return None
        parts_out: list[str] = []
        for line in r.stdout.strip().splitlines():
            seg = [s.strip() for s in line.split(",")]
            if len(seg) < 4:
                continue
            name, util, mem_u, mem_t = seg[0], seg[1], seg[2], seg[3]
            parts_out.append(f"{name}: GPU {util}% | VRAM {mem_u}/{mem_t} MiB")
        return "GPU — " + " | ".join(parts_out) if parts_out else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _log_once() -> None:
    import psutil

    cpu = psutil.cpu_percent(interval=None)
    vm = psutil.virtual_memory()
    ram_total_gib = vm.total / (1024**3)
    ram_used_gib = vm.used / (1024**3)
    proc = psutil.Process()
    rss_mib = proc.memory_info().rss / (1024**2)

    msg = (
        f"{LOG_PREFIX} CPU={cpu:.1f}% | "
        f"system RAM {ram_used_gib:.2f}/{ram_total_gib:.1f} GiB ({vm.percent:.1f}%) | "
        f"this process RSS ≈ {rss_mib:.0f} MiB"
    )
    gpu = _gpu_line()
    if gpu:
        msg += f" | {gpu}"
    else:
        msg += " | GPU: n/a (no nvidia-smi / non-NVIDIA)"
    LOG.info(msg)


def start(interval_sec: float | None = None) -> Callable[[], None]:
    """
    Start a daemon thread that logs resource usage every ``interval_sec`` seconds
    (default 60, or env LOCAL_VIDEO_UI_RESOURCE_LOG_INTERVAL_SEC, minimum 5).

    Returns a no-arg function to request stop (optional; thread is daemon).
    """
    interval = float(interval_sec) if interval_sec is not None else _interval_sec()
    interval = max(5.0, interval)
    stop = threading.Event()

    def loop() -> None:
        import psutil

        psutil.cpu_percent(interval=None)
        time.sleep(0.05)
        while True:
            if stop.wait(interval):
                break
            try:
                _log_once()
            except Exception:
                LOG.exception("%s logging failed", LOG_PREFIX)

    t = threading.Thread(target=loop, name="pc-resource-log", daemon=True)
    t.start()
    return stop.set

