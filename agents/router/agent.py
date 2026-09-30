"""Intent router implementation owned by the internal Router package.

Two ways in. **Intent** is the substring table below: what the user wants done,
in their own words. **Address** is naming the tool — "open Booth", "use Quill" —
which became necessary when the agents were relabelled to codenames on
2026-09-30 and "open Booth" started routing to Chat.

Addressing is deliberately narrow. Half the codenames are ordinary English:
matching a bare token would send "press release" to Press, "white label" to
Label, and "a reel of film" to Reel. So a codename only routes when the text
addresses it — an opening verb, or the whole message being the name — which is
the difference between naming a tool and happening to use its word.
"""

import re

from agents.catalog import AGENT_SPECS

ROUTES = (
    ("video", ("video", "youtube", "shorts", "reel", "storyboard", "sora")),
    ("social", ("social post", "caption", "schedule post", "pinterest", "reddit")),
    ("audiobook", ("audiobook", "narrate", "narration", "text to speech", "tts")),
    ("music", ("spotify", "music release", "album", "single", "artist profile")),
    ("webdesign", ("website", "web page", "html", "css", "landing page")),
    ("fiverr", ("fiverr", "client delivery", "gig listing", "logo order")),
    ("creator", ("content campaign", "content calendar", "promo asset", "creator")),
    ("manuscript", (
        "query letter", "synopsis", "blurb", "book proposal", "publish",
        "kdp", "goodreads", "arc outreach", "book marketing",
    )),
    ("author", (
        "write a chapter", "write a scene", "character arc", "world building",
        "novel", "manuscript", "book outline",
    )),
)


#: Verbs that mean "take me to this tool". Kept short on purpose: "in press"
#: and "with stamp" read as ordinary English, so they are not openers.
_OPENERS = ("open", "use", "switch to", "go to", "take me to")


def _addressable() -> dict[str, str]:
    """Codename -> agent key, from the catalog so it cannot drift from labels."""
    return {spec.label.casefold(): spec.key
            for spec in AGENT_SPECS if spec.workspace is not None}


def _addressed(lowered: str) -> str | None:
    """The agent the text names, or None if it only mentions a word."""
    for name, key in _addressable().items():
        escaped = re.escape(name)
        if re.fullmatch(rf"\W*{escaped}\W*", lowered):
            return key
        openers = "|".join(_OPENERS)
        if re.search(rf"\b(?:{openers})\s+(?:the\s+)?{escaped}\b", lowered):
            return key
    return None


class RouterAgent:
    def classify(self, text: str) -> str:
        lowered = text.casefold()
        # Addressing wins over intent: naming a tool is the more explicit act,
        # and the two only disagree when the user asked for one by name while
        # describing work that usually belongs to another.
        addressed = _addressed(lowered)
        if addressed is not None:
            return addressed
        for agent_key, keywords in ROUTES:
            if any(keyword in lowered for keyword in keywords):
                return agent_key
        return "chat"
