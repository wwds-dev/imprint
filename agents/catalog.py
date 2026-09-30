"""Canonical roster for the Imprint umbrella.

This is the only cross-agent index.  An agent owns its implementation and
project documents inside ``agents/<key>/``; the umbrella owns navigation,
shared providers, budgets, persistence and composition between agents.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class AgentSpec:
    """Stable metadata the umbrella needs without importing agent internals."""

    key: str
    label: str
    workspace: str | None
    description: str
    package: str
    panel: bool = True
    recommendation_profile: str | None = None


AGENT_SPECS = (
    AgentSpec(
        "author", "Quill", "Author",
        "Plan, draft and revise long-form fiction and non-fiction.",
        "agents.author",
        recommendation_profile="agents.author.recommendations",
    ),
    AgentSpec(
        "manuscript", "Press", "Author",
        "Prepare, export, distribute and measure finished books.",
        "agents.manuscript",
        recommendation_profile="agents.manuscript.recommendations",
    ),
    AgentSpec(
        "audiobook", "Booth", "Audio + Music",
        "Convert books into resumable, production-ready audiobooks.",
        "agents.audiobook",
        recommendation_profile="agents.audiobook.recommendations",
    ),
    AgentSpec(
        "music", "Label", "Audio + Music",
        "Develop songs and albums, artist identities, releases, promotion and income plans.",
        "agents.music",
        recommendation_profile="agents.music.recommendations",
    ),
    AgentSpec(
        "video", "Reel", "Video + Ads",
        "Script, generate, narrate and assemble long-form or vertical video.",
        "agents.video",
        recommendation_profile="agents.video.recommendations",
    ),
    AgentSpec(
        "social", "Herald", "Social",
        "Draft, schedule and publish platform-native campaign content.",
        "agents.social",
        recommendation_profile="agents.social.recommendations",
    ),
    AgentSpec(
        "webdesign", "Sitebuilder", "Web",
        "Create responsive HTML, CSS and JavaScript experiences.",
        "agents.webdesign",
        recommendation_profile="agents.webdesign.recommendations",
    ),
    AgentSpec(
        "fiverr", "Stamp", "Brand Design",
        "Create client-ready concepts, listings and delivery messages.",
        "agents.fiverr",
        recommendation_profile="agents.fiverr.recommendations",
    ),
    AgentSpec(
        "creator", "Muse", "Brand Content",
        "Create reusable campaigns, captions and promotional assets.",
        "agents.creator",
        recommendation_profile="agents.creator.recommendations",
    ),
    AgentSpec(
        "course", "Primer", None,
        "Produce packaged courses from the command line.",
        "agents.course", panel=False,
    ),
    AgentSpec(
        "chat", "Chat", "Assistant",
        "General-purpose chat and tool-assisted conversation.",
        "agents.chat", panel=False,
        recommendation_profile="agents.chat.recommendations",
    ),
    AgentSpec(
        "router", "Intent Router", None,
        "Internal intent classification for the umbrella runtime.",
        "agents.router", panel=False,
    ),
)

AGENTS_BY_KEY = MappingProxyType({spec.key: spec for spec in AGENT_SPECS})

# One line per workspace, shown under the header tab bar. Agent labels are
# codenames now ("Quill", "Booth", "Muse"), so a workspace name alone no
# longer tells a new user what lives inside it. Keyed by workspace name
# because a workspace is a grouping, not an agent, and has no spec of its own.
WORKSPACE_DESCRIPTIONS = MappingProxyType({
    "Author": "Write a book, then prepare, publish and track it.",
    "Audio + Music": "Narrate books into audiobooks, and develop and release music.",
    "Video + Ads": "Script, narrate and assemble long-form video and vertical ads.",
    "Social": "Write, schedule and publish platform-native posts.",
    "Web": "Build responsive pages in HTML, CSS and JavaScript.",
    "Brand Design": "Create client-ready brand concepts, logos and delivery copy.",
    "Brand Content": "Draft campaign content, plan it on a calendar, and render promos.",
    "Assistant": "General-purpose chat for anything without a dedicated tool.",
})


def workspace_description(workspace: str) -> str:
    """Return the line shown under a workspace tab, or "" if none is set."""
    return WORKSPACE_DESCRIPTIONS.get(workspace, "")


def workspace_map() -> dict[str, tuple[str, ...]]:
    """Return visible workspaces in catalog order."""
    result: dict[str, list[str]] = {}
    for spec in AGENT_SPECS:
        if spec.workspace is not None:
            result.setdefault(spec.workspace, []).append(spec.key)
    return {workspace: tuple(keys) for workspace, keys in result.items()}


def package_for(key: str) -> str:
    return AGENTS_BY_KEY[key].package
