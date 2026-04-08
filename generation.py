"""
Shared prompt → ComfyUI workflow → video path (used by Gradio and desktop UI).
"""
from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import audio_track
import comfy_client
import config
import filename_prefix
from workflow_wan_t2v import build_wan_t2v_prompt

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "local_video_ui.log"
GENERATION_LOG_NAME = "generation.log"
WORKFLOW_SNAPSHOT_NAME = "comfy_workflow.json"


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)sZ [%(levelname)s] %(name)s: %(message)s"

    class UtcFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
            if datefmt:
                return dt.strftime(datefmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(UtcFormatter(fmt))
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(UtcFormatter(fmt))
    root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(ch)


def _write_generation_log(
    run_folder: Path,
    *,
    raw_input_prompt: str,
    duration_requested_raw: float | None,
    duration_clamped: float,
    length_frames: int,
    fps: float,
    negative_prompt_effective: str,
    filename_prefix: str,
    comfy_prompt: dict[str, Any] | None,
    video_path: str | None,
    error_message: str | None,
    audio_note: str | None = None,
) -> Path:
    """Write generation.log next to the video (same folder)."""
    log_path = run_folder / GENERATION_LOG_NAME
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    trimmed = raw_input_prompt.strip()
    lines: list[str] = [
        "Local video UI — generation log",
        f"UTC: {now}",
        "",
        "## Input prompt (as entered)",
        raw_input_prompt if raw_input_prompt else "(empty)",
        "",
    ]
    if raw_input_prompt != trimmed:
        lines.extend(
            [
                "## Prompt text adjustments before ComfyUI",
                "- Leading/trailing whitespace was removed for encoding and for the folder name.",
                f"- Text sent to CLIP (positive): {trimmed!r}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Prompt text adjustments before ComfyUI",
                "- No whitespace trimming was needed (already trimmed).",
                f"- Text sent to CLIP (positive): {trimmed!r}",
                "",
            ]
        )

    dr = "default (config)" if duration_requested_raw is None else f"{duration_requested_raw}"
    lines.extend(
        [
            "## Duration / length (app adds these; not part of your text box)",
            f"- Duration requested: {dr} seconds",
            f"- Duration after clamp [{config.MIN_VIDEO_SECONDS}, {config.MAX_VIDEO_SECONDS}]: {duration_clamped} seconds",
            f"- Output FPS (CreateVideo): {fps}",
            f"- Frame count (Wan latent length, snapped to 1+4k): {length_frames}",
            f"- Approximate clip length: {length_frames / fps:.4f} seconds",
            "",
            "## Negative prompt (appended automatically; separate CLIP encode)",
            negative_prompt_effective,
            "",
            "## Other workflow parameters (not in your text prompt)",
            f"- Resolution: {config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}",
            f"- Sampler steps: {config.SAMPLER_STEPS}, CFG: {config.SAMPLER_CFG}",
            f"- Sampler: {config.SAMPLER_NAME} / {config.SAMPLER_SCHEDULER}",
            f"- Model sampling shift (ModelSamplingSD3): {config.MODEL_SAMPLING_SHIFT}",
            f"- Diffusion model: wan2.1_t2v_1.3B_fp16.safetensors",
            "",
        ]
    )

    if comfy_prompt:
        try:
            n7 = comfy_prompt.get("7", {}).get("inputs", {})
            seed = n7.get("seed")
            lines.extend(
                [
                    "## Random / internal values",
                    f"- Seed (random per run): {seed}",
                    "",
                ]
            )
        except (TypeError, AttributeError):
            pass

    lines.extend(
        [
            "## Output paths",
            f"- Run folder: {run_folder}",
            f"- ComfyUI SaveVideo filename_prefix: {filename_prefix}",
            f"- Full workflow JSON: {WORKFLOW_SNAPSHOT_NAME} (same folder)",
            "",
        ]
    )

    if audio_note is not None:
        lines.extend(["## Background audio (MusicGen + FFmpeg)", audio_note, ""])

    if error_message:
        lines.extend(["## Result", "FAILED", "", error_message, ""])
    else:
        lines.extend(["## Result", "SUCCESS", f"- Video file: {video_path}", ""])

    log_path.write_text("\n".join(lines), encoding="utf-8")
    return log_path


def generate_video_from_prompt(
    positive_prompt: str,
    duration_seconds: float | None = None,
    on_progress: Callable[[float], None] | None = None,
    *,
    add_audio: bool = True,
) -> tuple[str | None, str]:
    """
    Returns (video_path_or_none, user-facing status message).
    On success, first element is the path string; on failure, None and error text.
    """
    log = logging.getLogger("local_video_ui.generate")
    raw_input = positive_prompt

    try:
        comfy_client.wait_for_server(timeout_sec=30.0)
    except Exception as e:
        log.error("ComfyUI not reachable: %s", e, exc_info=True)
        return None, (
            f"Cannot reach ComfyUI at {comfy_client.server_http_url()}.\n"
            "Wait until the ComfyUI window is ready, then try again.\n\n"
            f"{type(e).__name__}: {e}"
        )

    if not str(positive_prompt).strip():
        return None, "Prompt is empty."

    sec_requested = float(duration_seconds) if duration_seconds is not None else None
    sec = float(duration_seconds) if duration_seconds is not None else float(config.DEFAULT_VIDEO_SECONDS)
    sec_clamped = max(config.MIN_VIDEO_SECONDS, min(config.MAX_VIDEO_SECONDS, sec))
    length_frames = filename_prefix.duration_seconds_to_length_frames(sec_clamped, config.VIDEO_FPS)
    actual_sec = length_frames / config.VIDEO_FPS

    neg_effective = config.DEFAULT_NEGATIVE_PROMPT.strip()

    try:
        filename_prefix_str, run_folder = filename_prefix.prepare_run_output_folder(
            config.COMFY_ROOT, positive_prompt.strip()
        )
        prompt = build_wan_t2v_prompt(
            positive_prompt,
            length_frames=length_frames,
            filename_prefix=filename_prefix_str,
        )
    except Exception as e:
        log.error("build prompt failed: %s", e, exc_info=True)
        return None, str(e)

    try:
        wf_path = run_folder / WORKFLOW_SNAPSHOT_NAME
        wf_path.write_text(json.dumps(prompt, indent=2), encoding="utf-8")
    except OSError as e:
        log.warning("Could not write %s: %s", WORKFLOW_SNAPSHOT_NAME, e)

    dump = LOG_DIR / "last_prompt.json"
    try:
        dump.write_text(json.dumps(prompt, indent=2), encoding="utf-8")
        log.info("Wrote %s", dump)
    except OSError as e:
        log.warning("Could not write last_prompt.json: %s", e)

    log.info(
        "Generation: ~%.2fs, %d frames, folder=%s",
        actual_sec,
        length_frames,
        run_folder,
    )

    try:
        path = comfy_client.run_workflow(prompt, config.COMFY_ROOT, on_progress=on_progress)
    except Exception as e:
        log.error("run_workflow failed: %s", e, exc_info=True)
        err_txt = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        try:
            log_path = _write_generation_log(
                run_folder,
                raw_input_prompt=raw_input,
                duration_requested_raw=sec_requested,
                duration_clamped=sec_clamped,
                length_frames=length_frames,
                fps=config.VIDEO_FPS,
                negative_prompt_effective=neg_effective,
                filename_prefix=filename_prefix_str,
                comfy_prompt=prompt,
                video_path=None,
                error_message=err_txt,
                audio_note=None,
            )
        except OSError:
            log_path = run_folder / GENERATION_LOG_NAME
        return None, f"{type(e).__name__}: {e}\n\nSee: {log_path}\nGlobal log: {LOG_FILE}"

    p = str(path)
    if add_audio:
        _, audio_note = audio_track.try_add_background_audio(
            Path(p),
            positive_prompt.strip(),
            actual_sec,
            run_folder,
        )
    else:
        audio_note = "Background audio not added (unchecked in UI)."

    try:
        log_path = _write_generation_log(
            run_folder,
            raw_input_prompt=raw_input,
            duration_requested_raw=sec_requested,
            duration_clamped=sec_clamped,
            length_frames=length_frames,
            fps=config.VIDEO_FPS,
            negative_prompt_effective=neg_effective,
            filename_prefix=filename_prefix_str,
            comfy_prompt=prompt,
            video_path=p,
            error_message=None,
            audio_note=audio_note,
        )
    except OSError as e:
        log.warning("Could not write generation.log: %s", e)
        log_path = run_folder / GENERATION_LOG_NAME

    log.info("Done: %s", path)
    msg = (
        f"Saved ({length_frames} frames ≈ {actual_sec:.2f}s @ {config.VIDEO_FPS} fps):\n{p}\n\n"
        f"Audio: {audio_note}\n\n"
        f"Log: {log_path}"
    )
    return p, msg
