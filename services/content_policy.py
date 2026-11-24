"""The one prompt check every image and video route runs before it sends.

Refused locally, before anything is reserved or spent: sexually explicit
material, identity manipulation of real people ("deepfake", "face swap",
"undress") and attempts to get around a provider's moderation (spec
ai-act-safeguards; EU AI Act Art. 5 as amended for intimate images, lawyer
trigger T5 decides whether this is enough).

Deliberately narrow. It catches the unambiguous cases rather than trying to
be a general content classifier: a broad keyword filter on a creative tool
mostly produces false positives and teaches people to work around it. Words
that flip the meaning ("no nudity", "free of nudity") let a prompt through.

Pure, standard library only, no Qt, no network: cheap enough for the UI
thread before a request and for a worker thread as a backstop.
"""

from __future__ import annotations

import re

# (key, pattern). The key picks the reason; a provider can word its own.
PATTERNS: tuple[tuple[str, str], ...] = (
    ("explicit",
     r"\b(explicit|hardcore|pornographic|porn|nude|nudity|naked|sex scene|sexual)\b"),
    ("identity",
     r"\b(deepfake|face swap|faceswap|undress|deep nude|deepnude)\b"),
    ("circumvent",
     r"\b(bypass|circumvent|jailbreak|evade)\b.{0,24}\b(filter|moderation|safety|nsfw)\b"),
)

REASONS: dict[str, str] = {
    "explicit": ("Imprint Studio does not generate sexually explicit images or "
                 "video. Generate safe-for-work material only."),
    "identity": ("Imprint Studio does not generate deepfakes, face swaps or "
                 "undressed images of real people."),
    "circumvent": ("Imprint Studio does not send requests that try to get "
                   "around a provider's moderation."),
}

# Words that flip the meaning of what follows. "no explicit content" is a
# perfectly good instruction to a model, and a filter that refuses it is a
# filter people learn to route around rather than one that protects anything.
_NEGATIONS = ("no", "not", "non", "none", "nothing", "neither", "without",
              "avoid", "never", "excluding", "exclude", "omit", "zero")
_NEGATION_PHRASES = ("free of", "devoid of", "clear of")


class ContentPolicyError(ValueError):
    """The request is refused by the local content policy; nothing was sent."""


def _is_negated(text: str, start: int) -> bool:
    """True when the match is preceded by a negation, e.g. 'no nudity'.

    Only within the current clause: "explicit shots, no captions" negates the
    captions, not the shots, so the window stops at the last punctuation.
    """
    window = text[max(0, start - 24):start]
    tail = re.split(r"[.;,]", window)[-1]
    words = re.findall(r"[a-z-]+", tail)
    if any(word in _NEGATIONS for word in words[-3:]):
        return True
    # Multi-word forms ("free of nudity") that word-splitting would miss.
    return any(phrase in tail for phrase in _NEGATION_PHRASES)


def refused_key(prompt: str | None) -> str | None:
    """The PATTERNS key the prompt breaks, or None if it may be sent."""
    text = (prompt or "").lower()
    for key, pattern in PATTERNS:
        for match in re.finditer(pattern, text):
            if not _is_negated(text, match.start()):
                return key
    return None


def refusal(prompt: str | None) -> str | None:
    """Why the prompt may not be sent, in words for the user; None if it may."""
    key = refused_key(prompt)
    return REASONS[key] if key else None


def check_prompt(prompt: str | None) -> None:
    """Raise ContentPolicyError if the prompt may not be sent."""
    reason = refusal(prompt)
    if reason:
        raise ContentPolicyError(reason)
