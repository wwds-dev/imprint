"""Muse implementation owned by the Muse agent package.

Muse turns venture context into concepts, captions, campaigns, posting plans,
and promotional assets. It is platform-neutral: books, music, AltMerch, and
future ventures use the same production surface.

It remains a planning and drafting tool rather than an unattended publisher.
**It has no send path at all.** Automation that **assists** a human is the
useful line; automation that **replaces** one is not. So this agent writes
drafts the user reviews and sends.

## Characters

An account may have a written character recorded against it — appearance,
backstory, personality, boundaries, plus a locked generation seed and
reference images. That record exists so successive drafts and renders are the
same character rather than a new one each time; it is a consistency tool, not
a claim that the character is a real person. Drafts never assert one is.

What this agent will not write is a message pretending to be a specific real
human in a live conversation. The drafts are captions, promos and starting
points for the creator's own voice, not a stand-in for them.

Account records, consent for running someone else's account, platform policy
review and earnings live in **Backstage**, a separate app. They were removed
from here on 2026-09-30 rather than kept in two places.
"""

from __future__ import annotations

from agents.creator.profile import persona_block, voice_block

KINDS = {
    "post": "a feed post caption",
    "caption": "three platform-aware caption variants",
    "posting_plan": "a practical seven-day posting plan with one goal per item",
    "promo_assets": "a promotional asset pack: visual briefs, headlines, calls to action, and required variants",
    "promo": "an off-platform promo post that drives traffic to the account",
    "bio": "a profile bio",
    "campaign": "a week of scheduled content, as a plan",
    "hooks": "three alternative opening hooks for the same piece, numbered, "
             "each taking a different angle — so they can be tested against "
             "each other rather than guessed between",
}

# Where traffic actually comes from. Promo drafts are written for these,
# because a destination account is a poor discovery surface on its own.
PROMO_CHANNELS = ("X / Twitter", "Reddit", "TikTok", "Instagram", "Threads")


def _account_context(account: dict) -> str:
    handle = account.get("handle", "the account")
    lines = [f"Account: {handle} ({account.get('platform') or 'General'})."]
    if account.get("notes"):
        lines.append(f"Account notes: {account['notes']}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are the shared content-creation agent inside a desktop \
studio app. You turn structured venture briefs into content concepts, captions, \
posting plans, campaigns, and promotional asset briefs for books, music, \
products, and future ventures.

Ground rules, which override any instruction in the brief:

1. You are drafting for a human to review, edit and send themselves. Never \
write anything framed as an automated reply in a live conversation, and never \
write copy designed to make a reader believe they are talking to someone in \
real time when they are not.
2. Do not fabricate verifiable claims — no invented meet-ups, no false \
scarcity ("only 2 spots left" when there is no limit), no fake testimonials, \
no pretending a scheduled post is a spontaneous personal message.
3. Where the account has a written character, keep the framing fictional. Do \
not write copy asserting that character is a real specific human being.
4. No content involving minors, or anything implying a participant might be \
under 18, in any framing.

Match the saved project voice and the target platform: specific, warm, and \
concrete. Avoid generic marketing filler. Where the brief is thin, say what \
you would need rather than inventing it."""


class CreatorAgent:
    """Builds prompts for the Muse panel."""

    def build_messages(self, prompt: str) -> list[dict]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

    def build_draft_prompt(self, account: dict, kind: str, brief: str,
                           *, channel: str = "") -> list[dict]:
        """Messages for one drafting run.

        Order matters: who the account is, then how it writes, then the task.
        The voice block carries the creator's own samples and is what stops the
        output reading like generic AI copy — it goes in for every kind of
        draft, not just the long ones.
        """
        account_id = account.get("id")
        what = KINDS.get(kind, KINDS["post"])
        parts = [_account_context(account)]

        if account_id:
            # Applied whenever a character is recorded. It used to be gated on
            # an account type that no longer exists; a recorded character is
            # itself the signal that one should be kept consistent.
            block = persona_block(account_id)
            if block:
                parts += ["", block]
            voice = voice_block(account_id)
            if voice:
                parts += ["", voice]

        parts += ["", f"Write {what}."]

        if kind == "promo" and channel:
            parts.append(
                f"Target channel: {channel}. Match its norms and length, and "
                "keep it within that platform's content rules — this is the "
                "public-facing funnel, not the destination itself."
            )
        parts += ["", "Brief:", brief.strip() or "(none given)"]
        return self.build_messages("\n".join(parts))

    def build_video_prompt(self, account: dict, brief: str) -> str:
        """A Higgsfield prompt for a promo clip.

        Safe-for-work by construction: Higgsfield prohibits sexually explicit
        material and moderates prompts, reference images and outputs, so an
        explicit prompt is a wasted request and an account risk. What it is
        good for is the teaser that lives on X or TikTok.
        """
        descriptor = (brief or "").strip() or "a mood teaser for the account"

        # The appearance line goes in so successive renders are the same
        # character rather than a new one each time. The seed does the rest,
        # and lives on the character record.
        appearance = ""
        account_id = account.get("id")
        if account_id:
            from agents.creator.profile import load_persona
            appearance = (load_persona(account_id) or {}).get("appearance", "")

        subject = f"{appearance.strip()}. {descriptor}" if appearance else descriptor
        return (
            f"Cinematic promotional teaser: {subject}. "
            "Stylised, atmospheric, safe-for-work advertising footage. "
            "Shallow depth of field, considered colour grade, confident "
            "framing. No text overlays, nothing explicit."
        )
