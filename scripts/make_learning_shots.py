"""Regenerate the Learning Centre screenshots.

    .venv/bin/python scripts/make_learning_shots.py

Runs the real window offscreen and grabs each panel, so the images in
`docs/learn/img/` are produced by the current code rather than pasted in and
left to rot. Re-run it after any UI change and commit whatever moves.

Offscreen on purpose: no display needed, so it works over SSH and in CI, and
the output is deterministic rather than depending on the machine's window
manager. `QMessageBox` is stubbed for the same reason a test stubs it — the
Audiobooks panel opens a modal when its input folder holds no ebooks, and a
modal with nobody to click it blocks forever.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OUT_DIR = PROJECT_ROOT / "docs" / "learn" / "img"

# Wide enough that nothing is scrolled out of frame, which is what a reader
# needs from a reference screenshot.
WINDOW = (1760, 1080)

def _show_tab(tabs, label: str) -> None:
    """Switch a QTabWidget to the tab captioned `label`.

    By caption, not index: inserting a tab shifts every index after it, and a
    wrong index still grabs *a* tab, so the screenshot silently shows the wrong
    page — Social's Accounts shot was capturing Analytics that way. A caption
    that no longer exists raises instead.

    Also scrolls the tab widget into view: Creator's tabs sit below a form that
    grew past the window, and a selected tab whose page is off-screen makes a
    screenshot of the form instead.
    """
    from PySide6.QtWidgets import QScrollArea

    captions = [tabs.tabText(i) for i in range(tabs.count())]
    if label not in captions:
        raise LookupError(f"no tab {label!r}; tabs are {captions}")
    tabs.setCurrentIndex(captions.index(label))
    parent = tabs.parentWidget()
    while parent is not None and not isinstance(parent, QScrollArea):
        parent = parent.parentWidget()
    if parent is not None:
        parent.ensureWidgetVisible(tabs, 0, 0)


# (filename, agent key, optional setup callable)
#
# Setups reach each control through the panel that owns it — since the
# 2026-09-21 extractions the window carries no aliases for panel widgets.
# tests/test_learning_shots.py runs every setup, so drift fails the suite
# instead of this script.
SHOTS: list[tuple[str, str, object]] = [
    ("workspace-draft.png", "author", None),
    ("workspace-publish.png", "author",
     lambda w: (w.author_panel.set_mode("pubmkt"),
                w.author_panel.set_sub_mode("publish"))),
    ("workspace-market.png", "author",
     lambda w: (w.author_panel.set_mode("pubmkt"),
                w.author_panel.set_sub_mode("market"))),
    ("agent-manuscript.png", "manuscript", None),
    ("agent-music.png", "music", None),
    ("agent-webdesign.png", "webdesign", None),
    ("agent-fiverr.png", "fiverr", None),
    ("agent-video.png", "video", None),
    ("agent-video-library.png", "video",
     lambda w: _show_tab(w.video_panel.video_tabs, "Library")),
    ("agent-social.png", "social", None),
    ("agent-social-accounts.png", "social",
     lambda w: _show_tab(w.social_panel.social_tabs, "Accounts")),
    ("agent-creator.png", "creator", None),
    ("agent-creator-earnings.png", "creator",
     lambda w: _show_tab(w.creator_panel.creator_tabs, "Earnings")),
    ("agent-audiobook-listen.png", "audiobook",
     lambda w: _show_tab(w.audiobook_panel.audiobook_tabs, "Listen")),
]


def main() -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    import main as app_main

    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)

    try:
        app = QApplication.instance() or QApplication([])
        window = app_main.GodAI()
        # Without vidforge the Video panel is a notice, not the workspace —
        # the shots would document an error. A worktree has no vidforge/
        # (it is its own git-ignored repo), so this is the usual way in.
        if not window.video_panel._available:
            print("vidforge is not importable from this checkout; the Video "
                  "shots would show the unavailable notice. Run from a "
                  "checkout with vidforge/ in it.", file=sys.stderr)
            return 1
        window.show()
        _settle(app)
        window.resize(*WINDOW)
        _settle(app)

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for filename, agent, setup in SHOTS:
            window.select_agent(agent)
            _settle(app)
            if setup is not None:
                setup(window)
                _settle(app)
            path = OUT_DIR / filename
            window.grab().save(str(path))
            print(f"  wrote {path.relative_to(PROJECT_ROOT)}")
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved

    print(f"\n{len(SHOTS)} screenshots written to {OUT_DIR.relative_to(PROJECT_ROOT)}")
    return 0


def _settle(app, rounds: int = 8) -> None:
    """Let Qt finish laying out before grabbing — a grab taken too early
    catches widgets at their pre-layout geometry."""
    for _ in range(rounds):
        app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
