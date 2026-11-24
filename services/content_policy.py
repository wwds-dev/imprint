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
     # Plurals only for nude and sexual: "nudes" yes, but not "sexuality"
     # or "nakedness" in a book topic (re-review P3-2).
     r"\b(explicit|hardcore|porn\w*|nudes?|nudity|naked|"
     r"sex[\s_-]*scenes?|sexual)\b"),
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
# "not any nudity", "no such deepfake", "free of any nudity".
_FILLERS = ("a", "an", "the", "any", "such", "all")
# A negation reaches across a list: "no gore or nudity", "no explicit/sexual
# content", "avoid nudity and explicit scenes" (re-review P2-1).
_CONJUNCTIONS = ("or", "nor", "and", "/")
_MAX_LIST_ITEMS = 3


class ContentPolicyError(ValueError):
    """The request is refused by the local content policy; nothing was sent."""


def _is_policy_word(word: str) -> bool:
    """True for a single word one of the refusal patterns matches."""
    return any(re.fullmatch(pattern.replace(r"\b", ""), word)
               for _key, pattern in PATTERNS[:2])


def _is_negated(text: str, start: int) -> bool:
    """True when the negation governs this match, e.g. 'no nudity'.

    Directly before it, with at most one filler word between ("not any
    nudity"), or at the head of a short list joined by or/nor/and/slash ("no
    gore or nudity"). "no watermark nude photo" negates the watermark, not
    the photo (code review P2-1). Only within the current clause: in "no
    captions, nude model" the "no" belongs to the captions. A hyphen ends a
    word, so "non-explicit" and "no-nudity" are negated (re-review P3-3).
    "and" joins only refused terms ("avoid nudity and explicit scenes"), so
    "not shy and naked" stays refused. Trade-off within the spec's narrowness:
    "no text or nude photo" reads as negated.
    """
    window = text[max(0, start - 64):start]
    tail = re.split(r"[.;,:!?]", window)[-1]
    words = re.findall(r"[a-z]+|/", tail)
    for _ in range(_MAX_LIST_ITEMS):
        if len(words) < 2 or words[-1] not in _CONJUNCTIONS:
            break
        # "and" joins only refused terms ("avoid nudity and explicit
        # scenes"); "not shy and naked" keeps its "naked".
        if words[-1] == "and" and not _is_policy_word(words[-2]):
            break
        words = words[:-2]              # drop "<item> or"
    if words and words[-1] in _FILLERS:
        words = words[:-1]
    if words and words[-1] in _NEGATIONS:
        return True
    # Multi-word forms ("free of nudity") that word-splitting would miss.
    return " ".join(words).endswith(_NEGATION_PHRASES)


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
