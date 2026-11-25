"""Two looks in three accents, one design system.

``ui/style.py`` is the design system: a colour is named once and every surface
that uses it agrees. This module is the other half of that promise — the named
colours are not fixed values but a *choice between sets*, and the sheet is
built from whichever set is current.

Sentinel solves the same problem by turning the hue of a sheet full of literal
colours. Imprint does not need that: its sheet was already written against
tokens, so swapping the tokens is the whole mechanism. Keep it that way. The
moment a colour is written into a rule as a literal, it stops following the
theme and no test will tell you.

Looks and accents
-----------------
A theme is a *look* (Light or Dark) in one of three *accents* (green, rose,
teal), stored as one key under ``ui_theme``. The dark keys are the strings the
three dark themes always had (``green``, ``red``, ``blue``), so a saved choice
never becomes invalid; the light keys are ``light-green``, ``light-rose`` and
``light-teal``. Light is the default (spec manuscript-redesign, D4; ADR 0006).

Within the dark look the accent changes, the phosphor changes, and the greys
change their *tint* — that is all. The greys are never neutral: a pure grey
beside a saturated accent reads as faintly tinted the opposite way, so each
dark palette pre-tints them to a value that sits comfortably with its own
accent. There is no formula behind the sets, and do not invent one; each is
chosen by eye and built from the same channel values as the green set so the
lightness never moves. The light look shares one set of greys.

Semantic colour keeps its meaning in every theme and its value within a look.
``DANGER`` stops work, ``WARNING`` flags an irreversible or paid step, ``INFO``
is neutral emphasis — those mean the same thing under every theme. The dark
palettes carry the values they always had; light needs darker values to stay
readable on white, so the semantic colours and the borders are palette keys
too. Under the rose accent that puts the accent and ``DANGER`` in the same
family, which is why the accent is rose and ``DANGER`` stays coral (dark) or
brick (light): different saturation, different lightness, and ``DANGER`` is
never the colour of a focus ring.

``WARNING_DOT`` is painter-only: its dark value equals ``WARNING``, so a swap
of literals could not tell the two apart. Painter code reads it with
``token("WARNING_DOT")``; it is not in ``ui/style.py`` and not in the swap.

``save_setting``/``get_setting`` are imported inside the functions: ``ui.style``
imports this module at import time, and the database opens and migrates on
first touch, which is not something importing a stylesheet should trigger.
"""

from __future__ import annotations

import re
import weakref
from typing import Final

LIGHT: Final[str] = "light"
DARK: Final[str] = "dark"
LOOKS: Final[tuple[str, ...]] = (LIGHT, DARK)
ACCENTS: Final[tuple[str, ...]] = ("green", "rose", "teal")

#: The dark keys keep the strings they were saved under before the light look.
GREEN: Final[str] = "green"
RED: Final[str] = "red"
BLUE: Final[str] = "blue"
LIGHT_GREEN: Final[str] = "light-green"
LIGHT_ROSE: Final[str] = "light-rose"
LIGHT_TEAL: Final[str] = "light-teal"

#: Every stored key, in display order: Light first, then Dark.
THEMES: Final[tuple[str, ...]] = (
    LIGHT_GREEN, LIGHT_ROSE, LIGHT_TEAL, GREEN, RED, BLUE)
DEFAULT: Final[str] = LIGHT_GREEN

_KEYS: Final[dict[tuple[str, str], str]] = {
    (LIGHT, "green"): LIGHT_GREEN, (LIGHT, "rose"): LIGHT_ROSE,
    (LIGHT, "teal"): LIGHT_TEAL,
    (DARK, "green"): GREEN, (DARK, "rose"): RED, (DARK, "teal"): BLUE,
}
_PARTS: Final[dict[str, tuple[str, str]]] = {v: k for k, v in _KEYS.items()}

LOOK_LABELS: Final[dict[str, str]] = {LIGHT: "Light", DARK: "Dark"}
ACCENT_LABELS: Final[dict[str, str]] = {
    "green": "Green", "rose": "Rose", "teal": "Teal"}

#: Human labels for the picker, in display order.
LABELS: Final[dict[str, str]] = {
    key: f"{LOOK_LABELS[_PARTS[key][0]]} · {ACCENT_LABELS[_PARTS[key][1]]}"
    for key in THEMES
}

SETTING_KEY: Final[str] = "ui_theme"
ADOPTED_KEY: Final[str] = "ui_light_adopted"

#: Tokens painter code reads with `token()`; never swapped, not in ui/style.py.
PAINTER_ONLY: Final[frozenset[str]] = frozenset({"WARNING_DOT"})

# Semantic colour and borders in the dark look: today's values, the same in
# all three dark palettes (so the swap holds no pair for them).
_DARK_SEMANTIC: Final[dict[str, str]] = {
    "BORDER":        "rgba(255, 255, 255, 0.09)",
    "BORDER_STRONG": "rgba(255, 255, 255, 0.16)",
    "DANGER":        "#f87171",
    "DANGER_WASH":   "rgba(248, 113, 113, 0.12)",
    "DANGER_LINE":   "rgba(248, 113, 113, 0.35)",
    "WARNING":       "#fbbf24",
    "WARNING_WASH":  "rgba(251, 191, 36, 0.12)",
    "WARNING_LINE":  "rgba(251, 191, 36, 0.32)",
    "INFO":          "#60a5fa",
    "INFO_WASH":     "rgba(96, 165, 250, 0.12)",
    "INFO_LINE":     "rgba(96, 165, 250, 0.32)",
    # The white overlays that lift a row or a pressed chip off a dark card.
    "SHEEN":         "rgba(255, 255, 255, 0.025)",
    "SHEEN_STRONG":  "rgba(255, 255, 255, 0.07)",
    "WARNING_DOT":   "#fbbf24",
}

# The light look's semantic colours and borders (spec manuscript-redesign,
# S8): darker, so each meets WCAG AA on white. Contrast in tests/test_contrast.py.
_LIGHT_SEMANTIC: Final[dict[str, str]] = {
    "BORDER":        "#e1e4ea",     # hairlines only, never a control's edge
    "BORDER_STRONG": "#7a8290",     # control edges: 3:1 on every surface
    "DANGER":        "#b91c1c",
    "DANGER_WASH":   "rgba(185, 28, 28, 0.10)",
    "DANGER_LINE":   "rgba(185, 28, 28, 0.40)",
    "WARNING":       "#92400e",
    "WARNING_WASH":  "rgba(146, 64, 14, 0.10)",
    "WARNING_LINE":  "rgba(146, 64, 14, 0.40)",
    "INFO":          "#1d4ed8",
    "INFO_WASH":     "rgba(29, 78, 216, 0.10)",
    "INFO_LINE":     "rgba(29, 78, 216, 0.40)",
    "SHEEN":         "rgba(20, 24, 31, 0.025)",
    "SHEEN_STRONG":  "rgba(20, 24, 31, 0.06)",
    "WARNING_DOT":   "#b45309",
}

_LIGHT_GREYS: Final[dict[str, str]] = {
    "BG":            "#f4f5f7",
    "SURFACE":       "#ffffff",
    "ELEVATED":      "#eef0f3",
    # The field is marked by its border, not by a darker well.
    "SUNKEN":        "#ffffff",
    "TEXT":          "#14181f",
    "TEXT_DIM":      "#5b6472",
    # The mockup's #6b7482 fails AA on ELEVATED and BG.
    "TEXT_MUTE":     "#636b78",
    "ACCENT_TEXT":   "#ffffff",
}

# The tokens that belong to the theme. Everything else in ui/style.py — the
# radii, the chevron, the fonts — is shared by all of them.
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
    **_DARK_SEMANTIC,
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
    # The phosphor is its own colour in every dark theme, hotter and more
    # saturated than the accent: the accent says "this is current", the
    # phosphor says "you wrote this".
    "PHOSPHOR":      "#ff0033",
    "PHOSPHOR_LINE": "rgba(255, 0, 51, 0.45)",
    "SUNKEN_LIT":    "#270910",
    **_DARK_SEMANTIC,
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
    **_DARK_SEMANTIC,
}


def _light(accent_hex: str, accent_rgb: str, dim_hex: str, dim_rgb: str,
           lit: str) -> dict[str, str]:
    """One light palette. On white the "you wrote this" colour is the deep
    accent: the dark looks' neon phosphor is 1.4:1 on white."""
    return {
        **_LIGHT_GREYS,
        "ACCENT":        accent_hex,
        "ACCENT_DIM":    dim_hex,
        "ACCENT_WASH":   f"rgba({accent_rgb}, 0.10)",
        "ACCENT_LINE":   f"rgba({accent_rgb}, 0.45)",
        "PHOSPHOR":      dim_hex,
        "PHOSPHOR_LINE": f"rgba({dim_rgb}, 0.45)",
        "SUNKEN_LIT":    lit,
        **_LIGHT_SEMANTIC,
    }


_LIGHT_GREEN = _light("#0b7a55", "11, 122, 85", "#086446", "8, 100, 70",
                      "#e8f3ee")
_LIGHT_ROSE = _light("#be123c", "190, 18, 60", "#9f1239", "159, 18, 57",
                     "#fbe9ed")
_LIGHT_TEAL = _light("#0e7490", "14, 116, 144", "#155e75", "21, 94, 117",
                     "#e6f3f6")

PALETTES: Final[dict[str, dict[str, str]]] = {
    LIGHT_GREEN: _LIGHT_GREEN, LIGHT_ROSE: _LIGHT_ROSE,
    LIGHT_TEAL: _LIGHT_TEAL,
    GREEN: _GREEN, RED: _RED, BLUE: _BLUE,
}


def _build_swap() -> dict[str, dict[str, str]]:
    """Authored (green) literal → themed value, per theme.

    Raises if one authored literal would have to become two different values
    in one palette: two tokens sharing an authored value cannot be told apart
    by a swap, and a silent pick would paint one of them the wrong colour.
    """
    swaps: dict[str, dict[str, str]] = {}
    for name, tokens in PALETTES.items():
        pairs: dict[str, str] = {}
        for key, authored in _GREEN.items():
            if key in PAINTER_ONLY:
                continue
            target = tokens[key]
            if pairs.get(authored, target) != target:
                raise ValueError(
                    f"{name}: authored {authored!r} maps to both "
                    f"{pairs[authored]!r} and {target!r}")
            pairs[authored] = target
        swaps[name] = {a: t for a, t in pairs.items() if a != t}
    return swaps


_SWAP: Final[dict[str, dict[str, str]]] = _build_swap()
# One pattern per theme, longest literal first, applied in a single pass so a
# swapped value is never swapped again.
_PATTERN: Final[dict[str, re.Pattern | None]] = {
    name: (re.compile("|".join(re.escape(a) for a in
                               sorted(pairs, key=len, reverse=True)))
           if pairs else None)
    for name, pairs in _SWAP.items()
}

_cached: str | None = None


def look(key: str | None = None) -> str:
    """LIGHT or DARK for a theme key."""
    return _PARTS[key or current()][0]


def accent_of(key: str | None = None) -> str:
    """"green", "rose" or "teal" for a theme key."""
    return _PARTS[key or current()][1]


def compose(look_name: str, accent_name: str) -> str:
    """The theme key for a look and an accent."""
    return _KEYS[(look_name, accent_name)]


def themes_for(look_name: str) -> tuple[str, ...]:
    """The three keys of one look, in accent order."""
    return tuple(_KEYS[(look_name, a)] for a in ACCENTS)


def palette(theme: str | None = None) -> dict[str, str]:
    """The themed tokens under `theme`."""
    return dict(PALETTES[theme or current()])


def token(name: str, theme: str | None = None) -> str:
    """One token's value under `theme`, for painter code."""
    return PALETTES[theme or current()][name]


def recolour(css: str, theme: str | None = None) -> str:
    """Return `css` under `theme`.

    For the sheets and snippets that call sites still build by hand out of
    ``ui.style``'s names. Those names hold the authored (dark green) values,
    so this swaps each one for its counterpart in a single pass.
    """
    name = theme or current()
    pattern = _PATTERN[name]
    if pattern is None:
        return css
    pairs = _SWAP[name]
    return pattern.sub(lambda m: pairs[m.group(0)], css)


def accent(theme: str | None = None) -> str:
    """The accent under `theme`, for painter code that cannot use a sheet."""
    return PALETTES[theme or current()]["ACCENT"]


def current() -> str:
    """The saved theme, defaulting to Light · Green and never raising."""
    global _cached
    if _cached is None:
        try:
            from services.database import get_setting
            saved = get_setting(SETTING_KEY, DEFAULT)
        except Exception:
            saved = DEFAULT
        _cached = saved if saved in THEMES else DEFAULT
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


def adopt_light_once() -> bool:
    """Move a saved dark theme to the light look once; True to show the note.

    Spec manuscript-redesign O2: the first launch with the light look moves a
    saved dark key to the light key with the same accent and tells the user
    once. A fresh install (nothing saved) already gets light and no note.
    ``ui_light_adopted`` is written first, so this happens at most once and a
    later choice of Dark is never overridden. Never raises.
    """
    try:
        from services.database import get_setting, save_setting
        if get_setting(ADOPTED_KEY, ""):
            return False
        save_setting(ADOPTED_KEY, "1")
        saved = get_setting(SETTING_KEY, "")
    except Exception:
        return False
    if saved not in THEMES or look(saved) == LIGHT:
        return False
    set_current(compose(LIGHT, accent_of(saved)))
    return True


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
