"""
Builds a ComfyUI API prompt dict for Wan 2.1 text-to-video (official graph layout).
"""
from __future__ import annotations

import random
from typing import Any

import config


def build_wan_t2v_prompt(
    positive_prompt: str,
    negative_prompt: str | None = None,
    seed: int | None = None,
    length_frames: int | None = None,
    filename_prefix: str | None = None,
) -> dict[str, Any]:
    if not positive_prompt or not str(positive_prompt).strip():
        raise ValueError("Prompt is empty.")

    neg = negative_prompt if negative_prompt is not None else config.DEFAULT_NEGATIVE_PROMPT
    if seed is None:
        seed = random.randint(0, 2**63 - 1)

    length = int(length_frames) if length_frames is not None else int(config.VIDEO_LENGTH)
    prefix = filename_prefix if filename_prefix is not None else config.OUTPUT_FILENAME_PREFIX

    # Node IDs are stable strings for logging / history lookup
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": config.MODEL_DIFFUSION_FILE,
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "ModelSamplingSD3",
            "inputs": {
                "model": ["1", 0],
                "shift": config.MODEL_SAMPLING_SHIFT,
            },
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": config.MODEL_CLIP_FILE,
                "type": "wan",
                "device": "default",
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt.strip(),
                "clip": ["3", 0],
            },
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": neg.strip(),
                "clip": ["3", 0],
            },
        },
        "6": {
            "class_type": "EmptyHunyuanLatentVideo",
            "inputs": {
                "width": config.VIDEO_WIDTH,
                "height": config.VIDEO_HEIGHT,
                "length": length,
                "batch_size": 1,
            },
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["2", 0],
                "seed": seed,
                "steps": config.SAMPLER_STEPS,
                "cfg": config.SAMPLER_CFG,
                "sampler_name": config.SAMPLER_NAME,
                "scheduler": config.SAMPLER_SCHEDULER,
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
                "denoise": 1.0,
            },
        },
        "8": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": config.MODEL_VAE_FILE,
            },
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["8", 0],
            },
        },
        "10": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["9", 0],
                "fps": config.VIDEO_FPS,
            },
        },
        "11": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["10", 0],
                "filename_prefix": prefix,
                "format": "mp4",
                "codec": "auto",
            },
        },
    }
