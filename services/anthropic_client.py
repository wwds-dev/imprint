import os

from services.api_limits import REQUEST_TIMEOUT_SECONDS, MAX_RETRIES

try:
    import anthropic as _sdk
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False


def _usage(usage) -> dict:
    """Token counts as the usage tracker reads them.

    Anthropic reports `input_tokens` *excluding* prompt-cache reads and
    writes, which come back separately. The tracker treats input_tokens as
    the whole prompt and bills the `cached_input_tokens` slice at the cached
    rate, so the three are added up and the reads named.
    """
    read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    written = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    return {
        "input_tokens": int(usage.input_tokens or 0) + read + written,
        "output_tokens": int(usage.output_tokens or 0),
        "cached_input_tokens": read,
    }


def _raise_on_refusal(message) -> None:
    """A declined request is an error, not an empty answer.

    Claude Opus 5.5, Sonnet 5.5 and Fable 5.1 run safety classifiers that can
    stop a turn with stop_reason "refusal" (HTTP 200). Returning its empty
    text made a refusal look like a blank reply.
    """
    if message is None or getattr(message, "stop_reason", None) != "refusal":
        return
    details = getattr(message, "stop_details", None)
    category = getattr(details, "category", None) if details else None
    explanation = getattr(details, "explanation", None) if details else None
    reason = f" ({category})" if category else ""
    raise RuntimeError(
        f"The model declined this request{reason}."
        + (f" {explanation}" if explanation else "")
        + "\n→ Rephrase the request, or pick another model.")


class AnthropicClientWrapper:
    # Offline fallback, checked against the provider's model list on 2026-10-07.
    # Every id here needs its own row in config/pricing.json
    # (tests/test_settings_pricing.py fails otherwise).
    # The claude-3 family is retired (the last on 2026-04-20). This client
    # sends no temperature, thinking config or assistant prefill, all of
    # which the 5.x models reject.
    KNOWN_MODELS = [
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-fable-5-1",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-6",
        "claude-sonnet-4-6",
    ]
    DEFAULT_MODEL = "claude-sonnet-5-5"

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = (
            _sdk.Anthropic(
                api_key=api_key,
                timeout=REQUEST_TIMEOUT_SECONDS,
                max_retries=MAX_RETRIES,
            )
            if _HAS_SDK and api_key
            else None
        )

    @staticmethod
    def key_available() -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY", ""))

    def list_models(self) -> list[str]:
        try:
            return self.list_models_live()
        except Exception:
            return self.KNOWN_MODELS

    def list_models_live(self) -> list[str]:
        """Live ids, or an exception — no silent fallback.

        The async model refresh must be able to tell a live answer from a
        failure: swallowing the error here made the worker cache
        KNOWN_MODELS as this session's live list, never retried. A no-key
        client still returns KNOWN_MODELS (that IS the correct answer),
        and so does an empty listing.
        """
        if not self.client:
            return self.KNOWN_MODELS
        result = self.client.models.list()
        models = sorted(m.id for m in result.data)
        return models if models else self.KNOWN_MODELS

    # test_connection() was removed here and in the Qwen wrapper: nothing
    # called either (the API-keys status card reads key_available() only),
    # and wiring one up would have made an unguarded paid call.

    def stream_chat(self, messages: list, model: str = "claude-sonnet-5-5"):
        if not self.client:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Add it to your .env file and restart the app."
            )
        system, chat_messages = self._split(messages)
        kwargs = {"model": model, "max_tokens": 8096, "messages": chat_messages}
        if system:
            kwargs["system"] = system

        def _gen(out):
            yield from self._stream(kwargs, out)

        from services.stream_usage import UsageStream
        return UsageStream(_gen)

    def _stream(self, kwargs, out):
        try:
            with self.client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text
                # The final message carries the real token counts; without
                # this the whole stream was billed on the chars/4 estimate.
                try:
                    final = stream.get_final_message()
                    if final is not None and final.usage is not None:
                        out.usage = _usage(final.usage)
                except Exception:
                    final = None    # usage is best-effort; the text streamed
                _raise_on_refusal(final)
        except _sdk.AuthenticationError:
            raise RuntimeError(
                "AuthenticationError (401) — API key invalid or expired.\n"
                "→ Go to console.anthropic.com → API Keys and generate a new key,\n"
                "  then update ANTHROPIC_API_KEY in your .env file."
            )
        except _sdk.APIConnectionError:
            raise RuntimeError(
                "APIConnectionError — Could not reach api.anthropic.com.\n"
                "→ Check your internet connection.\n"
                "→ If your key is new, make sure it has been activated.\n"
                "→ Check that no firewall or VPN is blocking outbound HTTPS."
            )
        except _sdk.RateLimitError:
            raise RuntimeError(
                "RateLimitError (429) — Too many requests.\n"
                "→ Wait a moment and try again.\n"
                "→ Check your usage limits at console.anthropic.com."
            )
        except _sdk.NotFoundError:
            raise RuntimeError(
                f"NotFoundError (404) — Model '{model}' does not exist.\n"
                "→ Select a different model from the dropdown."
            )
        except _sdk.APIStatusError as e:
            raise RuntimeError(
                f"APIStatusError ({e.status_code}) — {e.message}"
            )

    def chat(self, messages: list, model: str = "claude-sonnet-5-5"):
        if not self.client:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Add it to your .env file and restart the app."
            )
        system, chat_messages = self._split(messages)
        kwargs = {"model": model, "max_tokens": 8096, "messages": chat_messages}
        if system:
            kwargs["system"] = system
        try:
            response = self.client.messages.create(**kwargs)
        except _sdk.AuthenticationError:
            raise RuntimeError(
                "AuthenticationError (401) — API key invalid or expired.\n"
                "→ Go to console.anthropic.com → API Keys and generate a new key,\n"
                "  then update ANTHROPIC_API_KEY in your .env file."
            )
        except _sdk.APIConnectionError:
            raise RuntimeError(
                "APIConnectionError — Could not reach api.anthropic.com.\n"
                "→ Check your internet connection.\n"
                "→ If your key is new, make sure it has been activated.\n"
                "→ Check that no firewall or VPN is blocking outbound HTTPS."
            )
        except _sdk.RateLimitError:
            raise RuntimeError(
                "RateLimitError (429) — Too many requests.\n"
                "→ Wait a moment and try again."
            )
        except _sdk.NotFoundError:
            raise RuntimeError(
                f"NotFoundError (404) — Model '{model}' does not exist.\n"
                "→ Select a different model from the dropdown."
            )
        except _sdk.APIStatusError as e:
            raise RuntimeError(
                f"APIStatusError ({e.status_code}) — {e.message}"
            )
        _raise_on_refusal(response)
        usage = _usage(response.usage)
        # content can be empty (max_tokens exhausted before any text block)
        # and can carry more than one text block; indexing [0] crashed on the
        # first case and silently dropped the rest on the second.
        text = "".join(
            block.text for block in response.content
            if getattr(block, "type", "") == "text")
        return text, usage

    def _split(self, messages: list) -> tuple[str, list]:
        system = ""
        chat = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat.append({"role": msg["role"], "content": msg["content"]})
        return system, chat
