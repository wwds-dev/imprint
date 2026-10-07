import os
from openai import OpenAI

from services.api_limits import REQUEST_TIMEOUT_SECONDS, MAX_RETRIES
from services.stream_usage import UsageStream, cached_input_tokens


class DeepSeekClientWrapper:
    # Offline fallback, checked against the provider's model list on 2026-10-07.
    # Every id here needs its own row in config/pricing.json
    # (tests/test_settings_pricing.py fails otherwise).
    # deepseek-chat / deepseek-reasoner were discontinued on 2026-07-24, and
    # deepseek-v4-flash is a legacy name routed to deepseek-flash (V4.1).
    KNOWN_MODELS = [
        "deepseek-flash",
        "deepseek-v4-pro",
    ]
    DEFAULT_MODEL = "deepseek-flash"

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.client = (
            OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com",
                timeout=REQUEST_TIMEOUT_SECONDS,
                max_retries=MAX_RETRIES,
            )
            if self.api_key
            else None
        )

    @staticmethod
    def key_available():
        return bool(os.getenv("DEEPSEEK_API_KEY"))

    def list_models(self) -> list[str]:
        """Available model ids, from the API when reachable.

        Falls back to KNOWN_MODELS with no key or on any API error so the model
        dropdowns are never left empty.
        """
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

    def chat(self, messages, model="deepseek-flash"):
        if not self.client:
            raise RuntimeError("DEEPSEEK_API_KEY is not set.")

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
        )

        text = response.choices[0].message.content or ""

        usage = {
            "input_tokens": response.usage.prompt_tokens if response.usage else 0,
            "output_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }

        return text, usage

    def generate(self, prompt, model="deepseek-flash"):
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages=messages, model=model)
    
    def stream_chat(self, messages, model="deepseek-flash"):
        if not self.client:
            raise RuntimeError("DEEPSEEK_API_KEY is not set.")

        def _gen(out):
            try:
                stream = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    # The provider's real token counts arrive in a final
                    # usage-only frame; without this every stream was billed
                    # on the chars/4 estimate (and cached-input billing could
                    # never fire).
                    stream_options={"include_usage": True},
                )
                for chunk in stream:
                    usage = getattr(chunk, "usage", None)
                    if usage:
                        out.usage = {
                            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
                            "cached_input_tokens": cached_input_tokens(usage),
                        }
                    # OpenAI-compatible endpoints legitimately emit chunks with an
                    # empty choices array (content filters, usage-only frames);
                    # indexing [0] blindly crashed the stream mid-response.
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
            except Exception as e:
                raise RuntimeError(f"DeepSeek streaming request failed: {e}")

        return UsageStream(_gen)