"""
Sentinel AI — Agent Scenario Tests
===================================
Type: Functional / Scenario-based Tests  (also called "Use Case Tests")

These tests verify that every agent:
  1. Produces a correctly structured message list for the LLM.
  2. Injects the right system prompt for its domain.
  3. Embeds every piece of user-supplied input into the user message.
  4. Executes its own logic correctly (routing, parsing, config).

They are NOT unit tests of individual helper lines, and they are NOT
end-to-end tests that call a live LLM.  The sweet spot is: "given this
realistic scenario, does the agent behave exactly as designed?"

Run with:  pytest tests/test_agents_scenarios.py -v
"""

import sys
import os
import pytest

# Make sure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.router             import RouterAgent
from agents.chat               import ChatAgent
from agents.author             import AuthorAgent
from agents.fiverr             import FiverrAgent
from agents.music              import MusicAgent
from agents.webdesign          import WebdesignAgent
from agents.audiobook          import AudiobookConnector


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _roles(msgs):
    """Return just the list of roles from a message list."""
    return [m["role"] for m in msgs]

def _system(msgs):
    """Return the content of the first system message, or None."""
    for m in msgs:
        if m["role"] == "system":
            return m["content"]
    return None

def _user(msgs):
    """Return the content of the last user message."""
    for m in reversed(msgs):
        if m["role"] == "user":
            return m["content"]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. RouterAgent
# Scenario: classify representative creative work, plus the safe fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestRouterAgent:
    agent = RouterAgent()

    def test_routes_video(self):
        assert self.agent.classify("Make a YouTube video and storyboard") == "video"

    def test_routes_social(self):
        assert self.agent.classify("Schedule a social post for Reddit") == "social"

    def test_routes_audiobook(self):
        assert self.agent.classify("Narrate this ebook as an audiobook") == "audiobook"

    def test_routes_site_builder(self):
        assert self.agent.classify("Build a responsive landing page in HTML") == "webdesign"

    def test_routes_drafting(self):
        assert self.agent.classify("Write a chapter with a stronger character arc") == "author"

    def test_routes_publishing(self):
        assert self.agent.classify("Create a query letter and synopsis") == "manuscript"

    def test_defaults_to_chat(self):
        assert self.agent.classify("What is the capital of France?") == "chat"

    # ── the decision is explicit about confidence and fallback ──────────
    def test_addressed_decision_is_certain(self):
        decision = self.agent.route("open Quill")
        assert (decision.key, decision.confidence) == ("author", "addressed")
        assert "Quill" in decision.reason

    def test_intent_decision_names_the_matched_keyword(self):
        decision = self.agent.route("Narrate this ebook as an audiobook")
        assert (decision.key, decision.confidence) == ("audiobook", "intent")
        assert "narrate" in decision.reason or "audiobook" in decision.reason
        assert not decision.ambiguous

    def test_ambiguous_intent_is_visible_not_silent(self):
        decision = self.agent.route(
            "Make a YouTube video for the music release")
        assert decision.confidence == "intent"
        assert decision.ambiguous
        assert "also matched" in decision.reason
        keys = {key for key, _kw in decision.matches}
        assert {"video", "music"} <= keys

    def test_fallback_says_so_instead_of_pretending(self):
        decision = self.agent.route("What is the capital of France?")
        assert (decision.key, decision.confidence) == ("chat", "fallback")
        assert "no intent" in decision.reason

    def test_classify_stays_the_decisions_key(self):
        text = "Build a responsive landing page in HTML"
        assert self.agent.classify(text) == self.agent.route(text).key

    def test_case_insensitive_routing(self):
        assert self.agent.classify("MAKE A SPOTIFY MUSIC RELEASE PLAN") == "music"

    # ── Addressing an agent by its codename ──────────────────────────────────
    # Added 2026-09-30 with the rename: "open Booth" routed to Chat, because
    # the router only ever knew intent words, never the agents' own names.

    @pytest.mark.parametrize("text,expected", [
        ("open Booth", "audiobook"),
        ("use Quill", "author"),
        ("switch to Muse", "creator"),
        ("go to Herald", "social"),
        ("take me to Press", "manuscript"),
        ("open the Reel", "video"),
        ("USE SITEBUILDER", "webdesign"),
    ])
    def test_addressing_an_agent_by_name(self, text, expected):
        assert self.agent.classify(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("Muse", "creator"),
        ("Booth", "audiobook"),
        ("Stamp.", "fiverr"),
    ])
    def test_the_bare_name_is_enough(self, text, expected):
        assert self.agent.classify(text) == expected

    @pytest.mark.parametrize("text", [
        "press release for the launch",
        "a white label deal",
        "stamp the document and send it",
        "we need a primer on solvency",
    ])
    def test_an_ordinary_word_is_not_an_address(self, text):
        """Half the codenames are ordinary English. Matching a bare token would
        send "press release" to Press, which is the reason addressing needs an
        opening verb rather than a word match."""
        assert self.agent.classify(text) == "chat"

    def test_codenames_come_from_the_catalog(self):
        """So a rename cannot leave the router answering to a name that no
        longer exists — the failure this whole change exists to fix."""
        from agents.catalog import AGENT_SPECS

        for spec in AGENT_SPECS:
            if spec.workspace is None:
                continue
            assert self.agent.classify(f"open {spec.label}") == spec.key

    def test_addressing_beats_intent_when_they_disagree(self):
        """Naming a tool is the more explicit act."""
        assert self.agent.classify("open Quill") == "author"
        assert self.agent.classify(
            "open Quill and write a social post") == "author"


# 3. ChatAgent
# Scenario: pass a multi-line, conversational prompt
# ─────────────────────────────────────────────────────────────────────────────

class TestChatAgent:
    agent = ChatAgent()

    def test_message_structure(self):
        msgs = self.agent.build_messages("Hello, how are you?")
        assert _roles(msgs) == ["user"]

    def test_user_content_preserved(self):
        prompt = "Explain quantum entanglement in simple terms."
        msgs = self.agent.build_messages(prompt)
        assert _user(msgs) == prompt

    def test_multiline_prompt(self):
        prompt = "Line one.\nLine two.\nLine three."
        msgs = self.agent.build_messages(prompt)
        assert "Line one" in _user(msgs)
        assert "Line three" in _user(msgs)

    def test_no_system_injection(self):
        # ChatAgent is intentionally system-prompt-free
        msgs = self.agent.build_messages("hi")
        assert _system(msgs) is None


# 8. AuthorAgent
# Scenario: draft prose  |  publish query letter  |  marketing copy
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorAgent:
    agent = AuthorAgent()

    DRAFT_PROMPT = (
        "Write the opening scene of a cyberpunk thriller. "
        "POV: third-person limited. Setting: neon-lit Tokyo, 2089. "
        "Tone: tense and atmospheric."
    )
    PUBLISH_PROMPT = "Write a query letter for a 90,000-word cyberpunk thriller manuscript."
    MARKET_PROMPT  = "Write Instagram caption copy for the launch of my cyberpunk thriller."

    def test_draft_message_structure(self):
        msgs = self.agent.build_messages(self.DRAFT_PROMPT)
        assert _roles(msgs) == ["system", "user"]

    def test_draft_prompt_preserved(self):
        msgs = self.agent.build_messages(self.DRAFT_PROMPT)
        assert "cyberpunk" in _user(msgs)

    def test_draft_system_prompt_contains_writing_principles(self):
        sys = _system(self.agent.build_messages(self.DRAFT_PROMPT))
        assert "DRAFT" in sys or "prose" in sys.lower()

    def test_publish_message_structure(self):
        msgs = self.agent.build_publish_messages(self.PUBLISH_PROMPT)
        assert _roles(msgs) == ["system", "user"]

    def test_publish_system_prompt_is_different(self):
        draft_sys   = _system(self.agent.build_messages(self.DRAFT_PROMPT))
        publish_sys = _system(self.agent.build_publish_messages(self.PUBLISH_PROMPT))
        assert draft_sys != publish_sys

    def test_publish_system_prompt_mentions_publishing(self):
        sys = _system(self.agent.build_publish_messages(self.PUBLISH_PROMPT))
        assert "publishing" in sys.lower() or "query" in sys.lower() or "synopsis" in sys.lower()

    def test_market_message_structure(self):
        msgs = self.agent.build_market_messages(self.MARKET_PROMPT)
        assert _roles(msgs) == ["system", "user"]

    def test_market_system_prompt_is_different_from_draft(self):
        draft_sys  = _system(self.agent.build_messages(self.DRAFT_PROMPT))
        market_sys = _system(self.agent.build_market_messages(self.MARKET_PROMPT))
        assert draft_sys != market_sys

    def test_market_system_prompt_mentions_marketing(self):
        sys = _system(self.agent.build_market_messages(self.MARKET_PROMPT))
        assert "marketing" in sys.lower() or "copy" in sys.lower() or "launch" in sys.lower()


# 10. FiverrAgent
# Scenario: delivery message  |  gig description  |  GPT Image logo prompt
# ─────────────────────────────────────────────────────────────────────────────

class TestFiverrAgent:
    agent = FiverrAgent()

    BRIEF = {
        "business_name": "NovaBrew Coffee",
        "industry":       "Specialty Coffee Shop",
        "style":          "Minimalist / Modern",
        "colors":         "Deep navy and warm gold",
        "notes":          "Should feel premium and artisan, not corporate",
    }

    def test_delivery_message_structure(self):
        msgs = self.agent.build_messages("Write a delivery message", self.BRIEF)
        assert _roles(msgs) == ["system", "user"]

    def test_brief_fields_in_user_message(self):
        msgs = self.agent.build_messages("Write a delivery message", self.BRIEF)
        user_text = _user(msgs)
        assert "NovaBrew Coffee" in user_text
        assert "Specialty Coffee Shop" in user_text
        assert "navy" in user_text.lower() or "Deep navy" in user_text

    def test_task_type_in_user_message(self):
        msgs = self.agent.build_messages("Write a delivery message", self.BRIEF)
        assert "delivery message" in _user(msgs).lower()

    def test_gig_description_task_in_user_message(self):
        msgs = self.agent.build_messages("Write a Fiverr gig description", self.BRIEF)
        assert "gig description" in _user(msgs).lower()

    def test_system_prompt_covers_all_three_modes(self):
        sys = _system(self.agent.build_messages("anything", self.BRIEF))
        assert "DELIVERY MESSAGE" in sys
        assert "GIG DESCRIPTION" in sys
        assert "LOGO PROMPT" in sys

    def test_image_prompt_request_structure(self):
        msgs = self.agent.build_image_prompt_request(self.BRIEF)
        assert _roles(msgs) == ["system", "user"]

    def test_image_prompt_request_mentions_current_image_model(self):
        msgs = self.agent.build_image_prompt_request(self.BRIEF)
        assert "GPT Image" in _user(msgs)

    def test_image_prompt_request_includes_brief(self):
        msgs = self.agent.build_image_prompt_request(self.BRIEF)
        assert "NovaBrew Coffee" in _user(msgs)


# 15. MusicAgent
# Scenario: full Spotify artist setup for an indie electronic artist
# ─────────────────────────────────────────────────────────────────────────────

class TestMusicAgent:
    agent = MusicAgent()

    PROMPT = (
        "Artist name: NOVA//DRIFT\n"
        "Genre: Indie Electronic / Ambient Pop\n"
        "Location: Berlin, Germany\n"
        "Similar artists: Bonobo, Tourist, Tycho\n"
        "First release: debut EP 'Static Light' — 5 tracks, release date in 3 weeks.\n"
        "Set up my complete Spotify profile and release."
    )

    def test_message_structure(self):
        msgs = self.agent.build_messages(self.PROMPT)
        assert _roles(msgs) == ["system", "user"]

    def test_prompt_preserved(self):
        msgs = self.agent.build_messages(self.PROMPT)
        assert "NOVA//DRIFT" in _user(msgs)
        assert "Static Light" in _user(msgs)

    def test_system_prompt_contains_output_sections(self):
        sys = _system(self.agent.build_messages(self.PROMPT))
        for section in ["ARTIST PROFILE", "RELEASE SETUP"]:
            assert section in sys

    def test_system_prompt_marks_ai_output_vs_human_steps(self):
        sys = _system(self.agent.build_messages(self.PROMPT))
        assert "AI OUTPUT" in sys
        assert "HUMAN ACTION" in sys

    def test_system_prompt_mentions_bio_length_constraints(self):
        sys = _system(self.agent.build_messages(self.PROMPT))
        # Both short bio (150 chars) and long bio (300-500 words) should be referenced
        assert "150" in sys
        assert "300" in sys or "500" in sys


# ─────────────────────────────────────────────────────────────────────────────
# 16. WebdesignAgent
# Scenario: SaaS landing page with hero, features, pricing, CTA
# ─────────────────────────────────────────────────────────────────────────────

class TestWebdesignAgent:
    agent = WebdesignAgent()

    PROMPT = (
        "Build a SaaS landing page for a project management tool called 'Taskly'.\n"
        "Sections: hero with CTA, 3-feature grid, pricing table (3 tiers), footer.\n"
        "Style: clean, modern, dark mode. Colours: indigo and white. No frameworks.\n"
        "Include a mobile hamburger menu."
    )

    def test_message_structure(self):
        msgs = self.agent.build_messages(self.PROMPT)
        assert _roles(msgs) == ["system", "user"]

    def test_prompt_preserved(self):
        msgs = self.agent.build_messages(self.PROMPT)
        assert "Taskly" in _user(msgs)
        assert "hamburger" in _user(msgs).lower()

    def test_system_prompt_requires_semantic_html(self):
        sys = _system(self.agent.build_messages(self.PROMPT))
        assert "semantic" in sys.lower() or "<header>" in sys or "HTML5" in sys

    def test_system_prompt_requires_responsive_css(self):
        sys = _system(self.agent.build_messages(self.PROMPT))
        assert "responsive" in sys.lower() or "mobile" in sys.lower()

    def test_system_prompt_mentions_accessibility(self):
        sys = _system(self.agent.build_messages(self.PROMPT))
        assert "accessibility" in sys.lower() or "aria" in sys.lower() or "alt" in sys.lower()

    def test_system_prompt_bans_jquery(self):
        sys = _system(self.agent.build_messages(self.PROMPT))
        assert "jQuery" in sys or "vanilla" in sys.lower()


# 18. AudiobookConnector
# Scenario A: full valid config  |  B: minimal valid  |  C/D: missing required fields
# ─────────────────────────────────────────────────────────────────────────────

class TestAudiobookConnector:
    connector = AudiobookConnector()

    def test_full_config_parses_correctly(self):
        text = (
            "input=/books/the_great_gatsby.epub\n"
            "output=/audiobooks/gatsby/\n"
            "voice=onyx\n"
            "chunk_tokens=2000"
        )
        config = self.connector.parse_input(text)
        assert config["input"]        == "/books/the_great_gatsby.epub"
        assert config["output"]       == "/audiobooks/gatsby/"
        assert config["voice"]        == "onyx"
        assert config["chunk_tokens"] == "2000"

    def test_minimal_config_parses_correctly(self):
        text = (
            "input=/books/dune.epub\n"
            "output=/audiobooks/dune/"
        )
        config = self.connector.parse_input(text)
        assert config["input"]  == "/books/dune.epub"
        assert config["output"] == "/audiobooks/dune/"

    def test_minimal_config_uses_default_voice(self):
        text = "input=/books/dune.epub\noutput=/audiobooks/dune/"
        config = self.connector.parse_input(text)
        assert config["voice"] == "alloy"   # default from __init__

    def test_minimal_config_uses_default_chunk_tokens(self):
        text = "input=/books/dune.epub\noutput=/audiobooks/dune/"
        config = self.connector.parse_input(text)
        assert config["chunk_tokens"] == 1500   # default from __init__

    def test_missing_input_raises_value_error(self):
        text = "output=/audiobooks/dune/"
        with pytest.raises(ValueError, match="input"):
            self.connector.parse_input(text)

    def test_missing_output_raises_value_error(self):
        text = "input=/books/dune.epub"
        with pytest.raises(ValueError, match="output"):
            self.connector.parse_input(text)

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            self.connector.parse_input("")

    def test_extra_whitespace_around_values_is_stripped(self):
        text = "input = /books/dune.epub\noutput = /audiobooks/dune/"
        config = self.connector.parse_input(text)
        assert config["input"]  == "/books/dune.epub"
        assert config["output"] == "/audiobooks/dune/"
