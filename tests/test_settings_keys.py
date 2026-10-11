"""Settings → API keys: paste, Test, Save — and the running window uses the key.

The Qt half of the feature (2026-10-11); `tests/test_api_keys.py` is the
file-and-process half. Every test points `services.api_keys.env_path` at a
tmp file, so the checkout's own .env is never read for display or written.
The conftest has already emptied every credential in the environment, and
each test that sets one does so through monkeypatch, so it is put back.
"""

from __future__ import annotations

import os

import pytest

from services import api_keys
from services.database import get_connection


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question, QMessageBox.information) = saved


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.setattr(api_keys, "env_path", lambda: path)
    monkeypatch.setattr(api_keys, "template_path", lambda: tmp_path / "no-template")
    return path


@pytest.fixture
def quiet_reload(window, monkeypatch):
    """Save rebuilds the clients; keep that off the network and count it."""
    calls = []
    monkeypatch.setattr(window, "load_provider_models", lambda: None)
    monkeypatch.setattr(window, "check_for_new_models", lambda: None)
    real = window.reload_provider_clients
    monkeypatch.setattr(window, "reload_provider_clients",
                        lambda: (calls.append(True), real())[1])
    return calls


def _open_settings(window, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from ui import dialogs
    opened = []
    monkeypatch.setattr(QDialog, "exec", lambda self: opened.append(self) or 0)
    dialogs.show_settings(window)
    return opened[0]


def _tab(dialog, title):
    from PySide6.QtWidgets import QTabWidget
    tabs = dialog.findChild(QTabWidget, "SettingsTabs")
    for i in range(tabs.count()):
        if tabs.tabText(i) == title:
            tabs.setCurrentIndex(i)
            return tabs.widget(i)
    raise AssertionError(f"no {title!r} tab")


def _field(dialog, name):
    from PySide6.QtWidgets import QLineEdit
    edit = dialog.findChild(QLineEdit, f"Key:{name}")
    assert edit is not None, f"no field for {name}"
    return edit


def _save(dialog):
    from PySide6.QtWidgets import QPushButton
    dialog.findChild(QPushButton, "SettingsSave").click()


def test_the_tab_has_a_field_for_every_credential_and_hides_secrets(window, monkeypatch, env_file):
    from PySide6.QtWidgets import QLineEdit, QPushButton
    dialog = _open_settings(window, monkeypatch)
    _tab(dialog, "API keys")
    for cred in api_keys.CREDENTIALS:
        edit = _field(dialog, cred.name)
        expected = QLineEdit.EchoMode.Password if cred.secret else QLineEdit.EchoMode.Normal
        assert edit.echoMode() == expected, cred.name
        button = dialog.findChild(QPushButton, f"TestKey:{cred.name}")
        assert (button is not None) == bool(cred.probe), f"Test button for {cred.name}"
    dialog.reject()


def test_show_keys_reveals_and_hides(window, monkeypatch, env_file):
    from PySide6.QtWidgets import QCheckBox, QLineEdit
    dialog = _open_settings(window, monkeypatch)
    show = dialog.findChild(QCheckBox, "ShowKeys")
    edit = _field(dialog, "OPENAI_API_KEY")
    username = _field(dialog, "REDDIT_USERNAME")
    show.setChecked(True)
    assert edit.echoMode() == QLineEdit.EchoMode.Normal
    show.setChecked(False)
    assert edit.echoMode() == QLineEdit.EchoMode.Password
    assert username.echoMode() == QLineEdit.EchoMode.Normal, "a username was never hidden"
    dialog.reject()


def test_fields_show_the_file_not_the_shell(window, monkeypatch, env_file):
    """The page edits the file; a shell-set key is reported, not copied in."""
    from PySide6.QtWidgets import QLabel
    env_file.write_text("OPENAI_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-shell")
    dialog = _open_settings(window, monkeypatch)
    assert _field(dialog, "OPENAI_API_KEY").text() == "from-file"
    assert _field(dialog, "DEEPSEEK_API_KEY").text() == ""
    labels = [l.text() for l in dialog.findChildren(QLabel)]
    assert any("set by the shell" in text for text in labels)
    dialog.reject()


def test_save_writes_the_file_applies_to_the_process_and_rebuilds_clients(
        window, monkeypatch, env_file, quiet_reload):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    before = window.anthropic
    dialog = _open_settings(window, monkeypatch)
    _field(dialog, "ANTHROPIC_API_KEY").setText("sk-ant-test-value")
    _save(dialog)
    assert api_keys.read_values(env_file)["ANTHROPIC_API_KEY"] == "sk-ant-test-value"
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-test-value"
    assert quiet_reload == [True]
    assert window.anthropic is not before, "the client must be rebuilt with the new key"
    assert window.api_keys_status_card.status_labels["anthropic"].text() == "Configured"
    with get_connection() as conn:
        rows = conn.execute("SELECT COUNT(*) FROM settings WHERE value LIKE ?",
                            ("%sk-ant-test%",)).fetchone()[0]
    assert rows == 0, "a key must never reach the settings table"
    # tidy: the module-scoped window keeps the rebuilt client; put the env back
    api_keys.apply({"ANTHROPIC_API_KEY": ""})
    window.reload_provider_clients()


def test_save_all_with_nothing_changed_leaves_the_file_alone(window, monkeypatch, env_file, quiet_reload):
    env_file.write_text("OPENAI_API_KEY=keep\n", encoding="utf-8")
    stamp = env_file.stat().st_mtime_ns
    dialog = _open_settings(window, monkeypatch)
    _save(dialog)
    assert env_file.stat().st_mtime_ns == stamp
    assert env_file.read_text(encoding="utf-8") == "OPENAI_API_KEY=keep\n"
    assert quiet_reload == []


def test_clearing_a_key_empties_it_in_the_file_and_the_process(window, monkeypatch, env_file, quiet_reload):
    env_file.write_text("KIMI_API_KEY=old\n", encoding="utf-8")
    monkeypatch.setenv("KIMI_API_KEY", "old")
    dialog = _open_settings(window, monkeypatch)
    _field(dialog, "KIMI_API_KEY").setText("")
    _save(dialog)
    assert api_keys.read_values(env_file)["KIMI_API_KEY"] == ""
    assert "KIMI_API_KEY" not in os.environ
    assert window.api_keys_status_card.status_labels["kimi"].text() == "Not configured"
    window.reload_provider_clients()


def test_test_button_with_an_empty_box_says_not_set_without_a_worker(window, monkeypatch, env_file):
    from PySide6.QtWidgets import QLabel, QPushButton
    dialog = _open_settings(window, monkeypatch)
    _field(dialog, "GOOGLE_API_KEY").setText("")
    dialog.findChild(QPushButton, "TestKey:GOOGLE_API_KEY").click()
    labels = [l.text() for l in dialog.findChildren(QLabel)]
    assert "not set" in labels
    dialog.reject()


def test_test_button_probes_the_typed_key_and_leaves_the_process_alone(app, window, monkeypatch, env_file):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLabel, QPushButton
    monkeypatch.setenv("ANTHROPIC_API_KEY", "saved-key")
    seen = []

    class Fake:
        def __init__(self):
            seen.append(os.environ.get("ANTHROPIC_API_KEY"))
        def list_models_live(self):
            return ["claude-x"]

    monkeypatch.setattr(api_keys, "_client", lambda kind: Fake())
    dialog = _open_settings(window, monkeypatch)
    _field(dialog, "ANTHROPIC_API_KEY").setText("typed-key")
    button = dialog.findChild(QPushButton, "TestKey:ANTHROPIC_API_KEY")
    button.click()
    assert not button.isEnabled(), "disabled while the probe runs"
    for _ in range(100):                      # the worker thread answers within a few ms
        QTest.qWait(20)
        if button.isEnabled():
            break
    assert button.isEnabled()
    assert seen == ["typed-key"], "the probe must see the typed value"
    assert os.environ["ANTHROPIC_API_KEY"] == "saved-key", "and the process keeps its own"
    labels = [l.text() for l in dialog.findChildren(QLabel)]
    assert any(text.startswith("reachable — 1 model(s)") for text in labels)
    dialog.reject()


def test_reload_provider_clients_refreshes_the_rail_tile(window, monkeypatch):
    monkeypatch.setattr(window, "load_provider_models", lambda: None)
    monkeypatch.setattr(window, "check_for_new_models", lambda: None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    window.reload_provider_clients()
    assert window.api_keys_status_card.status_labels["deepseek"].text() == "Configured"
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    window.reload_provider_clients()
    assert window.api_keys_status_card.status_labels["deepseek"].text() == "Not configured"
