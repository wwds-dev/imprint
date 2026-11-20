"""render_short takes an explicit voice provider (spec one-click-release, E3)."""

from __future__ import annotations

from pathlib import Path

from agents.manuscript import shorts_generator


class _Voice:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, output_path, config=None):
        self.calls.append((text, config.voice_id))
        Path(output_path).write_bytes(b"mp3")
        return output_path


def test_an_explicit_provider_is_used_and_the_environment_is_not_read(
        tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "set-but-unused")
    monkeypatch.setattr(shorts_generator, "get_voice_provider",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    ffmpeg = []
    monkeypatch.setattr(shorts_generator, "_ffmpeg",
                        lambda *args: ffmpeg.append(args) or Path(args[-1]).write_bytes(b"mp4"))
    voice = _Voice()
    out = shorts_generator.render_short(
        "A line.", tmp_path / "g.png", tmp_path / "s.mp4",
        use_elevenlabs=True, voice_id="Samantha", voice_provider=voice)
    assert out.read_bytes() == b"mp4"
    assert voice.calls == [("A line.", "Samantha")]
    assert not (tmp_path / "s.mp3").exists()


def test_without_a_provider_the_old_choice_stands(tmp_path, monkeypatch):
    chosen = []
    voice = _Voice()
    monkeypatch.setattr(shorts_generator, "get_voice_provider",
                        lambda use_elevenlabs=False: chosen.append(use_elevenlabs) or voice)
    monkeypatch.setattr(shorts_generator, "_ffmpeg",
                        lambda *args: Path(args[-1]).write_bytes(b"mp4"))
    shorts_generator.render_short("A line.", tmp_path / "g.png", tmp_path / "s.mp4")
    assert chosen == [False]
