"""The only way the shell moves anything (calm rule D5; ADR 0006, decision 7).

Spec manuscript-redesign D5 keeps the 2026-10-06 rule — nothing moves in a
pane someone is working in — and allows motion only when it answers the user's
own action, lasts 300 ms or less, does not loop, and is outside the field
being typed in. All of it stops under Reduce Motion: macOS's setting or the
in-app one.

- ``system_reduce_motion()`` reads ``NSWorkspace.accessibilityDisplayShouldReduceMotion``
  through ``ctypes`` (Qt has no API for it, QTBUG-133042; no PyObjC). It is
  False off macOS, offscreen, or on any failure, and is re-read when the app
  becomes active, never cached beyond that.
- ``reduced()`` adds the in-app setting ``reduce_motion``.
- ``animate()`` refuses more than 300 ms and any loop; when motion is reduced,
  or a text field outside the animated widget has focus, it applies the end
  value at once and returns None. Live animations are tracked in
  ``running()``, stopped when their widget hides, and by ``stop_all()`` at
  shutdown. No QThread, no QTimer loop.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
import weakref
from typing import Any, Callable

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QVariantAnimation

MAX_MS = 300
SETTING_KEY = "reduce_motion"

_system: bool | None = None
_live: list[QVariantAnimation] = []
_installed_app: weakref.ref | None = None


def _read_system_setting() -> bool:
    if sys.platform != "darwin":
        return False
    if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
        return False
    try:
        objc = ctypes.cdll.LoadLibrary(
            ctypes.util.find_library("objc") or "/usr/lib/libobjc.A.dylib")
        ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/AppKit.framework/AppKit")
        get_class = objc.objc_getClass
        get_class.restype = ctypes.c_void_p
        get_class.argtypes = [ctypes.c_char_p]
        register = objc.sel_registerName
        register.restype = ctypes.c_void_p
        register.argtypes = [ctypes.c_char_p]
        # Own prototypes over objc_msgSend's address: appkit_guard gives the
        # shared symbol its own restype, and the two must not fight over it.
        address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        send_id = ctypes.CFUNCTYPE(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
        send_bool = ctypes.CFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(address)
        send_responds = ctypes.CFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p)(address)

        workspace_class = get_class(b"NSWorkspace")
        if not workspace_class:
            return False
        workspace = send_id(workspace_class, register(b"sharedWorkspace"))
        if not workspace:
            return False
        selector = register(b"accessibilityDisplayShouldReduceMotion")
        if not send_responds(workspace, register(b"respondsToSelector:"),
                             selector):
            return False
        return bool(send_bool(workspace, selector))
    except Exception:
        return False


def system_reduce_motion() -> bool:
    """macOS's Reduce Motion, read once per activation. Never raises."""
    global _system
    if _system is None:
        _system = _read_system_setting()
    return _system


def forget_system_setting() -> None:
    """Read the system setting again next time (the app became active)."""
    global _system
    _system = None


def in_app_setting() -> bool:
    try:
        from services.database import get_setting
        return get_setting(SETTING_KEY, "0") == "1"
    except Exception:
        return False


def set_in_app_setting(on: bool) -> None:
    from services.database import save_setting
    save_setting(SETTING_KEY, "1" if on else "0")


def reduced() -> bool:
    """True when nothing may move: the system setting or the in-app one."""
    return system_reduce_motion() or in_app_setting()


def install(app) -> None:
    """Re-read the system setting whenever the app becomes active."""
    global _installed_app
    if _installed_app is not None and _installed_app() is app:
        return
    from PySide6.QtCore import Qt

    def _on_state(state):
        if state == Qt.ApplicationState.ApplicationActive:
            forget_system_setting()

    app.applicationStateChanged.connect(_on_state)
    _installed_app = weakref.ref(app)


def running() -> list[QVariantAnimation]:
    """The animations that are live now."""
    alive = []
    for animation in _live:
        try:
            if animation.state() == QVariantAnimation.State.Running:
                alive.append(animation)
        except RuntimeError:
            continue
    _live[:] = alive
    return list(alive)


def stop_all() -> None:
    """Stop every live animation (GodAI.shutdown, tests)."""
    for animation in list(_live):
        try:
            animation.stop()
        except RuntimeError:
            pass
    _live.clear()


def _typing_elsewhere(target) -> bool:
    """A text field outside `target` has focus: D5 says nothing moves."""
    from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QLineEdit,
                                   QPlainTextEdit, QTextEdit)
    focus = QApplication.focusWidget()
    if focus is None or not isinstance(
            focus, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
        return False
    if isinstance(focus, (QTextEdit, QPlainTextEdit)) and focus.isReadOnly():
        return False
    return not (focus is target or target.isAncestorOf(focus))


class _StopOnHide(QObject):
    """Stops a widget's animations when it hides."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Hide:
            for animation in list(_live):
                try:
                    if animation.property("motionTarget") is obj:
                        animation.stop()
                except RuntimeError:
                    continue
        return False


_hide_filter: _StopOnHide | None = None


def animate(target, start: Any, end: Any, ms: int,
            on_value: Callable[[Any], None], *,
            loops: int = 1,
            on_finished: Callable[[], None] | None = None,
            easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
            ) -> QVariantAnimation | None:
    """Move `target` from `start` to `end` over `ms`, calling `on_value`.

    Returns the running animation, or None when the end value was applied at
    once (motion reduced, or someone typing outside `target`).
    """
    global _hide_filter
    if ms > MAX_MS:
        raise ValueError(f"{ms} ms is longer than the {MAX_MS} ms D5 allows")
    if loops != 1:
        raise ValueError("D5: shell motion never loops")
    if ms <= 0 or reduced() or _typing_elsewhere(target):
        on_value(end)
        if on_finished is not None:
            on_finished()
        return None

    animation = QVariantAnimation(target)
    animation.setProperty("motionTarget", target)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setDuration(int(ms))
    animation.setLoopCount(1)
    animation.setEasingCurve(easing)
    animation.valueChanged.connect(on_value)

    def _done():
        try:
            _live.remove(animation)
        except ValueError:
            pass
        if on_finished is not None:
            on_finished()

    animation.finished.connect(_done)
    if _hide_filter is None:
        _hide_filter = _StopOnHide()
    target.installEventFilter(_hide_filter)
    _live.append(animation)
    animation.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation
