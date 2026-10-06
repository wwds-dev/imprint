"""A blinking underscore where Qt would draw a caret.

Imprint takes this and nothing else. Sentinel has a matching module that also
carries a moving backdrop and varies the caret's cadence by theme; that is
Sentinel's character, deliberately not Imprint's — this is a tool people write
books in, and a texture moving behind a draft is not atmosphere, it is
interference. The themes here differ in colour and in nothing else.

An underscore rather than a block: half of a block caret's cycle is a hole
punched in your own sentence, which reads as a blinking blank space. An
underscore sits under the line instead of on top of it, so nothing you typed
disappears while you are looking at it.

Why the caret is painted here at all: Qt draws a text caret itself and offers
no way to style one. A style sheet reaches the text, the selection and the
border, never the cursor. What Qt does offer is ``QTextEdit.setCursorWidth(0)``,
which removes it — so the underscore is drawn by a transparent child of the
viewport instead. ``QLineEdit`` has no such switch and no way to suppress its
bar, so single-line fields keep Qt's native caret; the underscore is for the
surfaces you actually compose in.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QEvent, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

from ui import theme

#: The authored phosphor; ui.theme turns it with everything else.
PHOSPHOR = "#00ff41"


def caret_alpha(elapsed_ms: float) -> float:
    """How bright the underscore is, this many milliseconds in.

    One cadence, a terminal's: on for about half of a 1.2s cycle, hard edges.
    It does not vary by theme — the caret belongs to the phosphor, and the
    phosphor is the same idea in all three.
    """
    return 1.0 if (elapsed_ms % 1200) < 620 else 0.0


class UnderscoreCaret(QWidget):
    """A blinking underscore standing in for a QTextEdit's own caret.

    Install with `install_caret`. Lives as a child of the edit's viewport, so
    it paints over the text rather than under it, and takes no mouse events.
    """

    THICKNESS = 2
    TICK_MS = 60

    def __init__(self, edit):
        super().__init__(edit.viewport())
        self._edit = edit
        self._started = time.monotonic()
        self._alpha = 0.0

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.hide()

        edit.setCursorWidth(0)          # Qt's own caret steps aside
        edit.installEventFilter(self)
        edit.cursorPositionChanged.connect(self._reposition)
        edit.textChanged.connect(self._reposition)
        edit.verticalScrollBar().valueChanged.connect(self._reposition)
        edit.horizontalScrollBar().valueChanged.connect(self._reposition)

        self._timer = QTimer(self)
        self._timer.setInterval(self.TICK_MS)
        self._timer.timeout.connect(self._tick)

        if edit.hasFocus():
            self._start()

    # ── lifecycle ─────────────────────────────────────────────────────
    def _start(self) -> None:
        self._started = time.monotonic()
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start()

    def _stop(self) -> None:
        self._timer.stop()
        self.hide()

    def eventFilter(self, watched, event):
        if watched is self._edit:
            if event.type() == QEvent.FocusIn:
                self._start()
            elif event.type() == QEvent.FocusOut:
                self._stop()
            elif event.type() in (QEvent.Resize, QEvent.Show):
                self._reposition()
        return False

    # ── placement ─────────────────────────────────────────────────────
    def _reposition(self) -> None:
        if not self._edit.hasFocus():
            return
        rect = self._edit.cursorRect()
        metrics = QFontMetrics(self._edit.font())
        width = max(6, metrics.horizontalAdvance("0"))
        self.setGeometry(QRect(
            rect.left(),
            rect.bottom() - self.THICKNESS + 1,
            width,
            self.THICKNESS,
        ))

    def _tick(self) -> None:
        elapsed = (time.monotonic() - self._started) * 1000.0
        alpha = caret_alpha(elapsed)
        if abs(alpha - self._alpha) > 0.01:
            self._alpha = alpha
            self.update()

    def paintEvent(self, event):
        if self._alpha <= 0.01:
            return
        colour = QColor(theme.recolour(PHOSPHOR))
        colour.setAlphaF(min(1.0, self._alpha))
        painter = QPainter(self)
        painter.fillRect(self.rect(), colour)


def install_caret(edit) -> UnderscoreCaret:
    """Give one editable QTextEdit an underscore caret."""
    return UnderscoreCaret(edit)


def install_carets(root) -> list:
    """Give every editable QTextEdit under `root` an underscore caret.

    Read-only edits are skipped: they are previews, logs and transcripts, and
    they are the same ones the phosphor rules skip, for the same reason — the
    caret marks where *you* are typing.
    """
    from PySide6.QtWidgets import QTextEdit

    installed = []
    for edit in root.findChildren(QTextEdit):
        if edit.isReadOnly() or edit.property("underscoreCaret"):
            continue
        edit.setProperty("underscoreCaret", True)
        installed.append(install_caret(edit))
    return installed
