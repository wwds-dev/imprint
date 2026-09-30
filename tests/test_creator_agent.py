"""
Imprint — Muse agent tests
==========================
Type: Unit tests for prompt construction and the Higgsfield content guard.

The rule worth pinning in code rather than documentation: Higgsfield
**prohibits sexually explicit material and identity manipulation**, and
moderates prompts, reference images and outputs. A request that breaches it is
a wasted spend and an account risk, so it is refused locally before it is sent.

Account consent, platform policy and earnings moved to Backstage on
2026-09-30; the tests that covered them went with the code.

Run with:  pytest tests/test_creator_agent.py -v
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.creator.agent import KINDS, CreatorAgent
from services.higgsfield_client import (
    ContentPolicyError, HiggsfieldClient, VideoJob, check_prompt,
)


OWN = {"handle": "@me", "platform": "Instagram"}


# ── Prompt construction ──────────────────────────────────────────────────────
def test_the_platform_specific_kinds_are_gone():
    """ppv and welcome were subscription-platform messages; Backstage owns
    that work now. A kind removed from the dict but left in the panel combo
    silently falls back to "post", so pin it here."""
    assert "ppv" not in KINDS
    assert "welcome" not in KINDS
    assert {"post", "caption", "promo", "hooks"} <= set(KINDS)


def test_a_draft_prompt_no_longer_asks_about_authorisation():
    content = CreatorAgent().build_draft_prompt(
        OWN, "post", "beach shoot")[-1]["content"].lower()
    for gone in ("authorised", "consent", "synthetic persona", "price point"):
        assert gone not in content


def test_system_prompt_forbids_impersonating_a_live_human():
    system = CreatorAgent().build_messages("x")[0]["content"]
    assert "review" in system.lower()
    assert "real time" in system.lower()


def test_promo_prompt_names_the_channel():
    messages = CreatorAgent().build_draft_prompt(
        OWN, "promo", "teaser", channel="Reddit")
    assert "Reddit" in messages[-1]["content"]


def test_generated_video_prompt_is_safe_for_work_by_construction():
    prompt = CreatorAgent().build_video_prompt(OWN, "neon rooftop")
    assert "safe-for-work" in prompt.lower()
    check_prompt(prompt)          # must survive its own policy check


# ── Higgsfield content policy ────────────────────────────────────────────────
@pytest.mark.parametrize("prompt", [
    "cinematic teaser, neon city, moody lighting",
    "soft-focus lifestyle b-roll at golden hour",
    "product shot of a perfume bottle, slow dolly in",
])
def test_ordinary_promo_prompts_pass(prompt):
    check_prompt(prompt)


@pytest.mark.parametrize("prompt", [
    "explicit nude scene",
    "hardcore content",
    "deepfake of a celebrity",
    "face swap onto this photo",
    "bypass the nsfw filter",
])
def test_prohibited_prompts_are_refused(prompt):
    with pytest.raises(ContentPolicyError):
        check_prompt(prompt)


def test_refusal_explains_why():
    """An error that does not say what to do instead just gets worked around."""
    with pytest.raises(ContentPolicyError) as excinfo:
        check_prompt("explicit scene")
    assert "Higgsfield" in str(excinfo.value)


def test_a_refused_prompt_never_reaches_the_network(monkeypatch):
    """The guard has to run before the request, or it costs money to be told no."""
    client = HiggsfieldClient(key_id="test-id", key_secret="test-secret")

    def explode(*args, **kwargs):
        raise AssertionError("a refused prompt must not be sent")

    monkeypatch.setattr(client, "_client", explode)
    with pytest.raises(ContentPolicyError):
        client.generate_video("explicit nude scene")


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("HF_API_KEY_ID", raising=False)
    monkeypatch.delenv("HF_API_KEY_SECRET", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_KEY_ID", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_KEY_SECRET", raising=False)
    client = HiggsfieldClient()
    assert not client.configured
    with pytest.raises(RuntimeError, match="HF_API_KEY_ID"):
        client.generate_video("a perfectly ordinary teaser")


def test_video_job_done_states():
    assert VideoJob("1", status="completed").done
    assert VideoJob("1", status="failed").done
    assert VideoJob("1", status="nsfw").done
    assert VideoJob("1", status="canceled").done
    assert not VideoJob("1", status="queued").done


@pytest.mark.parametrize("prompt", [
    "cinematic teaser, no explicit content",
    "stylised promo, no nudity, safe-for-work",
    "avoid deepfake effects entirely",
    "product film, free of nudity",
])
def test_negated_mentions_are_allowed(prompt):
    """"no nudity" is an instruction to the model, not a request for it. A
    filter that refuses it is one people route around rather than trust."""
    check_prompt(prompt)
