"""
Imprint — Gemini paid requests are sent exactly once
====================================================
Type: unit, offline (an httpx MockTransport answers every request).

The Interactions API (Omni video, image and speech output) ignores
HttpRetryOptions(attempts=1) on google-genai 2.21.0 and retries a 408/409/429/5xx
once, so a server error on a paid render was billed twice. one_attempt_client
switches that layer's retries off; this proves it on the wire.

Run with:  pytest tests/test_gemini_one_attempt.py -v
"""

import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_a_failed_interaction_is_posted_once():
    from services.gemini_client import one_attempt_client
    posts = []

    def handler(request):
        posts.append(str(request.url))
        return httpx.Response(503, json={"error": {
            "code": 503, "message": "unavailable", "status": "UNAVAILABLE"}})

    client = one_attempt_client(
        "test-not-a-real-key", timeout_ms=2000,
        httpx_client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(Exception):
        client.interactions.create(model="gemini-omni-1.1-flash", input="a calm sea")
    assert len(posts) == 1, posts
