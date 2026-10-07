"""One call for every implemented image route: OpenAI, Gemini and Qwen.

Stamp's logo concepts and the video pipeline's scene images used to be wired
to OpenAI's GPT Image models alone, so the image assessment compared three
OpenAI models and nothing else. Gemini (Nano Banana) and Alibaba (Qwen Image)
both sell image generation on keys Imprint already holds; this module is the
single place a model id becomes a request, so a caller never needs to know
which provider it is talking to.

Each request is sent exactly once. A paid image is never replayed
automatically: OpenAI's wrapper and DashScope's plain HTTP call have no
retries, and Gemini goes through services.gemini_client.one_attempt_client,
which switches off the Interactions layer's own retry. Request shapes are from
the providers' docs, checked 2026-10-07:
  Gemini  ai.google.dev/gemini-api/docs/image-generation (Interactions API)
  Qwen    alibabacloud.com/help/en/model-studio/qwen-image-generation-and-editing-api-reference
"""

from __future__ import annotations

import base64
import os

import requests

from services.media_catalog import MODELS

# Requests wait this long: an image takes tens of seconds, and DashScope's own
# server limit is 300 seconds.
IMAGE_TIMEOUT_SECONDS = 300

# The shapes every route can make, and how each provider is asked for them.
ASPECTS = ("1:1", "3:2", "2:3", "16:9", "9:16", "4:3", "3:4")
_OPENAI_SIZES = {"1:1": "1024x1024", "3:2": "1536x1024", "2:3": "1024x1536",
                 "16:9": "1536x1024", "9:16": "1024x1536", "4:3": "1536x1024",
                 "3:4": "1024x1536"}
# DashScope takes any "W*H" with an area from 512² to 2048²; these are about
# one megapixel, on multiples of 16, at each ratio.
_QWEN_SIZES = {"1:1": "1024*1024", "3:2": "1248*832", "2:3": "832*1248",
               "16:9": "1376*768", "9:16": "768*1376", "4:3": "1152*864",
               "3:4": "864*1152"}


class ImageRefused(RuntimeError):
    """The provider rejected the key or the account: retrying cannot help."""


def provider_for(model_id: str) -> str | None:
    """"OpenAI", "Gemini" or "Qwen" for an image model id, else None."""
    return next((m.provider for m in MODELS
                 if m.kind == "scene_images" and m.model_id == model_id), None)


def image_models() -> tuple[str, ...]:
    return tuple(m.model_id for m in MODELS if m.kind == "scene_images")


def aspect_for_size(size: str) -> str:
    """The supported ratio nearest to a "WxH" size, e.g. "1536x1024" -> "3:2"."""
    try:
        width, height = (int(n) for n in str(size).lower().split("x"))
        ratio = width / height
    except (ValueError, ZeroDivisionError):
        return "1:1"

    def value(aspect):
        w, h = (int(n) for n in aspect.split(":"))
        return w / h
    return min(ASPECTS, key=lambda aspect: abs(value(aspect) - ratio))


def generate_image(model_id: str, prompt: str, *, aspect: str = "1:1",
                   openai_client=None, quality: str = "medium") -> bytes:
    """One image from `model_id`, as encoded bytes (PNG or JPEG)."""
    provider = provider_for(model_id)
    if aspect not in ASPECTS:
        aspect = "1:1"
    if provider == "OpenAI":
        if openai_client is None:
            from services.openai_client import OpenAIClientWrapper
            openai_client = OpenAIClientWrapper()
        return openai_client.generate_image(
            prompt, size=_OPENAI_SIZES[aspect], model=model_id)
    if provider == "Gemini":
        return _gemini_image(model_id, prompt, aspect)
    if provider == "Qwen":
        return _qwen_image(model_id, prompt, aspect)
    raise ValueError(f"No image route for {model_id!r}.")


# ── Gemini (Nano Banana) ────────────────────────────────────────────────────

def _gemini_image(model_id: str, prompt: str, aspect: str,
                  *, httpx_client=None) -> bytes:
    from services.gemini_client import _gemini_api_key, one_attempt_client

    key = _gemini_api_key()
    if not key:
        raise ImageRefused("GOOGLE_API_KEY (or GEMINI_API_KEY) is not set.")
    client = one_attempt_client(key, timeout_ms=IMAGE_TIMEOUT_SECONDS * 1000,
                                httpx_client=httpx_client)
    try:
        interaction = client.interactions.create(
            model=model_id, input=prompt, store=False,
            response_format={"type": "image", "aspect_ratio": aspect,
                             "image_size": "1K"})
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        body = getattr(exc, "body", None)
        code = (body.get("error", {}).get("code", "")
                if isinstance(body, dict) else "")
        if status in (401, 402, 403) or code in (
                "quota_exceeded", "failed_precondition", "payment_required"):
            raise ImageRefused(f"Gemini refused the request ({status} {code}).") from exc
        raise
    image = getattr(interaction, "output_image", None)
    data = getattr(image, "data", None) if image is not None else None
    if not data:
        raise RuntimeError(
            f"Gemini returned no image ({getattr(interaction, 'status', '?')}).")
    return base64.b64decode(data)


# ── Qwen Image (DashScope) ──────────────────────────────────────────────────

def _qwen_endpoint() -> str:
    base = os.getenv("DASHSCOPE_VIDEO_BASE_URL",
                     "https://dashscope-intl.aliyuncs.com/api/v1").rstrip("/")
    return f"{base}/services/aigc/multimodal-generation/generation"


# DashScope error codes that mean the key or the account, not the moment.
_QWEN_REFUSALS = {"InvalidApiKey", "Arrearage", "AllocationQuota.FreeTierOnly",
                  "Throttling.AllocationQuota", "DataInspectionFailed"}


def _qwen_image(model_id: str, prompt: str, aspect: str) -> bytes:
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise ImageRefused("DASHSCOPE_API_KEY is not set.")
    # No X-DashScope-Async header: qwen-image-3.0-pro answers 429 to it.
    response = requests.post(
        _qwen_endpoint(), timeout=IMAGE_TIMEOUT_SECONDS,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json={"model": model_id,
              "input": {"messages": [{"role": "user",
                                      "content": [{"text": prompt}]}]},
              "parameters": {"size": _QWEN_SIZES[aspect], "n": 1,
                             "prompt_extend": True, "watermark": False}})
    try:
        data = response.json()
    except ValueError:
        data = {}
    code = data.get("code") or ""
    if response.status_code != 200 or code:
        message = data.get("message") or response.text[:200]
        if response.status_code in (401, 403) or code in _QWEN_REFUSALS:
            raise ImageRefused(f"Qwen refused the request ({code}): {message}")
        raise RuntimeError(f"Qwen image failed ({response.status_code} {code}): "
                           f"{message}")
    urls = [part["image"]
            for choice in data.get("output", {}).get("choices", [])
            for part in choice.get("message", {}).get("content", [])
            if "image" in part]
    if not urls:
        raise RuntimeError("Qwen returned no image.")
    # The result URL is valid for 24 hours; fetch it now.
    download = requests.get(urls[0], timeout=120)
    download.raise_for_status()
    return download.content
