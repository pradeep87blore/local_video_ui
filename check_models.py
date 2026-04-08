"""Exit 0 if all Wan repackaged files exist under COMFY_ROOT; else 1."""
from __future__ import annotations

import sys

import config


def main() -> int:
    for _remote, subdir, local_name in config.MODEL_FILES:
        p = config.COMFY_ROOT / "models" / subdir / local_name
        if not p.is_file() or p.stat().st_size == 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
