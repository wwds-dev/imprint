"""Shared teardown for tests that build a parentless panel or window."""

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
