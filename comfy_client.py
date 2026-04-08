"""
HTTP + WebSocket client for ComfyUI prompt queue (minimal subset for debugging).
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

import websocket

import config

LOG = logging.getLogger(__name__)


def server_http_url() -> str:
    return f"http://{config.COMFY_HOST}:{config.COMFY_PORT}"


def wait_for_server(timeout_sec: float = 180.0, poll: float = 1.0) -> None:
    """Block until ComfyUI responds on /system_stats or until timeout."""
    deadline = time.monotonic() + timeout_sec
    url = f"{server_http_url()}/system_stats"
    last_err: str | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                if r.status == 200:
                    LOG.info("ComfyUI server is up (%s)", url)
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = repr(e)
            LOG.debug("wait_for_server: not ready yet: %s", last_err)
        time.sleep(poll)
    raise RuntimeError(
        f"ComfyUI did not become ready within {timeout_sec}s. Last error: {last_err}. "
        f"Expected server at {server_http_url()}. Start ComfyUI first (see Launch.ps1)."
    )


def queue_prompt(prompt: dict[str, Any], client_id: str, prompt_id: str | None = None) -> str:
    payload = {
        "prompt": prompt,
        "client_id": client_id,
        "prompt_id": prompt_id or str(uuid.uuid4()),
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{server_http_url()}/prompt", data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        LOG.error("queue_prompt HTTP %s: %s", e.code, err_body)
        raise RuntimeError(f"ComfyUI rejected the prompt (HTTP {e.code}): {err_body}") from e

    if "error" in body:
        LOG.error("queue_prompt error payload: %s", body)
        raise RuntimeError(f"ComfyUI validation error: {body.get('error')}")

    pid = body.get("prompt_id")
    if not pid:
        raise RuntimeError(f"Unexpected /prompt response: {body}")
    node_errors = body.get("node_errors") or {}
    if node_errors:
        LOG.warning("queue_prompt node_errors (may still run): %s", node_errors)
    LOG.info("Queued prompt_id=%s", pid)
    return pid


def _ws_url(client_id: str) -> str:
    return f"ws://{config.COMFY_HOST}:{config.COMFY_PORT}/ws?clientId={urllib.parse.quote(client_id)}"


def wait_for_prompt_done(
    client_id: str,
    prompt_id: str,
    timeout_sec: float | None = 14400.0,
    on_progress: Callable[[float], None] | None = None,
) -> None:
    """Listen until execution finishes for prompt_id or raises on execution_error.

    on_progress receives values in [0.0, 1.0] from ComfyUI sampling progress (value/max).
    """
    ws_url = _ws_url(client_id)
    LOG.info("WebSocket connect %s", ws_url)
    ws = websocket.WebSocket()
    ws.connect(ws_url)
    try:
        start = time.monotonic()
        while True:
            if timeout_sec is not None and (time.monotonic() - start) > timeout_sec:
                raise TimeoutError(f"Timed out waiting for prompt {prompt_id} after {timeout_sec}s")
            raw = ws.recv()
            if not isinstance(raw, str):
                continue
            msg = json.loads(raw)
            mtype = msg.get("type")
            data = msg.get("data") or {}
            if mtype == "execution_error":
                err = data.get("exception_message") or data.get("error") or data
                LOG.error("execution_error: %s", data)
                raise RuntimeError(f"ComfyUI execution failed: {err}")
            if mtype == "progress" and on_progress:
                if data.get("prompt_id") != prompt_id:
                    continue
                val = data.get("value")
                maxv = data.get("max")
                try:
                    if maxv is not None and float(maxv) > 0 and val is not None:
                        on_progress(min(1.0, max(0.0, float(val) / float(maxv))))
                except (TypeError, ValueError):
                    LOG.debug("Ignoring malformed progress: %s", data)
            if mtype == "executing":
                if data.get("prompt_id") != prompt_id:
                    continue
                if data.get("node") is None:
                    LOG.info("execution finished (executing node=None) prompt_id=%s", prompt_id)
                    if on_progress:
                        try:
                            on_progress(1.0)
                        except Exception:
                            LOG.debug("on_progress(1.0) failed", exc_info=True)
                    return
    finally:
        ws.close()


def get_history(prompt_id: str) -> dict[str, Any]:
    url = f"{server_http_url()}/history/{urllib.parse.quote(prompt_id)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _gather_filenames(obj: Any, out: list[dict[str, str]]) -> None:
    if isinstance(obj, dict):
        if "filename" in obj and "type" in obj:
            out.append(
                {
                    "filename": str(obj["filename"]),
                    "subfolder": str(obj.get("subfolder", "")),
                    "type": str(obj.get("type", "output")),
                }
            )
        for v in obj.values():
            _gather_filenames(v, out)
    elif isinstance(obj, list):
        for x in obj:
            _gather_filenames(x, out)


def resolve_output_video_path(prompt_id: str, comfy_root: Path) -> Path:
    hist = get_history(prompt_id)
    entry = hist.get(prompt_id) or next(iter(hist.values()), None)
    if not entry:
        raise RuntimeError(f"No history entry for prompt_id={prompt_id}")

    outputs = entry.get("outputs") or {}
    files: list[dict[str, str]] = []
    _gather_filenames(outputs, files)
    LOG.debug("history outputs filenames: %s", files)

    for f in files:
        if not f["filename"].lower().endswith((".mp4", ".webm", ".webp", ".gif", ".avi", ".mov")):
            continue
        folder_type = f.get("type", "output")
        if folder_type == "output":
            base = comfy_root / "output"
        elif folder_type == "input":
            base = comfy_root / "input"
        else:
            base = comfy_root / "output"
        sub = f.get("subfolder") or ""
        path = base / sub / f["filename"] if sub else base / f["filename"]
        path = path.resolve()
        if path.is_file():
            LOG.info("Resolved output video: %s", path)
            return path

    # Fallback: newest mp4 under output/local_video_ui
    out_dir = comfy_root / "output" / "local_video_ui"
    if out_dir.is_dir():
        mp4s = sorted(out_dir.glob("**/*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        if mp4s:
            LOG.warning("Using newest mp4 under %s (history parse did not find a file): %s", out_dir, mp4s[0])
            return mp4s[0].resolve()

    raise RuntimeError(
        f"Could not locate output video file for prompt_id={prompt_id}. "
        f"History snippet: outputs keys={list(outputs.keys()) if isinstance(outputs, dict) else 'n/a'}"
    )


def run_workflow(
    prompt: dict[str, Any],
    comfy_root: Path | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> Path:
    """Queue prompt, wait for completion, return path to saved video."""
    root = comfy_root or config.COMFY_ROOT
    client_id = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    if on_progress:
        try:
            on_progress(0.0)
        except Exception:
            LOG.debug("on_progress(0.0) failed", exc_info=True)
    pid = queue_prompt(prompt, client_id, prompt_id=pid)
    wait_for_prompt_done(client_id, pid, timeout_sec=14400.0, on_progress=on_progress)
    return resolve_output_video_path(pid, root)
