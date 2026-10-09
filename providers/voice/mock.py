from __future__ import annotations
import os
import subprocess
import platform
from typing import Optional
from .base import VoiceProvider, VoiceConfig


class NoOnDeviceVoice(RuntimeError):
    """The free on-device narrator could not produce speech.

    Raised instead of writing anything, so a Short is never assembled over
    silence and presented as finished. The message names what was missing
    (the speech engine or ffmpeg) and, for ffmpeg, the tail of its stderr.
    """


class MockVoiceProvider(VoiceProvider):
    """
    Local TTS using the OS speech engine (no API key needed). The panel calls
    this the free on-device narrator (`providers.voice.registry.SYSTEM_SOURCE`).

    macOS: `say` → AIFF → MP3 via ffmpeg.
    Linux: `espeak` → WAV → MP3 via ffmpeg.

    It never fabricates audio. Until 2026-10-09 every failure here — no `say`,
    no `espeak`, an unsupported platform, a failed encode — fell back to a
    silent MP3 of about the right length and returned it as a success, so a
    Short rendered with no narration and no error (readiness audit, item 12).
    Now every failure raises `NoOnDeviceVoice`; the Shorts worker routes that
    to the panel's error path, which also releases any reservation.
    """

    @property
    def name(self) -> str:
        return "mock"

    def list_voices(self) -> list[dict]:
        if platform.system() == "Darwin":
            result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
            voices = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if parts:
                    voices.append({"id": parts[0], "name": parts[0], "preview_url": None})
            return voices[:10]
        return [{"id": "default", "name": "System TTS", "preview_url": None}]

    def synthesize(
        self,
        text: str,
        output_path: str,
        config: Optional[VoiceConfig] = None,
    ) -> str:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        system = platform.system()
        if system == "Darwin":
            return self._synthesize_macos(text, output_path, config)
        if system == "Linux":
            return self._synthesize_linux(text, output_path)
        raise NoOnDeviceVoice(
            f"No on-device speech engine is available on {system}; choose "
            "another narrator.")

    # ── engines ──────────────────────────────────────────────────────────────

    def _synthesize_macos(self, text: str, output_path: str, config: Optional[VoiceConfig]) -> str:
        voice = config.voice_id if config and config.voice_id != "default" else "Samantha"
        rate = int(180 * (config.speaking_rate if config else 1.0))

        aiff_path = output_path.replace(".mp3", ".aiff").replace(".wav", ".aiff")
        if not aiff_path.endswith(".aiff"):
            aiff_path += ".aiff"

        say_cmd = ["say", "-v", voice, "-r", str(rate), "-o", aiff_path, text]
        self._run_engine(say_cmd, "say", aiff_path)
        try:
            self._encode(aiff_path, output_path)
        finally:
            if os.path.exists(aiff_path):
                os.remove(aiff_path)
        return output_path

    def _synthesize_linux(self, text: str, output_path: str) -> str:
        wav_path = output_path.replace(".mp3", ".wav")
        if not wav_path.endswith(".wav"):
            wav_path += ".wav"

        self._run_engine(["espeak", "-w", wav_path, text], "espeak", wav_path)
        try:
            self._encode(wav_path, output_path)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)
        return output_path

    # ── failure is an exception, never a file ────────────────────────────────

    @staticmethod
    def _run_engine(cmd: list[str], engine: str, produced: str) -> None:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            raise NoOnDeviceVoice(
                f"The on-device narrator needs `{engine}`, which is not "
                "installed; choose another narrator.") from None
        if result.returncode != 0 or not os.path.exists(produced):
            detail = (result.stderr or "").strip().splitlines()
            reason = detail[-1][:200] if detail else f"exit {result.returncode}"
            raise NoOnDeviceVoice(
                f"`{engine}` produced no speech ({reason}); nothing was saved.")

    @staticmethod
    def _encode(source: str, output_path: str) -> None:
        cmd = ["ffmpeg", "-y", "-i", source,
               "-codec:a", "libmp3lame", "-qscale:a", "2", output_path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            raise NoOnDeviceVoice(
                "Encoding the narration needs ffmpeg, which is not installed "
                "(scripts/check_setup.py lists what is missing).") from None
        if result.returncode != 0 or not os.path.exists(output_path):
            tail = (result.stderr or "").strip()[-300:]
            raise NoOnDeviceVoice(
                f"ffmpeg could not encode the narration; nothing was saved. {tail}")
