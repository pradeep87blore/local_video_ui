"""
Gradio UI (optional): open http://127.0.0.1:7860 — same backend as app_desktop.py.
"""
from __future__ import annotations

import logging
import sys

import gradio as gr

import comfy_client
import config
import generation
import resource_monitor


def _generate(
    positive_prompt: str,
    duration_sec: float,
    add_audio: bool,
    progress: gr.Progress = gr.Progress(),
):
    def cb(p: float) -> None:
        progress(p, desc="Generating video…")

    return generation.generate_video_from_prompt(
        positive_prompt,
        duration_seconds=duration_sec,
        on_progress=cb,
        add_audio=add_audio,
    )


def main() -> None:
    generation.setup_logging()
    resource_monitor.start()
    log = logging.getLogger("local_video_ui")
    log.info("COMFY_ROOT=%s", config.COMFY_ROOT)
    log.info("ComfyUI URL %s", comfy_client.server_http_url())

    with gr.Blocks(title="Local Video (ComfyUI)") as demo:
        gr.Markdown(
            "### Local text-to-video\n"
            "Enter a description and target length. "
            "ComfyUI must already be running. "
            f"Log file: `{generation.LOG_FILE}`."
        )
        prompt = gr.Textbox(
            label="Prompt",
            placeholder="Describe the video you want (subject, motion, style, lighting)…",
            lines=4,
        )
        duration = gr.Number(
            label="Target length (seconds)",
            value=config.DEFAULT_VIDEO_SECONDS,
            minimum=config.MIN_VIDEO_SECONDS,
            maximum=config.MAX_VIDEO_SECONDS,
            step=0.25,
        )
        add_audio = gr.Checkbox(
            label="Add realistic background audio (MusicGen + FFmpeg mux)",
            value=True,
        )
        go = gr.Button("Generate", variant="primary")
        video = gr.Video(label="Output", interactive=False)
        status = gr.Textbox(label="Status / path", lines=8)

        go.click(
            fn=_generate,
            inputs=[prompt, duration, add_audio],
            outputs=[video, status],
        )

    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, show_error=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
