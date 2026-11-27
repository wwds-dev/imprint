"""No colour literal outside the token modules (ADR 0006, decision 1).

Light is the default look, so a colour written into a widget's sheet as a
literal is a dark box or an invisible line on white, and no other test says
so. Every colour in the window's code goes through a token: the main sheet,
``theme.themed``/``theme.recolour`` on the authored names, or
``theme.token``/``theme.palette`` for painter and HTML code.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LITERAL = re.compile(
    r"(?<![&\w])#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?(?![\w])|rgba?\(\s*\d")

#: Where colours are defined, not used.
TOKEN_MODULES = {"ui/style.py", "ui/theme.py"}

#: (file, the literal's line, with surrounding spaces stripped) — and why.
ALLOWED = {
    # The authored phosphor that ui.theme.recolour turns per theme.
    ("ui/vibe.py", 'PHOSPHOR = "#00ff41"'),
    # Placeholder text showing the input's format: data, not a colour.
    ("agents/webdesign/panel.py",
     'self.webdesign_palette_input = line_edit("#1a1a2e, #e94560  ·  ocean blues")'),
}
#: Whole files: byte-identical with Sentinel (tests/test_providers_drift.py),
#: and their translucent amber and slate tints read on both looks.
ALLOWED_FILES = {"ui/routing_advice.py"}


def _sources():
    yield ROOT / "main.py"
    for folder in ("ui", "agents"):
        yield from sorted((ROOT / folder).rglob("*.py"))


def test_no_colour_literal_outside_the_tokens():
    found = []
    for path in _sources():
        rel = path.relative_to(ROOT).as_posix()
        if rel in TOKEN_MODULES or rel in ALLOWED_FILES:
            continue
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue                                # a comment
            code = stripped.split("  # ")[0]            # a trailing comment
            if LITERAL.search(code) and (rel, stripped) not in ALLOWED:
                found.append(f"{rel}:{number}: {stripped}")
    assert not found, "colour literals outside the tokens:\n" + "\n".join(found)


def test_the_allow_list_is_still_needed():
    """An allowed line that no longer exists is a stale exception."""
    for rel, line in ALLOWED:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert line in {raw.strip() for raw in text.splitlines()}, (rel, line)
