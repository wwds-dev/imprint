"""Every text and indicator token is readable on every surface it is used on
(spec manuscript-redesign, measure 6; Design S8; ADR 0006).

WCAG 2.x relative luminance. Text needs 4.5:1 (1.4.3); indicators and control
edges need 3:1 (1.4.11). Translucent tokens are composited over the surface
they sit on; washes over ``SURFACE``. Computed from the tokens in
``ui/theme.py``, so a palette edit that breaks contrast fails here.

The dark palettes keep today's values (S8). Where today's dark values already
fail, the case is ``xfail(strict=True)``: it documents the gap and fails the
day someone fixes it without updating this file. ``TEXT_MUTE`` is the owner's
decision AO2 (2026-11-25); the others were found in Build and are raised with
the owner in the slice-1 PR (TODO.md).
"""

import re

import pytest

from ui import theme

SURFACES = ("BG", "SURFACE", "ELEVATED", "SUNKEN")

#: Tokens that carry text: 4.5:1 on every surface.
TEXT_TOKENS = ("TEXT", "TEXT_DIM", "TEXT_MUTE", "ACCENT", "ACCENT_DIM",
               "PHOSPHOR", "DANGER", "WARNING", "INFO")
#: Indicators and control edges: 3:1 on every surface.
INDICATOR_TOKENS = ("BORDER_STRONG", "WARNING_DOT", "ACCENT")

DARK = theme.themes_for(theme.DARK)
LIGHT = theme.themes_for(theme.LIGHT)

#: (theme, token) pairs that fail today in the dark looks, unchanged by slice 1.
KNOWN_DARK_GAPS = {
    **{(name, "TEXT_MUTE"): "AO2: dark TEXT_MUTE is 3.4–3.8:1" for name in DARK},
    **{(name, "BORDER_STRONG"): "dark control edges are ~1.5:1 (found in Build)"
       for name in DARK},
    (theme.RED, "ACCENT_DIM"): "dark rose ACCENT_DIM is 3.5:1 (found in Build)",
    (theme.RED, "PHOSPHOR"): "dark rose PHOSPHOR is 4.2:1 (found in Build)",
}


def _rgb(colour: str, over: tuple[int, int, int] | None = None):
    colour = colour.strip()
    if colour.startswith("#"):
        return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
    match = re.fullmatch(
        r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", colour)
    assert match, colour
    r, g, b, alpha = (int(match[1]), int(match[2]), int(match[3]),
                      float(match[4]))
    assert over is not None, f"{colour} needs a surface to sit on"
    return tuple(round(alpha * fg + (1 - alpha) * bg)
                 for fg, bg in zip((r, g, b), over))


def _luminance(rgb) -> float:
    def channel(value):
        value /= 255
        return (value / 12.92 if value <= 0.03928
                else ((value + 0.055) / 1.055) ** 2.4)
    r, g, b = map(channel, rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg) -> float:
    high, low = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _worst(name: str, token: str) -> tuple[float, str]:
    tokens = theme.PALETTES[name]
    results = []
    for surface in SURFACES:
        bg = _rgb(tokens[surface])
        results.append((contrast(_rgb(tokens[token], bg), bg), surface))
    return min(results)


def _cases(tokens):
    for name in theme.THEMES:
        for token in tokens:
            reason = KNOWN_DARK_GAPS.get((name, token))
            marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
            yield pytest.param(name, token, marks=marks, id=f"{name}-{token}")


def test_the_formula():
    assert round(contrast((0, 0, 0), (255, 255, 255)), 1) == 21.0
    assert round(contrast((255, 255, 255), (255, 255, 255)), 1) == 1.0
    # A documented pair: #767676 on white is the classic 4.54:1.
    assert round(contrast(_rgb("#767676"), _rgb("#ffffff")), 2) == 4.54


@pytest.mark.parametrize("name,token", list(_cases(TEXT_TOKENS)))
def test_text_tokens_meet_aa_on_every_surface(name, token):
    ratio, surface = _worst(name, token)
    assert ratio >= 4.5, f"{name}: {token} on {surface} is {ratio:.2f}:1"


@pytest.mark.parametrize("name,token", list(_cases(INDICATOR_TOKENS)))
def test_indicators_meet_3_to_1_on_every_surface(name, token):
    ratio, surface = _worst(name, token)
    assert ratio >= 3.0, f"{name}: {token} on {surface} is {ratio:.2f}:1"


@pytest.mark.parametrize("name", theme.THEMES)
def test_text_on_an_accent_fill(name):
    tokens = theme.PALETTES[name]
    ratio = contrast(_rgb(tokens["ACCENT_TEXT"]), _rgb(tokens["ACCENT"]))
    assert ratio >= 4.5, f"{name}: ACCENT_TEXT on ACCENT is {ratio:.2f}:1"


@pytest.mark.parametrize("name", theme.THEMES)
@pytest.mark.parametrize("wash", ["ACCENT_WASH", "DANGER_WASH", "WARNING_WASH",
                                  "INFO_WASH"])
def test_text_on_a_wash(name, wash):
    """Selected rows and the count badge put TEXT on a wash."""
    tokens = theme.PALETTES[name]
    surface = _rgb(tokens["SURFACE"])
    bg = _rgb(tokens[wash], surface)
    ratio = contrast(_rgb(tokens["TEXT"]), bg)
    assert ratio >= 4.5, f"{name}: TEXT on {wash} is {ratio:.2f}:1"


@pytest.mark.parametrize("name", LIGHT)
def test_accent_text_on_its_wash_in_the_light_look(name):
    """S8: ACCENT_DIM is the accent text on ACCENT_WASH."""
    tokens = theme.PALETTES[name]
    bg = _rgb(tokens["ACCENT_WASH"], _rgb(tokens["SURFACE"]))
    assert contrast(_rgb(tokens["ACCENT_DIM"]), bg) >= 4.5


@pytest.mark.parametrize("name", LIGHT)
def test_the_stale_dot_reads_on_the_app_mark(name):
    """S2: the stale dot sits on the TEXT-filled app mark (and has a SURFACE
    ring for the rail)."""
    tokens = theme.PALETTES[name]
    assert contrast(_rgb(tokens["WARNING_DOT"]), _rgb(tokens["TEXT"])) >= 3.0


def test_the_light_values_are_the_design_values():
    """S8's table, so a drift between the spec and the palette is visible."""
    light = theme.PALETTES[theme.LIGHT_GREEN]
    assert (light["BG"], light["SURFACE"], light["ELEVATED"], light["SUNKEN"]) \
        == ("#f4f5f7", "#ffffff", "#eef0f3", "#ffffff")
    assert (light["TEXT"], light["TEXT_DIM"], light["TEXT_MUTE"]) == \
        ("#14181f", "#5b6472", "#636b78")
    assert (light["BORDER"], light["BORDER_STRONG"]) == ("#e1e4ea", "#7a8290")
    assert [theme.PALETTES[k]["ACCENT"] for k in LIGHT] == \
        ["#0b7a55", "#be123c", "#0e7490"]
