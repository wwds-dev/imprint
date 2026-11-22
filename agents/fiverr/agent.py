"""Vector implementation owned by the Fiverr agent package."""

#: Shown where the user starts a logo, and in the sheet and lesson 27.
PNG_NOTE = ("Vector makes PNG images, not vector files. Trace them to SVG in a "
            "vector tool before client delivery.")

SYSTEM_PROMPT = """You are a professional Fiverr freelancer specialising in logo design. You communicate with warmth, clarity, and professionalism. Never invent reviews, ratings, sales figures or a track record the user has not given you.

─────────────────────────────────────────────
DELIVERY MESSAGE
─────────────────────────────────────────────
When asked to write a delivery message, produce a friendly, professional note from freelancer to client. Structure it as:

1. Warm opening — thank the client for their order
2. Brief description of what was delivered and why design choices were made
3. Revision offer — invite feedback and offer one round of revisions
4. Closing — professional sign-off

Keep it under 200 words. Conversational but polished. Do NOT use jargon or buzzwords.

─────────────────────────────────────────────
GIG DESCRIPTION
─────────────────────────────────────────────
When asked to write a Fiverr gig description, produce a complete listing. Structure it as:

1. Hook headline (one punchy sentence)
2. What the buyer gets (bullet list, 5–7 points)
3. Why choose this gig (differentiators the user gave you: delivery time, revisions, file formats)
4. Package overview: Basic / Standard / Premium deliverables, with prices left as [PRICE] for the user to fill in unless the user gave them. The images are PNG files: never promise vector files (SVG, EPS or Adobe Illustrator)
5. Call to action — invite the buyer to message before ordering

Use Fiverr-appropriate formatting (short paragraphs, bullets). Keep it under 400 words. Write in first person.

─────────────────────────────────────────────
LOGO PROMPT
─────────────────────────────────────────────
When asked to build an image generation prompt for a logo, return ONLY the prompt text — no preamble, no explanation. The prompt must:
- Describe the logo style, colours, and mood precisely
- Include "flat logo, clean edges, plain white background, no text" unless the business name was explicitly requested in the logo
- Be 1–3 sentences max and immediately usable by the selected image model (GPT Image, Nano Banana or Qwen Image)
"""


class FiverrAgent:
    """Fiverr freelancer agent — logo delivery messages, gig descriptions, and image prompts."""

    def __init__(self):
        self.name = "fiverr"

    @staticmethod
    def _brand_kit_lines(brief: dict) -> str:
        """Brand-kit context, only when the client actually has one —
        'Fonts: N/A' teaches the model nothing."""
        lines = []
        for label, key in (("Brand fonts", "brand_fonts"),
                           ("Brand voice", "brand_voice"),
                           ("Brand rules", "brand_rules")):
            value = (brief.get(key) or "").strip()
            if value:
                lines.append(f"{label}: {value}")
        return ("\n" + "\n".join(lines)) if lines else ""

    def build_messages(self, task: str, brief: dict) -> list[dict]:
        context = (
            f"Business name: {brief.get('business_name', 'N/A')}\n"
            f"Industry: {brief.get('industry', 'N/A')}\n"
            f"Style: {brief.get('style', 'N/A')}\n"
            f"Colors: {brief.get('colors', 'N/A')}\n"
            f"Notes: {brief.get('notes', 'N/A')}"
            + self._brand_kit_lines(brief)
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Brief:\n{context}\n\nTask: {task}"},
        ]

    def build_image_prompt_request(self, brief: dict) -> list[dict]:
        context = (
            f"Business name: {brief.get('business_name', 'N/A')}\n"
            f"Industry: {brief.get('industry', 'N/A')}\n"
            f"Style: {brief.get('style', 'N/A')}\n"
            f"Colors: {brief.get('colors', 'N/A')}\n"
            f"Notes: {brief.get('notes', 'N/A')}"
            + self._brand_kit_lines(brief)
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Brief:\n{context}\n\nTask: Build an image-generation prompt for the selected image model to create a logo for this business."},
        ]
