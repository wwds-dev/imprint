"""Connection onboarding states what connecting GRANTS, then how.

Contract: every publisher declares scopes in the user's words and numbered
setup steps; the guide leads with scopes, lists the exact credential keys,
and is empty for drafting-only platforms; the Accounts tab renders it.
"""

import os

import pytest

from agents.social import publishing


def test_every_publisher_declares_scopes_and_steps():
    for key, publisher in publishing.PUBLISHERS.items():
        assert publisher.scopes, f"{key} has no scopes"
        assert publisher.setup_steps, f"{key} has no setup steps"


def test_guide_leads_with_grants_then_steps():
    guide = publishing.connection_guide("reddit")
    assert guide.index("lets Imprint") < guide.index("To connect:")
    assert "scope: submit" in guide
    # The honest warning about what the script flow holds.
    assert "password" in guide.lower()
    assert "REDDIT_CLIENT_ID" in guide
    assert "1." in guide and "2." in guide


def test_guide_is_empty_for_drafting_only_platforms():
    assert publishing.connection_guide("x") == ""
    assert publishing.connection_guide("") == ""


def test_youtube_guide_says_uploads_stay_private():
    guide = publishing.connection_guide("youtube")
    assert "PRIVATE" in guide
    assert "youtube.upload" in guide


@pytest.fixture(scope="module")
def app():
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


def test_accounts_tab_shows_scopes_and_steps(window):
    panel = window.social_panel
    panel.refresh_accounts()
    text = panel.social_accounts_box.toPlainText()
    assert "This connection lets Imprint:" in text
    assert "scope: submit" in text          # reddit's grant, in plain words
    assert "To connect:" in text
    assert "PINTEREST_ACCESS_TOKEN" in text
