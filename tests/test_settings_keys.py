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


def _restore_env_after_save(monkeypatch):
    """Save calls api_keys.apply, which writes os.environ directly for every
    field (typed ones set, blank ones popped). Record each name first, so
    monkeypatch puts the conftest's value back when the test ends."""
    for cred in api_keys.CREDENTIALS:
        for name in (cred.name, *cred.aliases):
            monkeypatch.setenv(name, os.environ.get(name, ""))


def _status_beside(field):
    """The SettingsHelp label in the same grid row as `field`."""
    from PySide6.QtWidgets import QLabel
    grid = field.parentWidget().layout()
    row = grid.getItemPosition(grid.indexOf(field))[0]
    status = grid.itemAtPosition(row, 2).widget()
    assert isinstance(status, QLabel)
    return status


def _wait_until(condition, timeout_ms=5000):
    """Spin the event loop until `condition()` holds (the rows refresh 400 ms
    after typing stops); a fixed sleep is slow when idle and flaky under load."""
    from PySide6.QtTest import QTest
    for _ in range(timeout_ms // 20):
        if condition():
            return
        QTest.qWait(20)
    assert condition()


def _click_test_and_wait(dialog, name):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton
    button = dialog.findChild(QPushButton, f"TestKey:{name}")
    button.click()
    for _ in range(250):                      # the worker thread answers within a few ms
        if button.isEnabled():
            break
        QTest.qWait(20)
    assert button.isEnabled()


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
    _restore_env_after_save(monkeypatch)
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
    _restore_env_after_save(monkeypatch)
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


def test_workspace_id_field_explains_itself_and_never_blocks_save(app, window, monkeypatch, env_file, quiet_reload):
    from PySide6.QtTest import QTest
    _restore_env_after_save(monkeypatch)
    dialog = _open_settings(window, monkeypatch)
    field = _field(dialog, "DASHSCOPE_WORKSPACE_ID")
    status = _status_beside(field)
    field.setText("a.evil.com")
    QTest.qWait(600)                                   # past the 400 ms pause
    assert "letters, digits and hyphens only" in status.text()
    assert status.property("status") == "warning"
    field.setText("ws1")
    QTest.qWait(600)
    assert status.text() == "Chat will use ws1.ap-southeast-1.maas.aliyuncs.com"
    _field(dialog, "DASHSCOPE_BASE_URL").setText("https://x.example/v1")
    QTest.qWait(600)
    assert "takes priority" in status.text()
    _save(dialog)
    assert "DASHSCOPE_WORKSPACE_ID=ws1" in env_file.read_text()
    dialog.reject()
    # tidy: the module-scoped window keeps the rebuilt Qwen client; rebuild it on blanks
    api_keys.apply({"DASHSCOPE_WORKSPACE_ID": "", "DASHSCOPE_BASE_URL": ""})
    window.reload_provider_clients()


def test_endpoint_rows_warn_about_http_and_foreign_hosts_but_still_save(
        app, window, monkeypatch, env_file, quiet_reload):
    from PySide6.QtTest import QTest
    _restore_env_after_save(monkeypatch)
    dialog = _open_settings(window, monkeypatch)
    chat, video = _field(dialog, "DASHSCOPE_BASE_URL"), _field(dialog, "DASHSCOPE_VIDEO_BASE_URL")
    chat_status, video_status = _status_beside(chat), _status_beside(video)
    assert chat_status.text() == "default"
    chat.setText("http://my.example/v1")
    video.setText("https://dashscope-intl.aliyuncs.com/api/v1")
    QTest.qWait(600)                                   # past the 400 ms pause
    assert "not https" in chat_status.text() and "not an Alibaba Cloud host" in chat_status.text()
    assert chat_status.property("status") == "warning"
    assert "my.example" not in chat_status.text()
    assert video_status.text() == "default", "an Alibaba https address gets no warning"
    _save(dialog)
    assert "DASHSCOPE_BASE_URL=http://my.example/v1" in env_file.read_text(), "warned, never blocked"
    dialog.reject()
    api_keys.apply({"DASHSCOPE_BASE_URL": "", "DASHSCOPE_VIDEO_BASE_URL": ""})
    window.reload_provider_clients()


def test_a_pasted_two_line_value_is_refused_and_the_file_is_unchanged(
        app, window, monkeypatch, env_file, quiet_reload):
    """Pasting "ws2<newline>DASHSCOPE_BASE_URL=…" must not plant a second line."""
    from PySide6.QtWidgets import QMessageBox
    _restore_env_after_save(monkeypatch)
    env_file.write_text("DASHSCOPE_WORKSPACE_ID=ws1\n", encoding="utf-8")
    before = env_file.read_bytes()
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a[2])))
    dialog = _open_settings(window, monkeypatch)
    field = _field(dialog, "DASHSCOPE_WORKSPACE_ID")
    field.clear()
    field.insert("ws2\nDASHSCOPE_BASE_URL=https://evil.example/v1")    # what paste() does
    assert "\n" in field.text(), "the box keeps the line break, which is the case guarded"
    _field(dialog, "OPENAI_API_KEY").setText("sk-would-be-saved")
    _save(dialog)
    assert env_file.read_bytes() == before, "nothing on the page is written"
    assert quiet_reload == [] and os.environ["OPENAI_API_KEY"] == ""
    assert os.environ["DASHSCOPE_BASE_URL"] == "" and os.environ["DASHSCOPE_WORKSPACE_ID"] == ""
    assert len(warnings) == 1
    assert "Qwen workspace ID must be one line only" in warnings[0]
    assert "evil.example" not in warnings[0] and "sk-would" not in warnings[0]
    assert _status_beside(field).text() == "one line only — not saved"
    dialog.reject()


def test_the_workspace_row_keeps_saying_the_shell_sets_the_id(app, window, monkeypatch, env_file):
    """Shell ws2 and file ws1: the process uses ws2, so the row must not
    describe the box's ws1 as the host chat will use."""
    env_file.write_text("DASHSCOPE_WORKSPACE_ID=ws1\n", encoding="utf-8")
    monkeypatch.setenv("DASHSCOPE_WORKSPACE_ID", "ws2")
    dialog = _open_settings(window, monkeypatch)
    field = _field(dialog, "DASHSCOPE_WORKSPACE_ID")
    status = _status_beside(field)
    assert field.text() == "ws1"
    assert "set by the shell" in status.text() and "ws1" not in status.text()
    field.setText("ws3")                      # a new value is what Save would write
    _wait_until(lambda: "ws3" in status.text())
    assert status.text() == "Chat will use ws3.ap-southeast-1.maas.aliyuncs.com"
    field.setText("")
    _wait_until(lambda: "ws3" not in status.text())
    assert "set by the shell" in status.text()
    field.setText("ws3")
    _wait_until(lambda: "ws3" in status.text())
    field.setText("ws1")                      # back to the file's value
    _wait_until(lambda: "ws3" not in status.text())
    assert "set by the shell" in status.text()
    dialog.reject()


def test_a_failed_qwen_test_names_no_host(app, window, monkeypatch, env_file):
    from services import qwen_client

    def refuse(self):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(qwen_client.QwenClientWrapper, "list_models_live", refuse)
    dialog = _open_settings(window, monkeypatch)
    key = _field(dialog, "DASHSCOPE_API_KEY")
    key.setText("test-not-a-real-key")
    _field(dialog, "DASHSCOPE_WORKSPACE_ID").setText("ws1")
    _click_test_and_wait(dialog, "DASHSCOPE_API_KEY")
    assert _status_beside(key).text() == "unreachable — RuntimeError: upstream unavailable"
    assert _status_beside(key).property("status") == "warning"
    dialog.reject()


_INTL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
_WS1 = "https://ws1.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
_CHINA = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_LOOKALIKE = "https://x.maas.aliyuncs.com.evil.com/compatible-mode/v1"
_INTL_TYPED = "https://DashScope-Intl.aliyuncs.com/compatible-mode/v1/"


@pytest.mark.parametrize("shell_id,typed_id,typed_url,probed,where", [
    ("", "ws1", "", _WS1, "via workspace host"),
    ("", "", "", _INTL, "via standard host"),
    ("", "a.evil.com", "", _INTL, "via standard host (workspace ID ignored)"),
    ("ws1", "", "", _INTL, "via standard host"),       # a blank box masks the shell's ID
    ("", "ws1", _CHINA, _CHINA, "via dashscope.aliyuncs.com"),
    ("", "", _LOOKALIKE, _LOOKALIKE, "via x.maas.aliyuncs.com.evil.com"),
    # the standard host typed by hand (any case, trailing slash) is still the standard host
    ("", "ws1", _INTL_TYPED, _INTL_TYPED, "via standard host (workspace ID ignored)"),
])
def test_qwen_test_probes_the_typed_id_and_names_the_host(
        app, window, monkeypatch, env_file, shell_id, typed_id, typed_url, probed, where):
    """Test builds the real Qwen client from the boxes; only the network
    call is replaced, so the base URL asserted is the one it would call."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton
    from services import qwen_client
    monkeypatch.setenv("DASHSCOPE_WORKSPACE_ID", shell_id)
    seen = []
    monkeypatch.setattr(qwen_client.QwenClientWrapper, "list_models_live",
                        lambda self: seen.append(self.base_url) or ["qwen-x"])
    dialog = _open_settings(window, monkeypatch)
    key = _field(dialog, "DASHSCOPE_API_KEY")
    key.setText("test-not-a-real-key")
    _field(dialog, "DASHSCOPE_WORKSPACE_ID").setText(typed_id)
    _field(dialog, "DASHSCOPE_BASE_URL").setText(typed_url)
    button = dialog.findChild(QPushButton, "TestKey:DASHSCOPE_API_KEY")
    button.click()
    for _ in range(250):                      # the worker thread answers within a few ms
        if button.isEnabled():
            break
        QTest.qWait(20)
    assert button.isEnabled()
    assert seen == [probed]
    assert _status_beside(key).text() == f"reachable — 1 model(s) {where}"
    assert os.environ["DASHSCOPE_WORKSPACE_ID"] == shell_id, "the process keeps its own"
    assert os.environ.get("DASHSCOPE_BASE_URL", "") == ""
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
