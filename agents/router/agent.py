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
from dataclasses import dataclass, field

from agents.catalog import AGENT_SPECS


@dataclass(frozen=True)
class RouteDecision:
    """Where a request goes, and — explicitly — how sure the router is.

    confidence is one of three honest tiers, not a probability dressed up
    as one:
      "addressed" — the user named the tool; the router is certain.
      "intent"    — a keyword matched; certain-ish, and `matches` lists
                    every (agent, keyword) hit so an ambiguous request is
                    visible instead of silently first-match-wins.
      "fallback"  — nothing matched; Chat is the default, and saying so
                    beats pretending the router decided anything.
    """

    key: str
    confidence: str
    reason: str
    matches: tuple = field(default_factory=tuple)

    @property
    def ambiguous(self) -> bool:
        return len({key for key, _kw in self.matches}) > 1

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
    def route(self, text: str) -> RouteDecision:
        lowered = text.casefold()
        # Addressing wins over intent: naming a tool is the more explicit act,
        # and the two only disagree when the user asked for one by name while
        # describing work that usually belongs to another.
        addressed = _addressed(lowered)
        if addressed is not None:
            label = next((spec.label for spec in AGENT_SPECS
                          if spec.key == addressed), addressed)
            return RouteDecision(
                key=addressed, confidence="addressed",
                reason=f'addressed by name ("{label}")')
        matches = tuple(
            (agent_key, keyword)
            for agent_key, keywords in ROUTES
            for keyword in keywords if keyword in lowered)
        if matches:
            key, keyword = matches[0]
            reason = f'matched "{keyword}"'
            labels = {spec.key: spec.label for spec in AGENT_SPECS}
            others = sorted(labels.get(k, k)
                            for k in {k for k, _kw in matches} - {key})
            if others:
                reason += f" — but also matched {', '.join(others)}"
            return RouteDecision(key=key, confidence="intent",
                                 reason=reason, matches=matches)
        return RouteDecision(
            key="chat", confidence="fallback",
            reason="no intent recognized — Chat handles general requests")

    def classify(self, text: str) -> str:
        """The decision's key alone, for call sites that only route."""
        return self.route(text).key
