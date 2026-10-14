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


def test_elevenlabs_voices_come_from_the_paginated_endpoint(monkeypatch):
    import providers.voice.elevenlabs as el
    pages = [
        {"voices": [{"voice_id": "a", "name": "Ana"}], "has_more": True,
         "next_page_token": "p2"},
        {"voices": [{"voice_id": "b", "name": "Ben"}], "has_more": False},
    ]
    asked = []

    def fake_get(url, headers=None, params=None, timeout=None):
        asked.append((url, dict(params)))
        page = pages.pop(0)
        return types.SimpleNamespace(raise_for_status=lambda: None,
                                     json=lambda: page)

    monkeypatch.setattr(el.requests, "get", fake_get)
    voices = el.ElevenLabsProvider(api_key="test-not-a-real-key").list_voices()
    assert [v["id"] for v in voices] == ["a", "b"]
    assert all(url == "https://api.elevenlabs.io/v2/voices" for url, _ in asked)
    assert asked[1][1]["next_page_token"] == "p2"


def test_a_dated_rate_applies_from_its_date():
    from services.per_unit_pricing import dated_rate_usd
    rate = lambda day: dated_rate_usd("gemini_tts_per_minute",
                                      "gemini-3.8-flash-tts", day)
    assert rate("2026-12-31") == 0.0137
    assert rate("2027-01-01") == 0.0272


# ── Qwen endpoint honesty (readiness gate 2026-10-09) ────────────────────────

def test_qwen_says_when_it_is_on_the_standard_host(monkeypatch):
    from services import qwen_client

    monkeypatch.delenv("DASHSCOPE_BASE_URL", raising=False)
    assert qwen_client.on_legacy_endpoint()
    note = qwen_client.endpoint_note()
    assert "ap-southeast-1" in note and "maintenance" not in note

    monkeypatch.setenv("DASHSCOPE_BASE_URL",
                       "https://ws-abc123.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1")
    assert not qwen_client.on_legacy_endpoint()
    assert qwen_client.endpoint_note() == ""

    monkeypatch.setenv("DASHSCOPE_BASE_URL", qwen_client.CHINA_BASE_URL)
    assert not qwen_client.on_legacy_endpoint(), "the mainland host is not the legacy one"


# ── Qwen workspace id (spec dashscope-workspace-id) ──────────────────────────

WS1_URL = "https://ws1.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"


@pytest.fixture
def clean_dashscope(monkeypatch):
    for name in ("DASHSCOPE_BASE_URL", "DASHSCOPE_VIDEO_BASE_URL", "DASHSCOPE_WORKSPACE_ID"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_workspace_id_derives_chat_url(clean_dashscope):
    from services import qwen_client

    clean_dashscope.setenv("DASHSCOPE_WORKSPACE_ID", "ws1")
    assert qwen_client._base_url() == WS1_URL
    assert qwen_client.endpoint_note() == ""


_HOSTILE_IDS = ["a.evil.com", "evil.com/", "x@evil.com", "x#.", "ws1:443", "ws 1",
                "ws_1", "ws1%2f", "ws\\1", "ws\n1", "-ws", "ws-", "a" * 64, "wsа",
                "wsK",                       # Kelvin sign: lower() would fold it to "k"
                "https://ws1.ap-southeast-1.maas.aliyuncs.com"]


@pytest.mark.parametrize("bad", _HOSTILE_IDS)
def test_hostile_workspace_ids_never_reach_a_url(clean_dashscope, bad):
    from services import qwen_client

    clean_dashscope.setenv("DASHSCOPE_WORKSPACE_ID", bad)
    assert qwen_client.valid_workspace_id(bad) is None
    url = qwen_client._base_url()
    assert url == qwen_client.INTL_BASE_URL
    assert bad.strip() not in url


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_blank_workspace_id_is_unset_not_invalid(clean_dashscope, blank):
    from services import qwen_client

    clean_dashscope.setenv("DASHSCOPE_WORKSPACE_ID", blank)
    assert qwen_client.valid_workspace_id(blank) is None
    assert qwen_client._base_url() == qwen_client.INTL_BASE_URL
    note = qwen_client.endpoint_note()
    assert "Set DASHSCOPE_WORKSPACE_ID" in note and "not used" not in note


def test_workspace_id_is_stripped_and_lowercased(clean_dashscope):
    from services import qwen_client

    assert qwen_client.valid_workspace_id("ws1\n") == "ws1"
    assert qwen_client.valid_workspace_id(" WS1 ") == "ws1"
    assert qwen_client.valid_workspace_id("a" * 63) == "a" * 63
    # an ASCII punycode label is still one plain label under the fixed suffix
    assert qwen_client.valid_workspace_id("xn--ws1") == "xn--ws1"
    clean_dashscope.setenv("DASHSCOPE_WORKSPACE_ID", "xn--ws1")
    assert qwen_client._base_url() == \
        "https://xn--ws1.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    # the URL is built from the validated label, never the raw value
    clean_dashscope.setenv("DASHSCOPE_WORKSPACE_ID", " WS1 ")
    assert qwen_client._base_url() == WS1_URL


def test_note_says_why_a_set_workspace_id_is_not_used(clean_dashscope):
    from services import qwen_client

    clean_dashscope.setenv("DASHSCOPE_WORKSPACE_ID", "a.evil.com")
    note = qwen_client.endpoint_note()
    assert "Workspace ID not used" in note and "letters, digits and hyphens only" in note
    assert "a.evil.com" not in note and "Set DASHSCOPE_WORKSPACE_ID" not in note
    # an explicit chat endpoint takes priority, so the ID is not the note's subject
    clean_dashscope.setenv("DASHSCOPE_BASE_URL", qwen_client.CHINA_BASE_URL)
    assert qwen_client.endpoint_note() == ""


@pytest.mark.parametrize("ws", ["ws1", "a.evil.com", ""])
def test_an_explicit_standard_host_url_says_it_overrides_the_id(clean_dashscope, ws):
    """Setting the ID changes nothing while DASHSCOPE_BASE_URL names the
    standard host, so the note must not ask for it."""
    from services import qwen_client

    clean_dashscope.setenv("DASHSCOPE_WORKSPACE_ID", ws)
    clean_dashscope.setenv("DASHSCOPE_BASE_URL", qwen_client.INTL_BASE_URL)
    assert qwen_client._base_url() == qwen_client.INTL_BASE_URL
    note = qwen_client.endpoint_note()
    assert "DASHSCOPE_BASE_URL is set and overrides the workspace ID" in note
    assert "clear it to use DASHSCOPE_WORKSPACE_ID" in note
    assert "Set DASHSCOPE_WORKSPACE_ID to use it" not in note
    assert "Workspace ID not used" not in note and "a.evil.com" not in note
    assert "ap-southeast-1" in note


@pytest.mark.parametrize("url,expect", [
    ("https://ws1.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1", True),
    ("HTTPS://WS1.AP-SOUTHEAST-1.MAAS.ALIYUNCS.COM/compatible-mode/v1", True),
    ("https://x.maas.aliyuncs.com.evil.com/v1", False),
    ("https://evil.com\\@a.maas.aliyuncs.com/", False),
    ("https://evil.example/maas.aliyuncs.com", False),
    ("https://[::1/v1", False),                  # urlparse raises: no host
    ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", False),
    ("", False)])
def test_is_workspace_host_compares_the_parsed_host(url, expect):
    from services import qwen_client

    assert qwen_client.is_workspace_host(url) is expect


def test_legacy_endpoint_compares_the_parsed_host(clean_dashscope):
    from services import qwen_client

    clean_dashscope.setenv("DASHSCOPE_BASE_URL", "https://my.example/dashscope-intl.aliyuncs.com/v1")
    assert not qwen_client.on_legacy_endpoint()
    clean_dashscope.setenv("DASHSCOPE_BASE_URL", "https://DASHSCOPE-INTL.aliyuncs.com/compatible-mode/v1")
    assert qwen_client.on_legacy_endpoint()


@pytest.mark.parametrize("url,unencrypted,foreign", [
    ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", False, False),
    ("https://ws1.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1", False, False),
    ("http://dashscope.aliyuncs.com/compatible-mode/v1", True, False),
    ("https://my.example/v1", False, True),
    ("http://evil.example/v1", True, True),
    ("https://x.aliyuncs.com.evil.com/v1", False, True),
    ("https://evilaliyuncs.com/v1", False, True),  # a suffix match needs the dot
    ("http://localhost:8080/v1", False, True),   # http to this Mac is not flagged as unencrypted
    ("http://127.0.0.1:8080/v1", False, True),
    ("", False, False)])
def test_endpoint_warning_flags_http_and_foreign_hosts(url, unencrypted, foreign):
    from services import qwen_client

    warning = qwen_client.endpoint_warning(url)
    assert ("unencrypted" in warning) is unencrypted
    assert ("not an Alibaba Cloud host" in warning) is foreign
    assert bool(warning) is (unencrypted or foreign)
    assert url == "" or url not in warning, "the address itself is never echoed"


def test_explicit_endpoint_warning_reaches_the_note_and_never_blocks(clean_dashscope):
    from services import qwen_client

    for unreadable in ("https://evil.com\\@a.maas.aliyuncs.com/", "dashscope.aliyuncs.com/v1"):
        assert "plain https:// web address" in qwen_client.endpoint_warning(unreadable)

    clean_dashscope.setenv("DASHSCOPE_BASE_URL", "http://my.example/v1")
    clean_dashscope.setenv("DASHSCOPE_VIDEO_BASE_URL", qwen_client.INTL_VIDEO_BASE_URL)
    warning = qwen_client.explicit_endpoint_warning()
    assert warning.startswith("DASHSCOPE_BASE_URL is not https")
    assert "DASHSCOPE_VIDEO_BASE_URL" not in warning and "my.example" not in warning
    assert qwen_client._base_url() == "http://my.example/v1", "a warning, not a block"
    assert qwen_client.endpoint_note() == warning

    clean_dashscope.setenv("DASHSCOPE_BASE_URL", "")
    clean_dashscope.setenv("DASHSCOPE_VIDEO_BASE_URL", "https://v.example/api/v1")
    note = qwen_client.endpoint_note()
    assert note.startswith("DASHSCOPE_VIDEO_BASE_URL is not an Alibaba Cloud host")
    assert "Set DASHSCOPE_WORKSPACE_ID" in note, "the standard-host note still follows"
    assert qwen_client.video_base_url() == "https://v.example/api/v1"

    clean_dashscope.setenv("DASHSCOPE_VIDEO_BASE_URL", "")
    assert qwen_client.explicit_endpoint_warning() == ""


def test_no_id_is_byte_identical(clean_dashscope):
    from services import qwen_client

    assert qwen_client._base_url() == qwen_client.INTL_BASE_URL
    assert qwen_client.video_base_url() == qwen_client.INTL_VIDEO_BASE_URL
    note = qwen_client.endpoint_note()
    assert "ap-southeast-1" in note and "maintenance" not in note


@pytest.mark.parametrize("ws", ["", "ws1"])
@pytest.mark.parametrize("url,expect", [
    ("https://my.example/v1", "https://my.example/v1"),
    ("", None), ("   ", None)])
def test_explicit_urls_win_and_blank_is_unset(clean_dashscope, ws, url, expect):
    from services import qwen_client

    clean_dashscope.setenv("DASHSCOPE_WORKSPACE_ID", ws)
    clean_dashscope.setenv("DASHSCOPE_BASE_URL", url)
    clean_dashscope.setenv("DASHSCOPE_VIDEO_BASE_URL", url)
    if expect:
        assert qwen_client._base_url() == expect
        assert qwen_client.video_base_url() == expect
    else:
        assert qwen_client._base_url() == (WS1_URL if ws else qwen_client.INTL_BASE_URL)
        # chat only: the id never changes the video base; blank means default
        assert qwen_client.video_base_url() == qwen_client.INTL_VIDEO_BASE_URL


def test_video_base_strips_trailing_slash(clean_dashscope):
    from services import qwen_client

    clean_dashscope.setenv("DASHSCOPE_VIDEO_BASE_URL", "https://v.example/api/v1/")
    assert qwen_client.video_base_url() == "https://v.example/api/v1"


def test_probe_uses_typed_workspace_id(clean_dashscope):
    from services import api_keys

    before = dict(os.environ)
    client, note = api_keys.prepare_probe(
        "qwen", {"DASHSCOPE_API_KEY": "test-not-a-real-key", "DASHSCOPE_WORKSPACE_ID": "ws1"})
    assert note == "" and client.base_url == WS1_URL
    assert dict(os.environ) == before


def test_a_blank_typed_workspace_id_masks_the_saved_one(clean_dashscope):
    from services import api_keys, qwen_client

    clean_dashscope.setenv("DASHSCOPE_WORKSPACE_ID", "ws1")
    client, note = api_keys.prepare_probe(
        "qwen", {"DASHSCOPE_API_KEY": "test-not-a-real-key",
                 "DASHSCOPE_WORKSPACE_ID": "", "DASHSCOPE_BASE_URL": ""})
    assert note == "" and client.base_url == qwen_client.INTL_BASE_URL
    assert os.environ["DASHSCOPE_WORKSPACE_ID"] == "ws1", "the process keeps its own"


def test_image_endpoint_uses_the_video_resolver(clean_dashscope):
    from services import image_generation, qwen_client

    tail = "/services/aigc/multimodal-generation/generation"
    clean_dashscope.setenv("DASHSCOPE_WORKSPACE_ID", "ws1")
    assert image_generation._qwen_endpoint() == qwen_client.INTL_VIDEO_BASE_URL + tail
    clean_dashscope.setenv("DASHSCOPE_VIDEO_BASE_URL", "https://v.example/api/v1/")
    assert image_generation._qwen_endpoint() == "https://v.example/api/v1" + tail


def test_workspace_401_hint(clean_dashscope):
    from services import api_keys, qwen_client

    assert "different workspace" in qwen_client.workspace_auth_hint(WS1_URL)
    assert qwen_client.workspace_auth_hint(qwen_client.INTL_BASE_URL) == ""
    assert qwen_client.workspace_auth_hint("https://evil.example/maas.aliyuncs.com") == ""
    lookalike = "https://x.maas.aliyuncs.com.evil.com/compatible-mode/v1"
    assert qwen_client.workspace_auth_hint(lookalike) == ""
    assert qwen_client.workspace_auth_hint("https://evil.com\\@a.maas.aliyuncs.com/") == ""

    class Boom(Exception):
        status_code = 401

    class Fake:
        def __init__(self, base_url):
            self.base_url = base_url

        def list_models_live(self):
            raise Boom("Incorrect API key sk-secret-value")

    ok, note = api_keys.run_probe("qwen", Fake(WS1_URL))
    assert not ok and "different workspace" in note and "sk-secret" not in note
    ok, note = api_keys.run_probe("qwen", Fake(qwen_client.INTL_BASE_URL))
    assert not ok and note.startswith("Boom") and "different workspace" not in note
    ok, note = api_keys.run_probe("qwen", Fake(lookalike))
    assert not ok and note.startswith("Boom") and "different workspace" not in note


def test_workspace_401_hint_from_the_sdks_own_error(clean_dashscope):
    """The exception the OpenAI SDK really raises on 401, not a stand-in."""
    import httpx
    import openai
    from services import api_keys, qwen_client

    request = httpx.Request("GET", WS1_URL + "/models")
    response = httpx.Response(401, request=request,
                              json={"error": {"message": "Incorrect API key sk-secret-value"}})
    error = openai.AuthenticationError("Error code: 401 - Incorrect API key sk-secret-value",
                                       response=response, body=None)
    assert error.status_code == 401

    class Fake:
        def __init__(self, base_url):
            self.base_url = base_url

        def list_models_live(self):
            raise error

    ok, note = api_keys.run_probe("qwen", Fake(WS1_URL))
    assert not ok and "different workspace" in note and "sk-secret" not in note
    ok, note = api_keys.run_probe("qwen", Fake(qwen_client.INTL_BASE_URL))
    assert not ok and note.startswith("AuthenticationError") and "different workspace" not in note


def test_only_a_401_on_a_workspace_host_gets_the_workspace_hint(clean_dashscope):
    """A server error or a dropped connection is not a key mismatch."""
    import httpx
    import openai
    from services import api_keys

    request = httpx.Request("GET", WS1_URL + "/models")
    server_error = openai.InternalServerError(
        "Error code: 500 - upstream unavailable", response=httpx.Response(500, request=request), body=None)
    assert server_error.status_code == 500

    for error, expect in ((server_error, "InternalServerError: Error code: 500 - upstream unavailable"),
                          (ConnectionError("connection reset by peer"),
                           "ConnectionError: connection reset by peer")):
        class Fake:
            base_url = WS1_URL

            def list_models_live(self, error=error):
                raise error

        ok, note = api_keys.run_probe("qwen", Fake())
        assert not ok and note == expect, "the generic text, not the 401 hint"


def test_write_values_saves_workspace_id(tmp_path):
    import stat
    from services import api_keys

    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=keep-me\n")
    api_keys.write_values({"DASHSCOPE_WORKSPACE_ID": "ws1"}, env)
    text = env.read_text()
    assert "DASHSCOPE_WORKSPACE_ID=ws1" in text and "OPENAI_API_KEY=keep-me" in text
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
