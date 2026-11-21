"""Keeping "on this Mac" true for local model runtimes (Imprint only).

`services/providers.py` and `services/lmstudio_client.py` are byte-for-byte
copies shared with Sentinel (`tests/test_providers_drift.py`), so the release
kit's local-endpoint checks and the capped, proxy-free LM Studio stream live
here instead:

- `NO_PROXIES` (security S-1): passed as `proxies=` on a local request, so an
  HTTP(S)_PROXY / ALL_PROXY variable or a macOS system proxy cannot carry it,
  and the book in it, to the proxy host. requests merges the environment's
  proxies under the ones passed and then drops every key whose value is
  None, so these three keys switch every proxy off.
- `url_host` / `is_plain_endpoint` (security S-2): the host is read with
  urllib3, the parser requests dials with, and an address the two parsers
  could read differently is refused.
- `LocalLMStudioClient`: the shared client plus `max_tokens` (review P2-3),
  `stop_reason` and no proxies on its stream.
"""

from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlparse

import requests
from urllib3.util import parse_url

from services import lmstudio_client
from services.lmstudio_client import LMStudioClient
from services.output_limits import stop_kind
from services.stream_usage import UsageStream

NO_PROXIES = {"http": None, "https": None, "all": None}


def url_host(url: str) -> str:
    """The host requests will dial for `url` ("" when there is none)."""
    try:
        return (parse_url(url or "").host or "").strip("[]")
    except ValueError:
        return ""


def is_loopback_host(host: str) -> bool:
    """True for an address that can only be this machine."""
    if (host or "").casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_plain_endpoint(url: str) -> bool:
    """No user info, backslash or percent-encoding, and both URL parsers
    agree on the host: `urlparse` reads `http://evil.com\\@127.0.0.1` as
    127.0.0.1 while requests dials evil.com."""
    text = url or ""
    if "\\" in text or "%" in text:
        return False
    netloc = text.split("://", 1)[-1].split("/", 1)[0]
    if "@" in netloc:
        return False
    return url_host(text) == (urlparse(text).hostname or "")


class LocalLMStudioClient(LMStudioClient):
    """The shared LM Studio client with a capped, proxy-free stream."""

    def stream_chat(self, model: str, messages: list[dict],
                    max_tokens: int | None = None, **_ignored):
        payload = self._payload(model, messages, True)
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
        url = f"{self.base_url}/chat/completions"
        timeout = (lmstudio_client.CONNECT_TIMEOUT, lmstudio_client.READ_TIMEOUT)

        def _gen(out):
            try:
                with requests.post(url, json=payload, stream=True,
                                   proxies=NO_PROXIES, timeout=timeout) as response:
                    response.raise_for_status()
                    for raw in response.iter_lines():
                        if not raw:
                            continue
                        line = raw.decode("utf-8")
                        if not line.startswith("data:"):
                            continue
                        body = line[5:].strip()
                        if body == "[DONE]":
                            break
                        data = json.loads(body)
                        if data.get("error"):
                            raise RuntimeError(
                                f"LM Studio stopped mid-reply: {data['error']}")
                        choice = (data.get("choices") or [{}])[0]
                        if choice.get("finish_reason"):
                            out.stop_reason = stop_kind(choice["finish_reason"])
                        delta = choice.get("delta", {})
                        if delta.get("content"):
                            yield delta["content"]
            except requests.RequestException as exc:
                raise RuntimeError(f"LM Studio streaming request failed: {exc}")
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"LM Studio streaming JSON parse failed: {exc}")

        return UsageStream(_gen)
