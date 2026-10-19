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


def _post_now(window, monkeypatch, typed):
    """Drive Post on a Reddit draft up to "Post now?", answering No.
    Returns (questions asked, warnings shown, input prompts seen)."""
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    class Ready:
        configured = True

        def publish(self, *a, **k):
            raise AssertionError("nothing may be posted here")

    panel = window.social_panel
    monkeypatch.setattr(panel, "_selected_post", lambda: {
        "id": 1, "platform": "reddit", "status": "draft", "body": "b",
        "media_path": ""})
    monkeypatch.setattr(publishing, "publisher_for", lambda key: Ready())
    prompts = []
    answers = iter([(typed, True), ("A title", True)])
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(
        lambda _p, title, *a, **k: prompts.append(title) or next(answers)))
    asked, warned = [], []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda _p, title, text, *a, **k: asked.append((title, text))
        or QMessageBox.No))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(
        lambda _p, title, text, *a, **k: warned.append((title, text))))
    panel.post_selected()
    return asked, warned, prompts


def test_post_now_names_the_subreddit_it_will_post_to(window, monkeypatch):
    """Security review P3-5: the confirmation said only "Reddit", so the
    community a public post lands in was never shown before it went out."""
    asked, warned, _prompts = _post_now(window, monkeypatch, " R/rust ")
    assert warned == []
    assert asked == [("Post now?", "This publishes to r/rust on Reddit from "
                      "your own account, immediately.\n\nContinue?")]


def test_post_now_refuses_a_name_that_is_not_a_subreddit(window, monkeypatch):
    asked, warned, prompts = _post_now(window, monkeypatch, "r/r/rust")
    assert asked == [] and prompts == ["Subreddit"]       # no title asked
    (title, text), = warned
    assert title == "Not a subreddit"
    assert "is not a subreddit name" in text


def test_reddit_token_requests_only_the_submit_scope(monkeypatch):
    """The guide promises "submit, nothing else"; the password flow mints a
    full-scope token unless the request says otherwise."""
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"access_token": "tok"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["data"] = kwargs.get("data") or {}
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    assert publishing.PUBLISHERS["reddit"]._token() == "tok"
    assert captured["data"].get("scope") == "submit"


def test_env_example_lists_every_credential_a_publisher_needs():
    """The in-app guide named these correctly while `.env.example` listed only
    the model providers — so the one file a fresh checkout copies was the one
    place a publishing credential could not be found. Keep them in step: this
    reads the requirement off the publishers rather than a second hardcoded
    list, so adding a publisher fails here until its keys are in the template.
    """
    from pathlib import Path

    template = (Path(__file__).resolve().parents[1] / ".env.example"
                ).read_text(encoding="utf-8")
    required = {name for publisher in publishing.PUBLISHERS.values()
                for name in publisher.required_env}
    missing = sorted(name for name in required
                     if f"\n{name}=" not in f"\n{template}")
    assert not missing, f".env.example does not list: {', '.join(missing)}"
