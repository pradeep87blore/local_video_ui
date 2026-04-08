"""
Persistent FIFO queue of generation jobs (JSON file). Survives restarts; jobs removed only after completion.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)

QUEUE_VERSION = 1
DEFAULT_QUEUE_FILENAME = "generation_queue.json"


def default_queue_path() -> Path:
    env = os.environ.get("LOCAL_VIDEO_UI_QUEUE_FILE", "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent / DEFAULT_QUEUE_FILENAME


@dataclass
class QueuedJob:
    id: str
    prompt: str
    duration_seconds: float
    add_audio: bool
    save_preview_frames: bool

    @classmethod
    def create(
        cls,
        prompt: str,
        duration_seconds: float,
        *,
        add_audio: bool,
        save_preview_frames: bool,
    ) -> QueuedJob:
        return cls(
            id=str(uuid.uuid4()),
            prompt=prompt.strip(),
            duration_seconds=float(duration_seconds),
            add_audio=add_audio,
            save_preview_frames=save_preview_frames,
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> QueuedJob:
        return cls(
            id=str(d["id"]),
            prompt=str(d["prompt"]),
            duration_seconds=float(d["duration_seconds"]),
            add_audio=bool(d.get("add_audio", True)),
            save_preview_frames=bool(d.get("save_preview_frames", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PersistentJobQueue:
    """Thread-safe queue backed by a JSON file. First job is next to run."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_queue_path()
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._jobs: list[QueuedJob] = []
        self._stopped = False
        self.load()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        with self._lock:
            self._jobs = []
            if not self._path.is_file():
                return
            try:
                raw = self._path.read_text(encoding="utf-8")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    return
                for item in data.get("jobs", []):
                    if isinstance(item, dict):
                        self._jobs.append(QueuedJob.from_dict(item))
                LOG.info("Loaded %d job(s) from %s", len(self._jobs), self._path)
            except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as e:
                LOG.warning("Could not load queue file %s: %s", self._path, e)

    def _save_unlocked(self) -> None:
        payload = {"version": QUEUE_VERSION, "jobs": [j.to_dict() for j in self._jobs]}
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(text + "\n", encoding="utf-8")
        os.replace(tmp, self._path)

    def add(self, job: QueuedJob) -> None:
        with self._cond:
            self._jobs.append(job)
            self._save_unlocked()
            self._cond.notify_all()

    def snapshot(self) -> list[QueuedJob]:
        with self._lock:
            return list(self._jobs)

    def wait_peek_first(self, timeout: float = 0.5) -> QueuedJob | None:
        """Block until a job exists or queue is stopped. Returns jobs[0] without removing."""
        with self._cond:
            while not self._stopped and not self._jobs:
                self._cond.wait(timeout=timeout)
            if self._stopped:
                return None
            if not self._jobs:
                return None
            return self._jobs[0]

    def complete_first(self, job_id: str) -> None:
        """Remove the front job after a run finishes (success or failure). Unblocks the worker."""
        with self._cond:
            if not self._jobs:
                return
            if self._jobs[0].id != job_id:
                LOG.error(
                    "Queue head id mismatch (expected %s, got %s); removing front to unblock",
                    job_id,
                    self._jobs[0].id,
                )
            self._jobs.pop(0)
            self._save_unlocked()
            self._cond.notify_all()

    def remove_at_index(self, index: int) -> bool:
        """Remove a pending job by index (0 = next to run). Caller must avoid removing the running job."""
        with self._cond:
            if index < 0 or index >= len(self._jobs):
                return False
            self._jobs.pop(index)
            self._save_unlocked()
            self._cond.notify_all()
            return True

    def stop(self) -> None:
        with self._cond:
            self._stopped = True
            self._cond.notify_all()

    def is_stopped(self) -> bool:
        with self._lock:
            return self._stopped
