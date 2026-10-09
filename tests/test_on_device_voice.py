"""The free on-device narrator speaks or fails — it never writes silence.

Found by the 2026-10-09 readiness audit (READINESS_GATE item 12):
`providers/voice/mock.py` answered every failure — no `say`, no `espeak`, an
unsupported platform, a failed ffmpeg encode — with `_silent_audio()`, an MP3 of
roughly the right length containing nothing, returned as a success. The Shorts
worker then assembled the video over it and reported "[Done] Saved …". A quote
graphic with a silent soundtrack is not a Short; it is a defect that looks
like a deliverable.

Every failure now raises `NoOnDeviceVoice`. `agents/manuscript/workers.py`
already routes any exception to `_on_short_error`, which shows it and releases
the reservation, so nothing else had to change.

Mutation check: restore a `return output_path` in place of any raise below and
the matching test fails. Run with:  pytest tests/test_on_device_voice.py -v
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from providers.voice.base import VoiceConfig
from providers.voice.mock import MockVoiceProvider, NoOnDeviceVoice


class FakeRun:
    """Stand-in for subprocess.run: scripted per-executable behaviour.

    behaviour[exe] is one of: "ok" (exit 0 and write the output file the
    command names), "fail" (exit 1 with stderr), "missing" (FileNotFoundError),
    or "ok-nofile" (exit 0 but write nothing — a lying engine).
    """

    def __init__(self, behaviour: dict[str, str]):
        self.behaviour = behaviour
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        exe = cmd[0]
        mode = self.behaviour.get(exe, "ok")
        if mode == "missing":
            raise FileNotFoundError(exe)
        if mode == "fail":
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=f"{exe}: boom")
        if mode == "ok":
            # say -o <file>, espeak -w <file>, ffmpeg ... <file>: the output is
            # the argument after -o/-w, or the last argument for ffmpeg.
            if "-o" in cmd:
                out = cmd[cmd.index("-o") + 1]
            elif "-w" in cmd:
                out = cmd[cmd.index("-w") + 1]
            else:
                out = cmd[-1]
            Path(out).write_bytes(b"\x00" * 16)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


@pytest.fixture
def provider():
    return MockVoiceProvider()


def _patch(monkeypatch, system: str, behaviour: dict[str, str]) -> FakeRun:
    fake = FakeRun(behaviour)
    monkeypatch.setattr("providers.voice.mock.subprocess.run", fake)
    monkeypatch.setattr("providers.voice.mock.platform.system", lambda: system)
    return fake


# ── failures raise and leave nothing behind ──────────────────────────────────

def test_macos_without_say_raises_and_writes_nothing(provider, tmp_path, monkeypatch):
    _patch(monkeypatch, "Darwin", {"say": "missing"})
    out = tmp_path / "short.mp3"
    with pytest.raises(NoOnDeviceVoice, match="`say`"):
        provider.synthesize("hello world", str(out))
    assert not out.exists()
    assert list(tmp_path.iterdir()) == [], "no partial or silent file may remain"


def test_macos_say_failure_raises_with_its_reason(provider, tmp_path, monkeypatch):
    _patch(monkeypatch, "Darwin", {"say": "fail"})
    with pytest.raises(NoOnDeviceVoice, match="boom"):
        provider.synthesize("hello", str(tmp_path / "short.mp3"))
    assert list(tmp_path.iterdir()) == []


def test_an_engine_that_exits_zero_but_writes_nothing_is_a_failure(provider, tmp_path, monkeypatch):
    _patch(monkeypatch, "Darwin", {"say": "ok-nofile"})
    with pytest.raises(NoOnDeviceVoice, match="produced no speech"):
        provider.synthesize("hello", str(tmp_path / "short.mp3"))


def test_macos_ffmpeg_failure_raises_and_removes_the_aiff(provider, tmp_path, monkeypatch):
    _patch(monkeypatch, "Darwin", {"say": "ok", "ffmpeg": "fail"})
    out = tmp_path / "short.mp3"
    with pytest.raises(NoOnDeviceVoice, match="ffmpeg"):
        provider.synthesize("hello", str(out))
    assert not out.exists()
    assert not (tmp_path / "short.aiff").exists(), "temp AIFF must be cleaned up on failure"


def test_missing_ffmpeg_names_the_setup_check(provider, tmp_path, monkeypatch):
    _patch(monkeypatch, "Darwin", {"say": "ok", "ffmpeg": "missing"})
    with pytest.raises(NoOnDeviceVoice, match="check_setup"):
        provider.synthesize("hello", str(tmp_path / "short.mp3"))


def test_linux_without_espeak_raises(provider, tmp_path, monkeypatch):
    _patch(monkeypatch, "Linux", {"espeak": "missing"})
    with pytest.raises(NoOnDeviceVoice, match="`espeak`"):
        provider.synthesize("hello", str(tmp_path / "short.mp3"))
    assert list(tmp_path.iterdir()) == []


def test_unsupported_platform_raises_rather_than_inventing_audio(provider, tmp_path, monkeypatch):
    fake = _patch(monkeypatch, "Windows", {})
    with pytest.raises(NoOnDeviceVoice, match="Windows"):
        provider.synthesize("hello", str(tmp_path / "short.mp3"))
    assert fake.calls == [], "nothing may be run on a platform with no engine"


def test_no_code_path_writes_silence(provider):
    """The old fallback is gone, not merely unreachable."""
    assert not hasattr(provider, "_silent_audio")
    import inspect
    source = inspect.getsource(type(provider).__module__ and __import__(
        "providers.voice.mock", fromlist=["x"]))
    assert "anullsrc" not in source, "a silent-audio generator is back in mock.py"


# ── the success path is unchanged ────────────────────────────────────────────

def test_macos_success_returns_the_mp3_and_cleans_up(provider, tmp_path, monkeypatch):
    fake = _patch(monkeypatch, "Darwin", {"say": "ok", "ffmpeg": "ok"})
    out = tmp_path / "short.mp3"
    result = provider.synthesize("hello world", str(out),
                                 VoiceConfig(voice_id="Daniel", speaking_rate=1.5))
    assert result == str(out)
    assert out.exists()
    assert not (tmp_path / "short.aiff").exists()
    say = fake.calls[0]
    assert say[:3] == ["say", "-v", "Daniel"]
    assert say[say.index("-r") + 1] == str(int(180 * 1.5))
    assert fake.calls[1][0] == "ffmpeg"


def test_default_voice_and_rate_on_macos(provider, tmp_path, monkeypatch):
    fake = _patch(monkeypatch, "Darwin", {"say": "ok", "ffmpeg": "ok"})
    provider.synthesize("hello", str(tmp_path / "s.mp3"))
    say = fake.calls[0]
    assert say[say.index("-v") + 1] == "Samantha"
    assert say[say.index("-r") + 1] == "180"


def test_linux_success_encodes_the_wav(provider, tmp_path, monkeypatch):
    fake = _patch(monkeypatch, "Linux", {"espeak": "ok", "ffmpeg": "ok"})
    out = tmp_path / "s.mp3"
    assert provider.synthesize("hello", str(out)) == str(out)
    assert out.exists() and not (tmp_path / "s.wav").exists()
    assert fake.calls[0][0] == "espeak" and fake.calls[1][0] == "ffmpeg"


def test_voice_list_off_macos_is_the_single_system_entry(provider, monkeypatch):
    monkeypatch.setattr("providers.voice.mock.platform.system", lambda: "Linux")
    assert provider.list_voices() == [{"id": "default", "name": "System TTS", "preview_url": None}]
