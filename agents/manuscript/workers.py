"""Background worker threads owned by the Press workspace.

Moved here from ui/workers.py with the shorts pipeline: the host still
holds each instance as ``host.shorts_worker`` so the umbrella shutdown
sweep sees it.
"""

from pathlib import Path

from PySide6.QtCore import Signal

from ui.worker_registry import TrackedThread


class ShortsWorker(TrackedThread):
    """Narrates a quote and renders it into a short vertical MP4."""
    status_signal = Signal(str)
    done_signal = Signal(str)   # output video path
    error_signal = Signal(str)

    def __init__(self, quote: str, image_path: Path, output_path: Path,
                 use_elevenlabs: bool, voice_id: str):
        super().__init__()
        self.quote = quote
        self.image_path = image_path
        self.output_path = output_path
        self.use_elevenlabs = use_elevenlabs
        self.voice_id = voice_id
        self._cancel_requested = False

    def cancel(self):
        """Stop before the next step (quit only; Press has no Stop button).

        The narration call itself cannot be interrupted; the render after it
        is skipped. ffmpeg on one still image takes seconds.
        """
        self._cancel_requested = True

    def run(self):
        from agents.manuscript.shorts_generator import render_short
        try:
            self.status_signal.emit("[Narrating…]")
            render_short(
                self.quote, self.image_path, self.output_path,
                use_elevenlabs=self.use_elevenlabs, voice_id=self.voice_id,
                should_stop=lambda: self._cancel_requested,
            )
            self.done_signal.emit(str(self.output_path))
        except Exception as e:
            self.error_signal.emit(str(e))
