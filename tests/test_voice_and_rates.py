"""
Imprint — speech provider requests and per-unit rate lookup
===========================================================
Type: unit, no network (requests.post is replaced).

Two defects found in the 2026-10-07 audit against ElevenLabs' docs:
the provider sent `voice_settings.speaking_rate`, which is not an API field (so
every speed setting was silently ignored), and asked for `eleven_turbo_v2_5`,
which is deprecated. And per-unit rates were read from the editable copy of
config/pricing.json only — a frozen build seeds that copy once, so any rate
added in a later release read as "unknown" and the route was refused.

Run with:  pytest tests/test_voice_and_rates.py -v
"""

import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_elevenlabs_sends_the_documented_fields(monkeypatch, tmp_path):
    import providers.voice.elevenlabs as el
    from providers.voice.base import VoiceConfig
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.update(url=url, body=json)
        return types.SimpleNamespace(raise_for_status=lambda: None,
                                     content=b"ID3fake")

    monkeypatch.setattr(el.requests, "post", fake_post)
    provider = el.ElevenLabsProvider(api_key="test-not-a-real-key")
    provider.synthesize("Hello.", str(tmp_path / "a.mp3"),
                        VoiceConfig(voice_id="v1", speaking_rate=2.0))
    assert sent["body"]["model_id"] == "eleven_flash_v2_5"
    settings = sent["body"]["voice_settings"]
    assert "speaking_rate" not in settings
    assert settings["speed"] == 1.2                    # clamped into 0.7-1.2
    assert sent["url"].endswith("/text-to-speech/v1?output_format=mp3_44100_128")


def test_elevenlabs_rates_are_per_model():
    from services.per_unit_pricing import elevenlabs_rate_usd
    assert elevenlabs_rate_usd("eleven_flash_v2_5") == 0.04
    assert elevenlabs_rate_usd("eleven_multilingual_v2") == 0.08
    assert elevenlabs_rate_usd("eleven_unheard_of") is None     # unknown, not free


def test_a_rate_missing_from_an_old_editable_copy_comes_from_the_bundle(
        monkeypatch, tmp_path):
    import services.per_unit_pricing as pricing
    old_copy = tmp_path / "user_pricing.json"
    old_copy.write_text(json.dumps({"per_unit_usd": {
        "openai_tts_per_1k_chars": 0.5}}))            # an edited, older copy
    bundled = tmp_path / "bundled_pricing.json"
    bundled.write_text(json.dumps({"per_unit_usd": {
        "openai_tts_per_1k_chars": 0.016,
        "elevenlabs_tts": {"eleven_flash_v2_5": 0.04}}}))
    monkeypatch.setattr(pricing, "USER_CONFIG_PATH", old_copy)
    monkeypatch.setattr(pricing, "CONFIG_PATH", bundled)
    monkeypatch.setattr("services.database.get_setting", lambda *a, **k: "")
    assert pricing.rate_usd("openai_tts_per_1k_chars") == 0.5      # copy wins
    assert pricing.rate_usd("elevenlabs_tts", "eleven_flash_v2_5") == 0.04
    assert pricing.rate_usd("nothing_like_this") is None
