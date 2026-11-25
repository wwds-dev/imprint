"""The themes, and the line between theme colour and semantic colour.

Imprint's sheet was already written against tokens, so a theme is a swap of
token values rather than a second sheet. The things worth guarding are that
the swap is complete (nothing written as a literal escapes it), that the two
copies of the green palette have not drifted, and that semantic colour keeps
its value within a look (the dark looks are unchanged; the light look has its
own, darker set — spec manuscript-redesign S8, ADR 0006).
"""

import colorsys
import itertools
import re

import pytest

from ui import style, theme

ACCENT_GREEN = "#34d399"
PHOSPHOR_GREEN = "#00ff41"

#: The accent and phosphor each of the other themes swaps those two for.
OTHERS = {
    theme.RED: ("#f43f5e", "#ff0033"),
    theme.BLUE: ("#22d3ee", "#00ffdd"),
    theme.LIGHT_GREEN: ("#0b7a55", "#086446"),
    theme.LIGHT_ROSE: ("#be123c", "#9f1239"),
    theme.LIGHT_TEAL: ("#0e7490", "#155e75"),
}
DARK = theme.themes_for(theme.DARK)
LIGHT = theme.themes_for(theme.LIGHT)

#: Tokens that follow the accent within a look.
ACCENT_FAMILY = ("ACCENT", "ACCENT_DIM", "ACCENT_WASH", "ACCENT_LINE",
                 "PHOSPHOR", "PHOSPHOR_LINE", "SUNKEN_LIT")
#: Semantic colour and borders: one value per look.
SEMANTIC_KEYS = ("BORDER", "BORDER_STRONG", "DANGER", "DANGER_WASH",
                 "DANGER_LINE", "WARNING", "WARNING_WASH", "WARNING_LINE",
                 "INFO", "INFO_WASH", "INFO_LINE", "SHEEN", "SHEEN_STRONG",
                 "WARNING_DOT")
ACCENT_RED, PHOSPHOR_RED = OTHERS[theme.RED]


def _hue(colour: str) -> float:
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0] * 360

# Colour that means the same thing under both themes.
SEMANTIC = {
    "#f87171": "danger",
    "#fbbf24": "warning",
    "#60a5fa": "informational",
    "rgba(248, 113, 113, 0.12)": "danger wash",
    "rgba(96, 165, 250, 0.32)": "informational line",
}


# ── One palette, not two ──────────────────────────────────────────────

def test_green_palette_matches_the_design_system():
    """ui/style.py documents the colours; ui/theme.py has to agree with it.

    The values are written twice on purpose — style.py reads as the design
    system, with the reasoning beside each colour — so this is what stops the
    two from drifting.
    """
    mismatched = {
        token: (getattr(style, token, None), value)
        for token, value in theme.PALETTES[theme.GREEN].items()
        if token not in theme.PAINTER_ONLY
        and getattr(style, token, None) != value
    }
    assert not mismatched, f"ui/style.py and ui/theme.py disagree: {mismatched}"
    # Painter-only tokens stay out of the sheet's authored names: their dark
    # value equals another token's, so the swap could not tell them apart.
    for token in theme.PAINTER_ONLY:
        assert not hasattr(style, token), token


@pytest.mark.parametrize("name", theme.THEMES)
def test_every_palette_defines_the_same_tokens(name):
    assert set(theme.PALETTES[name]) == set(theme.PALETTES[theme.GREEN])


@pytest.mark.parametrize("left,right", sorted(itertools.combinations(DARK, 2)))
def test_every_dark_grey_and_accent_differs_between_every_dark_pair(left, right):
    """Within the dark look a token that is identical in two accents is one
    that should not be themed — except semantic colour, which is one value
    for the whole look."""
    same = [token for token, value in theme.PALETTES[left].items()
            if token not in SEMANTIC_KEYS
            and theme.PALETTES[right][token] == value]
    assert not same, f"themed but identical in {left} and {right}: {same}"


@pytest.mark.parametrize("left,right", sorted(itertools.combinations(LIGHT, 2)))
def test_the_light_accents_differ_in_the_accent_family_only(left, right):
    """The light look shares one set of greys; only the accent family moves."""
    for token, value in theme.PALETTES[left].items():
        other = theme.PALETTES[right][token]
        if token in ACCENT_FAMILY:
            assert other != value, (token, left, right)
        else:
            assert other == value, (token, left, right)


@pytest.mark.parametrize("accent", theme.ACCENTS)
def test_light_and_dark_differ_in_every_token(accent):
    dark = theme.PALETTES[theme.compose(theme.DARK, accent)]
    light = theme.PALETTES[theme.compose(theme.LIGHT, accent)]
    same = [token for token in dark if dark[token] == light[token]]
    assert not same, f"identical in both looks: {same}"


# ── The swap is complete ──────────────────────────────────────────────

def test_the_sheet_holds_no_themed_colour_as_a_literal():
    """A literal here would not follow the theme, and nothing else would say so."""
    template = re.sub(r"/\*.*?\*/", "", style._STYLESHEET_TEMPLATE, flags=re.S)
    leaked = [value for value in theme.PALETTES[theme.GREEN].values()
              if value in template]
    assert not leaked, f"written into a rule instead of used as a token: {leaked}"


@pytest.mark.parametrize("name", sorted(OTHERS))
def test_theme_replaces_accent_and_phosphor(name):
    sheet = style.global_stylesheet(name)
    expected_accent, expected_phosphor = OTHERS[name]
    assert ACCENT_GREEN not in sheet and expected_accent in sheet
    assert PHOSPHOR_GREEN not in sheet and expected_phosphor in sheet


def test_every_accent_stays_clear_of_the_semantic_blue():
    """Cyan is the closest any theme comes to a semantic colour: 25° away.

    Close it further and an informational badge stops being distinguishable
    from a focus ring.
    """
    for name in theme.THEMES:
        gap = abs(_hue(theme.accent(name)) - _hue(theme.token("INFO", name)))
        assert gap > 20, f"{name}: accent is {gap:.1f}° from INFO"


@pytest.mark.parametrize("colour,meaning", sorted(SEMANTIC.items()))
def test_semantic_colour_survives_every_dark_theme(colour, meaning):
    """Its value is the same in every dark palette, so there is nothing for
    the swap to change: the dark looks are unchanged pixel for pixel."""
    for name in DARK:
        assert theme.recolour(colour, name) == colour, meaning


@pytest.mark.parametrize("colour,meaning", sorted(SEMANTIC.items()))
def test_semantic_colour_is_one_value_across_the_light_accents(colour, meaning):
    """Light needs darker values on white, but one per look: the meaning
    never follows the accent."""
    swapped = {theme.recolour(colour, name) for name in LIGHT}
    assert len(swapped) == 1, meaning
    assert swapped != {colour}, meaning


@pytest.mark.parametrize("colour,meaning", [
    ("#f87171", "danger"), ("#fbbf24", "warning"),
    ("rgba(248, 113, 113, 0.12)", "danger wash"),
])
def test_semantic_colour_reaches_the_rendered_sheet(colour, meaning):
    """The ones the sheet actually paints must read the same in both themes.

    INFO is deliberately not here: it is a token the Python side uses, and no
    rule in the sheet carries it.
    """
    for name in DARK:
        assert colour in style.global_stylesheet(name), meaning


@pytest.mark.parametrize("token", ["DANGER", "WARNING", "DANGER_WASH"])
def test_light_semantic_colour_reaches_the_rendered_sheet(token):
    for name in LIGHT:
        sheet = style.global_stylesheet(name)
        assert theme.token(token, name) in sheet, token
        assert getattr(style, token) not in sheet, token


def test_recolour_swaps_the_authored_value():
    assert theme.recolour(f"color: {ACCENT_GREEN};", theme.RED) == \
        f"color: {ACCENT_RED};"
    assert theme.recolour(f"color: {ACCENT_GREEN};", theme.GREEN) == \
        f"color: {ACCENT_GREEN};"


def test_accent_and_phosphor_stay_apart_in_both_themes():
    """They make different claims, so they must not collapse to one colour."""
    for name in theme.THEMES:
        tokens = theme.PALETTES[name]
        assert tokens["ACCENT"] != tokens["PHOSPHOR"]


def test_accent_helper_matches_the_sheet():
    for name in theme.THEMES:
        assert theme.accent(name) in style.global_stylesheet(name)


# ── Persistence ───────────────────────────────────────────────────────

def test_saved_theme_round_trips():
    try:
        theme.set_current(theme.RED)
        theme.forget()
        assert theme.current() == theme.RED
    finally:
        theme.set_current(theme.GREEN)


def test_unknown_theme_is_refused():
    with pytest.raises(ValueError):
        theme.set_current("chartreuse")


def test_current_falls_back_to_light_green(monkeypatch):
    """A junk value in the database must not leave the app unstyled; the
    fallback is the default look (D4)."""
    theme.forget()
    monkeypatch.setattr("services.database.get_setting", lambda *a, **k: "chartreuse")
    assert theme.current() == theme.LIGHT_GREEN == theme.DEFAULT
    theme.forget()


# ── Look × Accent ─────────────────────────────────────────────────────

def test_the_dark_keys_keep_their_saved_strings():
    """A theme saved before the light look must still be valid."""
    assert theme.themes_for(theme.DARK) == ("green", "red", "blue")
    assert theme.themes_for(theme.LIGHT) == (
        "light-green", "light-rose", "light-teal")
    assert theme.THEMES == theme.themes_for(theme.LIGHT) + theme.themes_for(theme.DARK)


@pytest.mark.parametrize("key", theme.THEMES)
def test_look_and_accent_compose_back_to_the_key(key):
    assert theme.compose(theme.look(key), theme.accent_of(key)) == key


def test_labels_name_the_look_and_the_accent():
    assert theme.LABELS[theme.LIGHT_GREEN] == "Light · Green"
    assert theme.LABELS[theme.RED] == "Dark · Rose"
    assert theme.LABELS[theme.BLUE] == "Dark · Teal"


def test_a_literal_shared_by_two_tokens_is_refused(monkeypatch):
    """Two tokens with one authored literal cannot be told apart by a swap;
    building the swap must fail rather than pick one."""
    green = dict(theme._GREEN, EXTRA=theme._GREEN["WARNING"])
    light = dict(theme._LIGHT_GREEN, EXTRA="#123456")
    monkeypatch.setattr(theme, "_GREEN", green)
    monkeypatch.setattr(theme, "PALETTES", {theme.LIGHT_GREEN: light})
    with pytest.raises(ValueError, match="maps to both"):
        theme._build_swap()


def test_a_swapped_value_is_never_swapped_again():
    """One pass: the light BORDER_STRONG must not be re-swapped by a later
    pair whose authored literal happens to equal it."""
    for name in theme.THEMES:
        for authored, themed in theme._SWAP[name].items():
            assert theme.recolour(authored, name) == themed, (name, authored)


def test_warning_dot_is_painter_only():
    for name in DARK:
        assert theme.token("WARNING_DOT", name) == theme.token("WARNING", name)
    assert theme.token("WARNING_DOT", theme.LIGHT_GREEN) == "#b45309"
    for pairs in theme._SWAP.values():
        assert theme._GREEN["WARNING_DOT"] not in pairs or \
            theme._GREEN["WARNING_DOT"] == theme._GREEN["WARNING"]


# ── O2: the first launch with the light look ──────────────────────────

@pytest.fixture
def settings_store(monkeypatch):
    """The two settings adopt_light_once reads, in memory."""
    store = {}
    monkeypatch.setattr("services.database.get_setting",
                        lambda key, default="": store.get(key, default))
    monkeypatch.setattr("services.database.save_setting",
                        lambda key, value: store.__setitem__(key, value))
    theme.forget()
    yield store
    theme.forget()


@pytest.mark.parametrize("saved,moved_to", [
    ("green", "light-green"), ("red", "light-rose"), ("blue", "light-teal")])
def test_a_saved_dark_theme_moves_to_light_once(settings_store, saved, moved_to):
    settings_store[theme.SETTING_KEY] = saved
    assert theme.adopt_light_once() is True
    assert settings_store[theme.SETTING_KEY] == moved_to
    assert settings_store[theme.ADOPTED_KEY] == "1"
    # Second launch: nothing moves, no note.
    assert theme.adopt_light_once() is False
    assert settings_store[theme.SETTING_KEY] == moved_to


def test_a_fresh_install_gets_light_and_no_note(settings_store):
    assert theme.adopt_light_once() is False
    assert settings_store[theme.ADOPTED_KEY] == "1"
    assert theme.current() == theme.LIGHT_GREEN


def test_a_later_dark_choice_is_never_overridden(settings_store):
    settings_store[theme.SETTING_KEY] = "red"
    assert theme.adopt_light_once() is True
    settings_store[theme.SETTING_KEY] = "blue"          # the user picks Dark
    theme.forget()
    assert theme.adopt_light_once() is False
    assert settings_store[theme.SETTING_KEY] == "blue"


def test_a_saved_light_theme_is_left_alone(settings_store):
    settings_store[theme.SETTING_KEY] = "light-rose"
    assert theme.adopt_light_once() is False
    assert settings_store[theme.SETTING_KEY] == "light-rose"


# ── The live switch ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question,
             QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question,
         QMessageBox.information) = saved
        theme.set_current(theme.GREEN)


def test_switching_theme_repaints_the_sheets_built_by_hand(window):
    """The sheets call sites set themselves must not be left behind.

    They are applied once at build time, so without the registry behind
    `theme.themed` the spotlight, the status cards and the collapsible headers
    keep the old accent until the next launch — the one failure of this feature
    a screenshot would show and a unit test would miss.
    """
    assert theme._registered, "nothing registered; theme.themed went unused"

    for name, (expected_accent, _) in OTHERS.items():
        theme.set_current(name)
        window.apply_global_style()
        assert ACCENT_GREEN not in window.styleSheet()
        assert expected_accent in window.styleSheet()
        for ref, _ in theme._registered:
            widget = ref()
            if widget is not None:
                assert ACCENT_GREEN not in widget.styleSheet()

    theme.set_current(theme.GREEN)
    window.apply_global_style()
    assert ACCENT_GREEN in window.styleSheet()
    assert ACCENT_RED not in window.styleSheet()


def test_repaint_drops_widgets_that_have_gone():
    """A registered sheet must not keep its widget alive."""
    from PySide6.QtWidgets import QLabel

    before = len(theme._registered)
    label = QLabel()
    theme.themed(label, f"color: {ACCENT_GREEN};")
    assert len(theme._registered) == before + 1
    del label
    theme.repaint()
    assert len(theme._registered) == before


def test_settings_picker_previews_live_and_cancel_puts_it_back(window, monkeypatch):
    """Choosing a theme repaints at once; Cancel is a real undo.

    The preview writes the setting straight away so the window can repaint, so
    the restore on `rejected` is the only thing between a glance at the other
    theme and being stuck in it.
    """
    from PySide6.QtWidgets import QComboBox, QDialog
    from ui import dialogs

    opened = []
    monkeypatch.setattr(QDialog, "exec", lambda self: opened.append(self) or 0)

    theme.set_current(theme.GREEN)
    window.apply_global_style()
    dialogs.show_settings(window)
    dialog = opened[0]

    picker = dialog.findChild(QComboBox, "ThemePick")
    assert picker is not None, "the theme picker is not in the Settings dialog"
    assert picker.currentData() == theme.GREEN

    picker.setCurrentIndex(list(theme.THEMES).index(theme.RED))
    assert theme.current() == theme.RED
    assert ACCENT_RED in window.styleSheet()

    dialog.reject()
    assert theme.current() == theme.GREEN
    assert ACCENT_GREEN in window.styleSheet()

# ── The dots ──────────────────────────────────────────────────────────

def _press(dots, index):
    """A real left-click on the centre of dot `index`."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    where = QPointF(dots._centre(index), dots.height() / 2)
    dots.mousePressEvent(QMouseEvent(
        QEvent.MouseButtonPress, where, dots.mapToGlobal(where),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))


def test_the_dots_carry_one_dot_per_accent(window):
    dots = window.theme_dots
    assert dots.isVisible() or dots.parentWidget() is not None
    # Every dot has to be reachable: the hit test walks slots, so a dot the
    # geometry does not account for would silently never be clickable.
    assert {dots._at(dots._centre(i)) for i in range(len(theme.ACCENTS))} == \
        set(range(len(theme.ACCENTS)))


def test_clicking_a_dot_wears_that_theme(window):
    """The click has to reach the window, not just the setting."""
    try:
        for look in theme.LOOKS:
            theme.set_current(theme.compose(look, "green"))
            window.apply_global_style()
            for index, name in enumerate(theme.themes_for(look)):
                _press(window.theme_dots, index)
                assert theme.current() == name
                assert theme.accent(name) in window.styleSheet()
    finally:
        theme.set_current(theme.GREEN)
        window.apply_global_style()


def test_clicking_the_current_dot_changes_nothing(window):
    """No repaint, no write — a click on what you already have is a no-op."""
    theme.set_current(theme.GREEN)
    window.apply_global_style()
    before = window.styleSheet()
    _press(window.theme_dots, list(theme.themes_for(theme.DARK)).index(theme.GREEN))
    assert theme.current() == theme.GREEN
    assert window.styleSheet() == before


def test_arrow_keys_step_through_the_themes(window):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    try:
        theme.set_current(theme.GREEN)
        dots = window.theme_dots
        for key, step in ((Qt.Key_Right, 1), (Qt.Key_Left, -1)):
            theme.set_current(theme.GREEN)
            dark = theme.themes_for(theme.DARK)
            expected = dark[step % len(dark)]
            dots.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))
            assert theme.current() == expected, key
    finally:
        theme.set_current(theme.GREEN)
        window.apply_global_style()


# ── The copy ──────────────────────────────────────────────────────────

def test_appearance_copy_counts_the_looks_and_accents_that_ship():
    """It said "two themes … in both" for a week after Blue shipped. The
    sentence now counts LOOKS and ACCENTS and names each label, so adding one
    cannot leave it stale again."""
    from ui import dialogs

    text = dialogs.appearance_intro()
    assert "in both" not in text
    assert "two looks" in text and "three accents" in text
    for label in (*theme.LOOK_LABELS.values(), *theme.ACCENT_LABELS.values()):
        assert label in text
    assert "every theme" in text
    assert "never changes" not in text
