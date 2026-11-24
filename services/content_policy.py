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
import unicodedata

# (key, pattern). The key picks the reason; a provider can word its own.
# Each word also matches its own inflections and spacings ("nudes",
# "undressed", "face-swap", "deep fakes"): the same words, not new ones
# (security review P1-2, 2026-11-24).
PATTERNS: tuple[tuple[str, str], ...] = (
    ("explicit",
     r"\b(explicit|hardcore|porn\w*|nude\w*|nudity|naked\w*|"
     r"sex[\s_-]*scenes?|sexual\w*)\b"),
    ("identity",
     r"\b(deep[\s_-]*fake\w*|face[\s_-]*swap\w*|undress\w*|deep[\s_-]*nude\w*)\b"),
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
# Words that may sit between a negation and the term it negates:
# "not any nudity", "no such deepfake".
_FILLERS = ("a", "an", "the", "any", "such", "all")


class ContentPolicyError(ValueError):
    """The request is refused by the local content policy; nothing was sent."""


def _is_negated(text: str, start: int) -> bool:
    """True when the negation governs this match, e.g. 'no nudity'.

    Only directly before it, with at most one filler word between ("not any
    nudity"): "no watermark nude photo" negates the watermark, not the
    photo (code review P2-1). And only within the current clause: in "no
    captions, nude model" the "no" belongs to the captions.
    """
    window = text[max(0, start - 32):start]
    tail = re.split(r"[.;,:!?]", window)[-1]
    words = re.findall(r"[a-z-]+", tail)
    if words and words[-1] in _NEGATIONS:
        return True
    if len(words) >= 2 and words[-2] in _NEGATIONS and words[-1] in _FILLERS:
        return True
    # Multi-word forms ("free of nudity") that word-splitting would miss.
    return tail.rstrip().endswith(_NEGATION_PHRASES)


def _normalise(prompt: str | None) -> str:
    """Lower case, compatibility forms folded, invisible characters dropped.

    Fullwidth letters and ligatures fold to plain ones (NFKC), and zero-width
    joiners, soft hyphens and other format characters are removed, so they
    cannot split a word past the patterns (security review P2-2). Look-alike
    letters from other scripts are not folded: a residual risk the spec
    accepts by keeping this check narrow.
    """
    text = unicodedata.normalize("NFKC", prompt or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return text.casefold()


def refused_key(prompt: str | None) -> str | None:
    """The PATTERNS key the prompt breaks, or None if it may be sent."""
    text = _normalise(prompt)
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
