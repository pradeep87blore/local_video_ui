"""
Desktop UI (Tkinter): prompt + queue + serial generation worker.
Run via Launch.ps1 / Launch.bat after ComfyUI is up.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import comfy_client
import config
import generation
import resource_monitor
from generation_queue import PersistentJobQueue, QueuedJob


def _open_path(path: str) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


def main() -> None:
    generation.setup_logging()
    _stop_resources = resource_monitor.start()
    log = logging.getLogger("local_video_ui.desktop")
    log.info("COMFY_ROOT=%s", config.COMFY_ROOT)
    log.info("ComfyUI %s", comfy_client.server_http_url())

    pq = PersistentJobQueue()
    stop_worker = threading.Event()
    worker_running = [False]

    root = tk.Tk()
    root.title("Local video — prompt queue")
    root.minsize(560, 560)
    root.geometry("720x620")

    frm = ttk.Frame(root, padding=12)
    frm.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frm, text="Describe the video (add each prompt to the queue):").pack(anchor=tk.W)

    prompt_box = scrolledtext.ScrolledText(frm, height=6, wrap=tk.WORD, font=("Segoe UI", 11))
    prompt_box.pack(fill=tk.BOTH, expand=True, pady=(6, 8))
    prompt_box.insert(tk.END, "")

    dur_row = ttk.Frame(frm)
    dur_row.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(dur_row, text="Target length (seconds):").pack(side=tk.LEFT)
    dur_var = tk.DoubleVar(value=float(config.DEFAULT_VIDEO_SECONDS))
    dur_spin = tk.Spinbox(
        dur_row,
        from_=config.MIN_VIDEO_SECONDS,
        to=config.MAX_VIDEO_SECONDS,
        increment=0.25,
        textvariable=dur_var,
        width=10,
        font=("Segoe UI", 10),
    )
    dur_spin.pack(side=tk.LEFT, padx=(8, 0))
    ttk.Label(
        dur_row,
        text=f"(frames snap to Wan rules; ~{config.VIDEO_FPS:.0f} fps)",
        font=("Segoe UI", 8),
        foreground="#555",
    ).pack(side=tk.LEFT, padx=(12, 0))

    audio_row = ttk.Frame(frm)
    audio_row.pack(fill=tk.X, pady=(0, 6))
    add_audio_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        audio_row,
        text="Add realistic background audio (MusicGen instrumental bed + AAC mux)",
        variable=add_audio_var,
    ).pack(anchor=tk.W)

    preview_row = ttk.Frame(frm)
    preview_row.pack(fill=tk.X, pady=(0, 6))
    save_preview_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        preview_row,
        text=f"Save preview PNGs every {int(config.PREVIEW_FRAME_INTERVAL_SEC)}s of video (FFmpeg, same folder as output)",
        variable=save_preview_var,
    ).pack(anchor=tk.W)

    queue_label = ttk.Label(frm, text="Queue (runs in order; saved to disk — survives restart):")
    queue_label.pack(anchor=tk.W, pady=(4, 2))

    queue_frame = ttk.Frame(frm)
    queue_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 6))
    queue_scroll = ttk.Scrollbar(queue_frame)
    queue_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    queue_list = tk.Listbox(
        queue_frame,
        height=6,
        font=("Segoe UI", 9),
        yscrollcommand=queue_scroll.set,
        selectmode=tk.SINGLE,
    )
    queue_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    queue_scroll.config(command=queue_list.yview)

    q_btn_row = ttk.Frame(frm)
    q_btn_row.pack(fill=tk.X, pady=(0, 6))
    add_btn = ttk.Button(q_btn_row, text="Add to queue")
    add_btn.pack(side=tk.LEFT)
    remove_btn = ttk.Button(q_btn_row, text="Remove selected")
    remove_btn.pack(side=tk.LEFT, padx=(8, 0))

    progress_var = tk.DoubleVar(value=0.0)
    bar = ttk.Progressbar(frm, variable=progress_var, maximum=100.0, length=560, mode="determinate")
    bar.pack(fill=tk.X, pady=(0, 8))

    btn_row = ttk.Frame(frm)
    btn_row.pack(fill=tk.X, pady=(0, 8))

    open_btn = ttk.Button(btn_row, text="Open last video", state=tk.DISABLED)
    open_btn.pack(side=tk.LEFT)

    folder_btn = ttk.Button(btn_row, text="Open output folder", state=tk.DISABLED)
    folder_btn.pack(side=tk.LEFT, padx=(8, 0))

    last_video: list[str | None] = [None]

    status = scrolledtext.ScrolledText(frm, height=8, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
    status.pack(fill=tk.BOTH, expand=True)

    def set_status(text: str) -> None:
        status.configure(state=tk.NORMAL)
        status.delete("1.0", tk.END)
        status.insert(tk.END, text)
        status.configure(state=tk.DISABLED)

    def refresh_queue_list() -> None:
        queue_list.delete(0, tk.END)
        jobs = pq.snapshot()
        for i, j in enumerate(jobs):
            prefix = "► " if (worker_running[0] and i == 0) else f"{i + 1}. "
            one_line = j.prompt.replace("\n", " ").strip()
            if len(one_line) > 90:
                one_line = one_line[:87] + "..."
            queue_list.insert(tk.END, prefix + one_line)

    def on_job_done(path: str | None, msg: str) -> None:
        set_status(msg)
        if path:
            progress_var.set(100.0)
            last_video[0] = path
            open_btn.configure(state=tk.NORMAL)
            folder_btn.configure(state=tk.NORMAL)
        else:
            progress_var.set(0.0)

    def safe_progress(p: float) -> None:
        pct = min(100.0, max(0.0, p * 100.0))
        root.after(0, lambda v=pct: progress_var.set(v))

    def add_to_queue() -> None:
        text = prompt_box.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Prompt", "Enter a prompt first.")
            return
        try:
            d = float(dur_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Duration", "Enter a valid number for length (seconds).")
            return
        job = QueuedJob.create(
            text,
            d,
            add_audio=add_audio_var.get(),
            save_preview_frames=save_preview_var.get(),
        )
        pq.add(job)
        refresh_queue_list()
        set_status(
            f"Added to queue (position {len(pq.snapshot())}).\n"
            f"Queue file: {pq.path}\n"
            f"Log: {generation.LOG_FILE}"
        )

    def remove_selected() -> None:
        sel = queue_list.curselection()
        if not sel:
            messagebox.showinfo("Queue", "Select a row to remove.")
            return
        index = int(sel[0])
        if worker_running[0] and index == 0:
            messagebox.showwarning(
                "Queue",
                "Cannot remove the job that is currently running. Wait for it to finish.",
            )
            return
        if not pq.remove_at_index(index):
            messagebox.showerror("Queue", "Could not remove that entry.")
            return
        refresh_queue_list()
        set_status(f"Removed item from queue.\nQueue file: {pq.path}")

    def worker_loop() -> None:
        while not stop_worker.is_set():
            job = pq.wait_peek_first(timeout=0.5)
            if stop_worker.is_set() or pq.is_stopped():
                break
            if job is None:
                continue
            worker_running[0] = True
            root.after(0, lambda: progress_var.set(0.0))
            root.after(0, refresh_queue_list)
            path: str | None = None
            msg = ""
            try:
                path, msg = generation.generate_video_from_prompt(
                    job.prompt,
                    duration_seconds=job.duration_seconds,
                    on_progress=safe_progress,
                    add_audio=job.add_audio,
                    save_preview_frames=job.save_preview_frames,
                )
            except Exception as e:
                log.exception("Generation failed: %s", e)
                path = None
                msg = f"{type(e).__name__}: {e}"
            finally:
                pq.complete_first(job.id)
                worker_running[0] = False
                root.after(0, refresh_queue_list)
                p_final, m_final = path, msg
                root.after(0, lambda: on_job_done(p_final, m_final))

    worker_thread = threading.Thread(target=worker_loop, name="generation-queue-worker", daemon=True)
    worker_thread.start()

    refresh_queue_list()
    if pq.snapshot():
        set_status(
            f"Restored {len(pq.snapshot())} job(s) from queue file.\n"
            f"{pq.path}\n"
            f"Processing will continue automatically.\nLog: {generation.LOG_FILE}"
        )
    else:
        set_status(
            f"Queue file (empty): {pq.path}\n"
            f"Add prompts and click “Add to queue”. Jobs run one at a time.\n"
            f"Log: {generation.LOG_FILE}"
        )

    def on_open_video() -> None:
        p = last_video[0]
        if p and os.path.isfile(p):
            _open_path(p)
        else:
            messagebox.showwarning("No file", "No video path yet.")

    def on_open_folder() -> None:
        p = last_video[0]
        if p and os.path.isfile(p):
            folder = os.path.dirname(os.path.abspath(p))
            _open_path(folder)
        else:
            out_dir = config.COMFY_ROOT / "output" / "local_video_ui"
            if out_dir.is_dir():
                _open_path(str(out_dir))
            else:
                _open_path(str(config.COMFY_ROOT / "output"))

    add_btn.configure(command=add_to_queue)
    remove_btn.configure(command=remove_selected)
    open_btn.configure(command=on_open_video)
    folder_btn.configure(command=on_open_folder)

    ttk.Label(
        frm,
        text=f"ComfyUI: {comfy_client.server_http_url()}  ·  Queue: {pq.path}  ·  Log: {generation.LOG_FILE}",
        font=("Segoe UI", 8),
        foreground="#555",
    ).pack(anchor=tk.W, pady=(6, 0))

    def on_close() -> None:
        stop_worker.set()
        pq.stop()
        _stop_resources()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
