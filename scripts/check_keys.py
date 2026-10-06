#!/usr/bin/env python3
"""Which providers are actually usable right now.

Run before a paid test pass:

    .venv/bin/python scripts/check_keys.py

Two different questions, and the difference matters. "Set" only means a value
is present in the environment or the .env; "reachable" means the provider
accepted it. A typo, a revoked key and a key for the wrong account all look
identical until something asks the provider.

The reachability probe lists each provider's models. That is a metadata call,
not a generation: it costs nothing and bills nothing. Nothing here prints a key,
a prefix or a length -- only whether one is present.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv                                   # noqa: E402

load_dotenv(ROOT / ".env")

# (label, env names any one of which satisfies it, probe)
# A probe returns (ok, note). None means "presence is all we can check here".
PROVIDERS: list[tuple[str, tuple[str, ...], str | None]] = [
    ("Anthropic",  ("ANTHROPIC_API_KEY",),                   "anthropic"),
    ("OpenAI",     ("OPENAI_API_KEY",),                      "openai"),
    ("Gemini",     ("GEMINI_API_KEY", "GOOGLE_API_KEY"),     "gemini"),
    ("DeepSeek",   ("DEEPSEEK_API_KEY",),                    "deepseek"),
    ("Kimi",       ("KIMI_API_KEY",),                        "kimi"),
    ("Qwen",       ("DASHSCOPE_API_KEY",),                   "qwen"),
    ("Higgsfield", ("HF_API_KEY_ID", "HIGGSFIELD_API_KEY_ID"), None),
    ("ElevenLabs", ("ELEVENLABS_API_KEY",),                   None),
    ("Ollama",     (),                                       "ollama"),
]

# Publishing credentials are all-or-nothing per platform, so they are reported
# as a set rather than probed -- a probe would mean posting something.
PUBLISHERS: list[tuple[str, tuple[str, ...]]] = [
    ("Reddit",    ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
                   "REDDIT_USERNAME", "REDDIT_PASSWORD")),
    ("Pinterest", ("PINTEREST_ACCESS_TOKEN",)),
]


def _probe(kind: str) -> tuple[bool, str]:
    """List models for one provider. Metadata only; never generates."""
    try:
        if kind == "ollama":
            from services.ollama_client import OllamaClient
            models = OllamaClient().list_models()
            return bool(models), (f"{len(models)} model(s) pulled"
                                  if models else "daemon up but nothing pulled")
        if kind == "anthropic":
            from services.anthropic_client import AnthropicClient
            models = AnthropicClient().list_models()
        elif kind == "openai":
            from services.openai_client import OpenAIClient
            models = OpenAIClient().list_models()
        elif kind == "gemini":
            from services.gemini_client import GeminiClient
            models = GeminiClient().list_models()
        elif kind == "deepseek":
            from services.deepseek_client import DeepSeekClient
            models = DeepSeekClient().list_models()
        elif kind == "kimi":
            from services.kimi_client import KimiClient
            models = KimiClient().list_models()
        elif kind == "qwen":
            from services.qwen_client import QwenClient
            models = QwenClient().list_models()
        else:
            return False, "no probe"
        return bool(models), f"{len(models)} model(s)"
    except Exception as exc:
        # The message can carry a provider's own echo of a request, so report
        # the type and a short reason rather than the whole thing.
        reason = str(exc).splitlines()[0][:70] if str(exc) else ""
        return False, f"{type(exc).__name__}: {reason}" if reason else type(exc).__name__


def main() -> int:
    env_file = ROOT / ".env"
    print(f"Imprint key check   .env: "
          f"{'found' if env_file.exists() else 'MISSING — copy .env.example'}\n")

    print("Model providers")
    usable = 0
    for label, names, probe in PROVIDERS:
        present = [n for n in names if os.getenv(n)]
        if names and not present:
            print(f"  {'—':4} {label:12} not set            ({' or '.join(names)})")
            continue
        if probe is None:
            print(f"  {'set':4} {label:12} set, not probed    "
                  f"(no metadata endpoint; first render is the test)")
            usable += 1
            continue
        ok, note = _probe(probe)
        print(f"  {'OK' if ok else 'FAIL':4} {label:12} "
              f"{'reachable' if ok else 'unreachable':18} ({note})")
        usable += bool(ok)

    print(f"\n  {usable} provider(s) usable.")

    print("\nHerald publishing (optional — drafting needs none of these)")
    for label, names in PUBLISHERS:
        missing = [n for n in names if not os.getenv(n)]
        if not missing:
            print(f"  {'OK':4} {label:12} complete")
        elif len(missing) == len(names):
            print(f"  {'—':4} {label:12} not set")
        else:
            print(f"  {'FAIL':4} {label:12} incomplete — missing "
                  f"{', '.join(missing)}")

    print("\nNotes: Booth narrates with OpenAI TTS, so audiobooks need\n"
          "OPENAI_API_KEY specifically. ElevenLabs is used by one thing, the\n"
          "narration in Press's Shorts tab, and falls back to a mock voice\n"
          "without a key. YouTube uses no key here: it needs a Google Cloud\n"
          "Desktop OAuth client_secret*.json in vidforge's secrets folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
