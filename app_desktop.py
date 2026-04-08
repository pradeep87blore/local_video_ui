"""
Minimal desktop UI (Tkinter): prompt + duration + Generate — no browser, no node graph.
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

    root = tk.Tk()
    root.title("Local video — prompt")
    root.minsize(520, 460)
    root.geometry("680x520")

    frm = ttk.Frame(root, padding=12)
    frm.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frm, text="Describe the video (one prompt only):").pack(anchor=tk.W)

    prompt_box = scrolledtext.ScrolledText(frm, height=7, wrap=tk.WORD, font=("Segoe UI", 11))
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

    progress_var = tk.DoubleVar(value=0.0)
    bar = ttk.Progressbar(frm, variable=progress_var, maximum=100.0, length=560, mode="determinate")
    bar.pack(fill=tk.X, pady=(0, 8))

    btn_row = ttk.Frame(frm)
    btn_row.pack(fill=tk.X, pady=(0, 8))

    run_btn = ttk.Button(btn_row, text="Generate video")
    run_btn.pack(side=tk.LEFT)

    open_btn = ttk.Button(btn_row, text="Open last video", state=tk.DISABLED)
    open_btn.pack(side=tk.LEFT, padx=(8, 0))

    folder_btn = ttk.Button(btn_row, text="Open output folder", state=tk.DISABLED)
    folder_btn.pack(side=tk.LEFT, padx=(8, 0))

    last_video: list[str | None] = [None]

    status = scrolledtext.ScrolledText(frm, height=8, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 10))
    status.pack(fill=tk.BOTH, expand=True)

    def set_status(text: str) -> None:
        status.configure(state=tk.NORMAL)
        status.delete("1.0", tk.END)
        status.insert(tk.END, text)
        status.configure(state=tk.DISABLED)

    def on_done(path: str | None, msg: str) -> None:
        run_btn.configure(state=tk.NORMAL)
        set_status(msg)
        if path:
            progress_var.set(100.0)
            last_video[0] = path
            open_btn.configure(state=tk.NORMAL)
            folder_btn.configure(state=tk.NORMAL)
        else:
            progress_var.set(0.0)
            last_video[0] = None
            open_btn.configure(state=tk.DISABLED)
            folder_btn.configure(state=tk.DISABLED)

    def safe_progress(p: float) -> None:
        pct = min(100.0, max(0.0, p * 100.0))
        root.after(0, lambda v=pct: progress_var.set(v))

    def run_generate() -> None:
        text = prompt_box.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Prompt", "Enter a prompt first.")
            return
        try:
            d = float(dur_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Duration", "Enter a valid number for length (seconds).")
            return
        run_btn.configure(state=tk.DISABLED)
        progress_var.set(0.0)
        set_status("Working…\nLog: " + str(generation.LOG_FILE))

        def work() -> None:
            path, msg = generation.generate_video_from_prompt(
                text,
                duration_seconds=d,
                on_progress=safe_progress,
                add_audio=add_audio_var.get(),
            )
            root.after(0, lambda: on_done(path, msg))

        threading.Thread(target=work, daemon=True).start()

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

    run_btn.configure(command=run_generate)
    open_btn.configure(command=on_open_video)
    folder_btn.configure(command=on_open_folder)

    ttk.Label(
        frm,
        text=f"ComfyUI: {comfy_client.server_http_url()}  ·  Log: {generation.LOG_FILE}",
        font=("Segoe UI", 8),
        foreground="#555",
    ).pack(anchor=tk.W, pady=(6, 0))

    def on_close() -> None:
        _stop_resources()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
