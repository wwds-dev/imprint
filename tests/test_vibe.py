"""The underscore caret, and the line Imprint does not cross.

Imprint takes the caret and nothing else. Sentinel's matching module also
carries a moving backdrop and varies the caret's cadence by theme; this one
must not grow either, so there is a test for that too — the useful kind of
guard, because the pressure to port "just the nice bit" across is what would
turn a writing tool into a toy.
"""

import os

import pytest

from ui import theme, vibe


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def edit(app):
    from PySide6.QtWidgets import QTextEdit

    box = QTextEdit()
    box.resize(360, 90)
    box.setStyleSheet("QTextEdit { font-family: Menlo, monospace; font-size: 13px }")
    caret = vibe.install_caret(box)
    box.show()
    yield box, caret
    box.deleteLater()


# ── Cadence ───────────────────────────────────────────────────────────

def test_one_cadence_for_every_theme():
    """A terminal's square wave, 1.2s, and the same in all three themes.

    The caret belongs to the phosphor, and the phosphor is the same idea under
    every theme — only its colour changes.
    """
    assert vibe.caret_alpha(0) == 1.0
    assert vibe.caret_alpha(610) == 1.0
    assert vibe.caret_alpha(630) == 0.0
    assert vibe.caret_alpha(1210) == 1.0


def test_imprint_keeps_only_the_caret():
    """No backdrop here, and no per-theme cadence. Both are Sentinel's.

    If this fails because someone ported one across, that is the decision this
    test exists to make them take deliberately.
    """
    assert not hasattr(vibe, "VibeBackdrop")
    assert not hasattr(vibe, "install_backdrop")
    assert vibe.caret_alpha.__code__.co_argcount == 1, "cadence must not take a theme"


# ── The caret ─────────────────────────────────────────────────────────

def test_qt_own_caret_is_switched_off(edit):
    """Otherwise you compose against two carets at once.

    This is the reason the underscore is painted rather than styled: Qt gives
    a style sheet no way at the cursor, only `setCursorWidth`.
    """
    box, _ = edit
    assert box.cursorWidth() == 0


def test_the_caret_follows_focus(edit, app):
    box, caret = edit
    box.setFocus()
    app.processEvents()
    assert caret.isVisible()
    box.clearFocus()
    app.processEvents()
    assert not caret.isVisible()


def test_the_caret_sits_under_the_line_not_over_it(edit, app):
    """An underscore, which is the whole reason it replaced the block."""
    box, caret = edit
    box.setPlainText("a quiet chapter about rain")
    box.setFocus()
    app.processEvents()
    assert caret.height() == caret.THICKNESS <= 2
    assert caret.width() >= 6
    assert caret.geometry().bottom() >= box.cursorRect().bottom() - 1


def test_the_caret_moves_with_the_cursor(edit, app):
    from PySide6.QtGui import QTextCursor

    box, caret = edit
    box.setPlainText("a quiet chapter about rain")
    box.setFocus()
    app.processEvents()
    at_start = caret.geometry().left()

    cursor = box.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    box.setTextCursor(cursor)
    app.processEvents()
    assert caret.geometry().left() > at_start


@pytest.mark.parametrize("name", theme.THEMES)
def test_the_caret_is_painted_in_the_theme_phosphor(name):
    from PySide6.QtGui import QColor

    theme.set_current(name)
    try:
        expected = theme.PALETTES[name]["PHOSPHOR"]
        assert QColor(theme.recolour(vibe.PHOSPHOR)).name() == QColor(expected).name()
    finally:
        theme.set_current(theme.GREEN)


# ── The sweep ─────────────────────────────────────────────────────────

def test_every_editable_text_box_gets_one_and_no_other(app):
    """Read-only edits are previews, logs and transcripts — not yours to type in.

    They are the same ones the phosphor rules skip, for the same reason.
    """
    from PySide6.QtWidgets import QMessageBox, QTextEdit
    import main

    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        window = main.GodAI()
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved

    boxes = window.findChildren(QTextEdit)
    editable = [box for box in boxes if not box.isReadOnly()]
    assert editable, "no composing surfaces found; the sweep would be vacuous"
    assert len(window._carets) == len(editable)
    assert all(box.cursorWidth() == 0 for box in editable)
    assert all(box.cursorWidth() != 0 for box in boxes if box.isReadOnly())


def test_the_sweep_does_not_double_up(app):
    """Running it twice must not leave two carets stacked on one field."""
    from PySide6.QtWidgets import QTextEdit, QWidget
    from PySide6.QtWidgets import QVBoxLayout

    host = QWidget()
    layout = QVBoxLayout(host)
    layout.addWidget(QTextEdit())
    try:
        assert len(vibe.install_carets(host)) == 1
        assert len(vibe.install_carets(host)) == 0
    finally:
        host.deleteLater()
