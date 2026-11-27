"""Shared teardown for tests that build a parentless panel or window."""

import warnings

from PySide6.QtCore import QCoreApplication, QEvent


def dispose(widget):
    """Delete a parentless widget now rather than leaving it to the cyclic
    collector. Freed inside a later `gc.collect()`, its combos are destroyed
    while the app-wide `_DropdownPolisher` still filters their events, and
    the suite segfaulted there (2026-11-20, -21 and -22, seed 2481708264).

    The flush names the widget as receiver: an app-wide flush also destroys
    other tests' pending deletions (see tests/test_release_kit_e2e.py)."""
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(widget, QEvent.Type.DeferredDelete)


def live_windows(window_class) -> list:
    """The live top-level `window_class` windows."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return []
    return [w for w in app.topLevelWidgets() if isinstance(w, window_class)]


def dispose_windows(windows) -> int:
    """Delete these `main.GodAI` windows now; return how many.

    A dropped `main.GodAI` is never freed by the collector: bound methods
    and closures held by long-lived objects keep its wrapper reachable, so
    its C++ side lived on, each one still an application-wide event filter
    with about 88 top-level widgets. By the middle of a CI run 70 windows and
    6,571 top-level widgets were alive; `qWait` stalled for up to 6.9 s in
    `GodAI.eventFilter` and the runner was killed for memory (exit 137).

    The order matters. Workers are stopped first (`stop_all`, the quit path's
    cancel-and-wait, never `terminate()`), so no thread emits into a window
    being destroyed. Then each window stops being an app filter and stops its
    timers before it is deleted, and the flush names each window as receiver
    (see `dispose`). `closeEvent` is not called: it can open a modal box.
    The Python wrapper may outlive this; it no longer owns any Qt object.

    Deleting a window used to segfault the next module's `qWait`: a
    context-less `QTimer.singleShot` lambda fired on the deleted panel, and
    its RuntimeError reached Shiboken inside the next Python application
    event filter. App timers now name a context
    (`tests/test_single_shot_context.py`)."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from ui.worker_registry import stop_all

    app = QApplication.instance()
    windows = list(windows)
    if app is None or not windows:
        return 0
    # Process-wide on purpose: the test (or module) that built these windows
    # is over, so any worker still running is its leftover.
    still_running = stop_all()
    if still_running:
        # Never delete a host under a live worker. The windows are only
        # retired; the warning names the worker so it can be fixed.
        warnings.warn(f"workers still running after stop_all: "
                      f"{', '.join(still_running)}; their windows were "
                      "retired, not deleted", RuntimeWarning, stacklevel=2)
    from ui import text_fit
    callback = getattr(text_fit._FILTER, "explanations_enabled", None)
    cells = getattr(callback, "__closure__", None) or ()
    if any(cell.cell_contents is window for cell in cells for window in windows):
        text_fit._FILTER.explanations_enabled = None   # no deleted window's toggle
    for window in windows:
        try:
            app.removeEventFilter(window)
            for timer in window.findChildren(QTimer):
                timer.stop()
            panel = getattr(window, "audiobook_panel", None)
            player = getattr(panel, "audiobook_player", None)
            if player is not None:
                player.release()
            window.hide()
            if still_running:
                continue
            window.deleteLater()
            QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
        except RuntimeError:
            continue                    # its C++ side is already gone
    return 0 if still_running else len(windows)
