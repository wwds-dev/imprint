"""Two palettes, one design system.

``ui/style.py`` is the design system: a colour is named once and every surface
that uses it agrees. This module is the other half of that promise — the named
colours are not fixed values but a *choice between two sets*, and the sheet is
built from whichever set is current.

Sentinel solves the same problem by turning the hue of a sheet full of literal
colours. Imprint does not need that: its sheet was already written against
tokens, so swapping the tokens is the whole mechanism. Keep it that way. The
moment a colour is written into a rule as a literal, it stops following the
theme and no test will tell you.

What changes, and what does not
-------------------------------
The accent changes, the phosphor changes, and the greys change their *tint* —
that is all. The greys are never neutral: a pure grey beside a saturated accent
reads as faintly tinted the opposite way, so each palette pre-tints them to a
value that sits comfortably with its own accent. There is no formula behind the
three sets, and do not invent one; each is chosen by eye and built from the same
channel values as the green set so the lightness never moves.

Semantic colour does not change. ``DANGER`` stops work, ``WARNING`` flags an
irreversible or paid step, ``INFO`` is neutral emphasis — those mean the same
thing under both themes and are not in either palette below. Under the red
theme that puts the accent and ``DANGER`` in the same family, which is why the
accent is rose and ``DANGER`` stays coral: different saturation, different
lightness, and ``DANGER`` is never the colour of a focus ring.

``save_setting``/``get_setting`` are imported inside the functions: ``ui.style``
imports this module at import time, and the database opens and migrates on
first touch, which is not something importing a stylesheet should trigger.
"""

from __future__ import annotations

import weakref
from typing import Final

GREEN: Final[str] = "green"
RED: Final[str] = "red"
BLUE: Final[str] = "blue"
THEMES: Final[tuple[str, ...]] = (GREEN, RED, BLUE)

#: Human labels for the picker, in display order.
LABELS: Final[dict[str, str]] = {
    GREEN: "Green (Matrix)",
    RED: "Red",
    BLUE: "Blue (Cyberpunk)",
}

SETTING_KEY: Final[str] = "ui_theme"

# The tokens that belong to the theme. Everything else in ui/style.py — the
# semantic colours, the radii, the chevron — is shared by both.
_GREEN: Final[dict[str, str]] = {
    "BG":            "#0d0f12",
    "SURFACE":       "#141820",
    "ELEVATED":      "#1a1f29",
    "SUNKEN":        "#0a0c0f",
    "TEXT":          "#e8ecf1",
    "TEXT_DIM":      "#9aa5b4",
    "TEXT_MUTE":     "#6b7684",
    "ACCENT":        "#34d399",
    "ACCENT_DIM":    "#2bb583",
    "ACCENT_TEXT":   "#04140d",
    "ACCENT_WASH":   "rgba(52, 211, 153, 0.12)",
    "ACCENT_LINE":   "rgba(52, 211, 153, 0.35)",
    "PHOSPHOR":      "#00ff41",
    "PHOSPHOR_LINE": "rgba(0, 255, 65, 0.45)",
    "SUNKEN_LIT":    "#0a2414",
}

_RED: Final[dict[str, str]] = {
    # The same greys with the tint turned: identical channel values, rotated so
    # red carries what blue carried. Lightness is unchanged to within a point.
    "BG":            "#120d0f",
    "SURFACE":       "#201418",
    "ELEVATED":      "#291a1f",
    "SUNKEN":        "#0f0a0c",
    "TEXT":          "#f1e8ec",
    "TEXT_DIM":      "#b49aa5",
    "TEXT_MUTE":     "#846b76",
    # Rose rather than red: DANGER is coral (#f87171) and the two must not be
    # read as the same claim. Rose is pinker and darker, and the accent never
    # appears where DANGER does — on a fill behind white text, or on a label.
    "ACCENT":        "#f43f5e",
    "ACCENT_DIM":    "#e11d48",
    "ACCENT_TEXT":   "#1a040b",
    "ACCENT_WASH":   "rgba(244, 63, 94, 0.12)",
    "ACCENT_LINE":   "rgba(244, 63, 94, 0.35)",
    # The phosphor is its own colour in both themes, hotter and more saturated
    # than the accent: the accent says "this is current", the phosphor says
    # "you wrote this".
    "PHOSPHOR":      "#ff0033",
    "PHOSPHOR_LINE": "rgba(255, 0, 51, 0.45)",
    "SUNKEN_LIT":    "#270910",
}

_BLUE: Final[dict[str, str]] = {
    # Cyan rather than blue in the greys too: the green theme's greys already
    # lean blue, so a blue-tinted set here would be the same chrome twice.
    "BG":            "#0d1212",
    "SURFACE":       "#142020",
    "ELEVATED":      "#1a2929",
    "SUNKEN":        "#0a0f0f",
    "TEXT":          "#e8f1f1",
    "TEXT_DIM":      "#9ab4b4",
    "TEXT_MUTE":     "#6b8484",
    # Cyan at 188°, not the azure a "blue theme" first suggests. INFO is
    # #60a5fa at 213°, and an accent any closer stops being distinguishable
    # from an informational badge. 25° is the narrowest margin in this file.
    "ACCENT":        "#22d3ee",
    "ACCENT_DIM":    "#06b6d4",
    "ACCENT_TEXT":   "#021417",
    "ACCENT_WASH":   "rgba(34, 211, 238, 0.12)",
    "ACCENT_LINE":   "rgba(34, 211, 238, 0.35)",
    # Electric aqua, 16° off the accent and far more saturated — the same
    # distance the Matrix green keeps from the emerald.
    "PHOSPHOR":      "#00ffdd",
    "PHOSPHOR_LINE": "rgba(0, 255, 221, 0.45)",
    "SUNKEN_LIT":    "#092724",
}

PALETTES: Final[dict[str, dict[str, str]]] = {GREEN: _GREEN, RED: _RED, BLUE: _BLUE}

# Longest first, so #34d399 is never matched inside a longer literal and the
# rgba() forms are replaced before their bare triples could be.
_SWAP: Final[dict[str, list[tuple[str, str]]]] = {
    name: sorted(
        ((_GREEN[key], tokens[key]) for key in _GREEN if _GREEN[key] != tokens[key]),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    for name, tokens in PALETTES.items()
}

_cached: str | None = None


def palette(theme: str | None = None) -> dict[str, str]:
    """The themed tokens under `theme`."""
    return dict(PALETTES[theme or current()])


def recolour(css: str, theme: str | None = None) -> str:
    """Return `css` under `theme`.

    For the sheets and snippets that call sites still build by hand out of
    ``ui.style``'s names. Those names hold the *green* values, so this swaps
    each one for its counterpart. Anything semantic passes through: there is no
    rule for it in the palette, so there is nothing to swap.
    """
    for authored, themed_value in _SWAP[theme or current()]:
        css = css.replace(authored, themed_value)
    return css


def accent(theme: str | None = None) -> str:
    """The accent under `theme`, for painter code that cannot use a sheet."""
    return PALETTES[theme or current()]["ACCENT"]


def current() -> str:
    """The saved theme, defaulting to green and never raising."""
    global _cached
    if _cached is None:
        try:
            from services.database import get_setting
            saved = get_setting(SETTING_KEY, GREEN)
        except Exception:
            saved = GREEN
        _cached = saved if saved in THEMES else GREEN
    return _cached


def set_current(theme: str) -> None:
    """Persist `theme` and make it the one every later call reads."""
    global _cached
    if theme not in THEMES:
        raise ValueError(f"unknown theme {theme!r}; expected one of {THEMES}")
    from services.database import save_setting
    save_setting(SETTING_KEY, theme)
    _cached = theme


def forget() -> None:
    """Drop the cached theme so the next read goes back to the database."""
    global _cached
    _cached = None


# ── Sheets that call sites build by hand ──────────────────────────────
# A sheet set on a widget at build time is painted once and never looked at
# again, so a theme change would leave that one widget behind. Registering it
# here is what lets `repaint()` find it later. Weak references, so a widget
# that goes away is not kept alive by its own styling.
_registered: list[tuple[weakref.ref, str]] = []


def themed(widget, css: str) -> None:
    """Apply `css` to `widget` now, and again on every theme change."""
    _registered.append((weakref.ref(widget), css))
    widget.setStyleSheet(recolour(css))


def repaint() -> None:
    """Re-apply every registered sheet, dropping the widgets that have gone."""
    live: list[tuple[weakref.ref, str]] = []
    for ref, css in _registered:
        widget = ref()
        if widget is None:
            continue
        try:
            widget.setStyleSheet(recolour(css))
        except RuntimeError:
            continue        # the C++ side is gone; drop the row
        live.append((ref, css))
    _registered[:] = live
