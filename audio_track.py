"""
Text-conditioned background audio (MusicGen) + FFmpeg mux onto the final MP4.
Instrumental / ambient bed — not literal scene foley; uses the same scene prompt for conditioning.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

LOG = logging.getLogger(__name__)


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    f = shutil.which("ffmpeg")
    if f:
        return f
    raise RuntimeError(
        "ffmpeg not found. Install FFmpeg or ensure imageio-ffmpeg is installed (comes with ComfyUI deps)."
    )


def _musicgen_audio_prompt(scene_prompt: str) -> str:
    p = scene_prompt.strip()
    return (
        "Realistic cinematic ambient instrumental soundtrack, subtle environmental atmosphere, "
        "no vocals, no spoken words, wide stereo mix. Scene: "
        + p
    )


def _max_tokens_for_duration(duration_sec: float) -> int:
    # ~50 codec steps per second; hard cap 1503 (~30s) per MusicGen limits
    return int(min(1503, max(64, round(float(duration_sec) * 50.0))))


def generate_musicgen_wav(
    scene_prompt: str,
    duration_sec: float,
    out_wav: Path,
    model_id: str,
    device: str,
    guidance_scale: float,
) -> tuple[int, str]:
    """Generate WAV file; returns (sample_rate, device_used)."""
    import torch
    from transformers import AutoProcessor, MusicgenForConditionalGeneration

    text = _musicgen_audio_prompt(scene_prompt)
    dev = torch.device(device if device in ("cpu", "cuda") else ("cuda" if torch.cuda.is_available() else "cpu"))
    if dev.type == "cuda" and not torch.cuda.is_available():
        dev = torch.device("cpu")

    LOG.info("Loading MusicGen %s on %s …", model_id, dev)
    processor = AutoProcessor.from_pretrained(model_id)
    model = MusicgenForConditionalGeneration.from_pretrained(model_id)
    model.to(dev)
    model.eval()

    inputs = processor(text=[text], padding=True, return_tensors="pt")
    inputs = {k: v.to(dev) for k, v in inputs.items()}
    max_new_tokens = _max_tokens_for_duration(duration_sec)

    with torch.no_grad():
        audio_values = model.generate(
            **inputs,
            do_sample=True,
            guidance_scale=guidance_scale,
            max_new_tokens=max_new_tokens,
        )

    import numpy as np
    import soundfile as sf

    # Hugging Face MusicGen: [batch, channels, samples] (see model card / scipy.io example).
    av = audio_values[0].detach().float().cpu().numpy()
    if av.ndim == 2:
        # channels x samples -> time x channels for soundfile
        x = np.clip(av.T, -1.0, 1.0)
    elif av.ndim == 1:
        x = np.clip(av[:, np.newaxis], -1.0, 1.0)
    else:
        x = np.clip(np.asarray(av).reshape(-1, 1), -1.0, 1.0)

    sr: int | None = None
    ae = getattr(model.config, "audio_encoder", None)
    if ae is not None:
        sr = getattr(ae, "sampling_rate", None)
    if sr is None:
        fe = getattr(processor, "feature_extractor", None)
        if fe is not None:
            sr = getattr(fe, "sampling_rate", None)
    if sr is None:
        sr = 32000

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), x, int(sr), subtype="PCM_16")

    del model
    del processor
    if dev.type == "cuda":
        torch.cuda.empty_cache()

    return int(sr), str(dev)


def mux_video_audio_ffmpeg(video_mp4: Path, audio_wav: Path, out_mp4: Path) -> None:
    ffmpeg = _ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_mp4),
        "-i",
        str(audio_wav),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def add_background_audio(
    video_mp4: Path,
    scene_prompt: str,
    duration_sec: float,
    run_folder: Path,
    *,
    model_id: str,
    device: str,
    guidance_scale: float,
) -> tuple[Path, str]:
    """
    Generate MusicGen WAV in run_folder, mux onto video (replaces file in place via temp).
    Returns (final_video_path, human-readable status line).
    """
    wav_path = run_folder / "audio_musicgen.wav"
    tmp_out = video_mp4.with_suffix(".mux_tmp.mp4")

    sr, used_dev = generate_musicgen_wav(
        scene_prompt,
        duration_sec,
        wav_path,
        model_id=model_id,
        device=device,
        guidance_scale=guidance_scale,
    )

    try:
        mux_video_audio_ffmpeg(video_mp4, wav_path, tmp_out)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg mux failed: {e.stderr or e}") from e

    os.replace(tmp_out, video_mp4)

    note = (
        f"Background audio: MusicGen ({model_id}) on {used_dev}, {sr} Hz; "
        f"WAV saved as {wav_path.name}. Muxed AAC into video."
    )
    return video_mp4.resolve(), note


def try_add_background_audio(
    video_mp4: Path,
    scene_prompt: str,
    duration_sec: float,
    run_folder: Path,
) -> tuple[Path, str]:
    """
    Best-effort audio. On failure returns original path + error note (caller logs, does not fail run).
    """
    import config as cfg

    if not getattr(cfg, "AUDIO_ENABLE", True):
        return video_mp4, "Background audio disabled in config."

    try:
        return add_background_audio(
            video_mp4,
            scene_prompt,
            duration_sec,
            run_folder,
            model_id=cfg.AUDIO_MODEL_ID,
            device=cfg.AUDIO_DEVICE,
            guidance_scale=cfg.AUDIO_GUIDANCE_SCALE,
        )
    except Exception as e:
        LOG.exception("Background audio failed; leaving silent video.")
        return video_mp4, f"Background audio skipped ({type(e).__name__}: {e}). Video has no added track."
