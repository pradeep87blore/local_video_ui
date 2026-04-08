"""
Download Wan 2.1 repackaged files into the sibling ComfyUI models/ folders.
"""
from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

import config

LOG = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    root = config.COMFY_ROOT
    models = root / "models"
    if not root.is_dir():
        LOG.error("COMFY_ROOT does not exist: %s (set LOCAL_VIDEO_UI_COMFY_ROOT?)", root)
        return 1

    for remote, subdir, local_name in config.MODEL_FILES:
        dest = models / subdir / local_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0:
            LOG.info("Already present, skipping: %s", dest)
            continue
        LOG.info("Downloading %s from %s …", remote, config.HF_REPO)
        try:
            cached = hf_hub_download(
                repo_id=config.HF_REPO,
                filename=remote,
            )
        except Exception as e:
            LOG.exception("Download failed: %s", e)
            return 2
        shutil.copy2(cached, dest)
        LOG.info("Installed: %s (%s bytes)", dest, dest.stat().st_size)

    LOG.info("All model files are in place under %s", models)
    return 0


if __name__ == "__main__":
    sys.exit(main())
