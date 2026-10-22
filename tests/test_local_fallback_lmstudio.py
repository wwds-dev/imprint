"""Budget-cap fallback and key probes know LM Studio, not only Ollama."""

import os
from types import SimpleNamespace

import pytest

from services import api_keys, local_models as lm

GB = 1e9


def _snap(models):
    return lm.Snapshot(models=tuple(models), ram_free_bytes=16 * GB,
                       ram_total_bytes=24 * GB)


def _m(provider, ident, *, loaded=False, fit="ok", size=5 * GB):
    return lm.LocalModel(provider=provider, id=ident, name=ident, size_bytes=size,
                         loaded=loaded, fit=fit)


def _host(models):
    import main
    inv = lm.LocalInventory()
    inv.store(_snap(models))
    return SimpleNamespace(local_inventory=inv), main.GodAI._installed_local_models


def test_installed_local_models_come_from_the_inventory_best_first():
    host, installed = _host([
        _m("lmstudio", "big", fit="too_big"),
        _m("lmstudio", "tight-one", fit="tight"),
        _m("lmstudio", "dolphin"),
        _m("ollama", "llama3:8b"),
        _m("lmstudio", "resident", loaded=True),
    ])
    assert installed(host) == [("lmstudio", "resident"), ("ollama", "llama3:8b"),
                               ("lmstudio", "dolphin"), ("lmstudio", "tight-one")]


def test_nothing_installed_means_no_offer():
    host, installed = _host([_m("lmstudio", "big", fit="too_big")])
    assert installed(host) == []


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _offer_host(models, providers):
    import main
    from PySide6.QtWidgets import QComboBox, QWidget
    parent = QWidget()
    pbox, mbox = QComboBox(parent), QComboBox(parent)
    pbox.addItems(providers)
    mbox.addItem("claude-sonnet-5-5")
    inv = lm.LocalInventory()
    inv.store(_snap(models))
    marked = []
    host = SimpleNamespace(
        local_inventory=inv, _find_control=lambda n: {"p": pbox, "m": mbox}[n],
        _find_model_index=lambda box, wanted: box.findText(wanted),
        _set_route_result=lambda *a: marked.append(a))
    host._installed_local_models = lambda: main.GodAI._installed_local_models(host)
    return parent, host, pbox, mbox, marked


def test_budget_offer_switches_to_lm_studio_when_only_it_has_a_model(qapp, monkeypatch):
    import main
    from PySide6.QtWidgets import QMessageBox
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: asked.append(a[2]) or QMessageBox.Yes))
    monkeypatch.setitem(main.AGENT_SETUP_WIDGETS, "t", ("p", "m"))
    parent, host, pbox, mbox, marked = _offer_host(
        [_m("lmstudio", "dolphin")], ["openai", "ollama", "lmstudio"])
    ok = main.GodAI._offer_local_fallback(
        host, "t", "openai", SimpleNamespace(scope="daily_cap", reason="Daily cap."), None)
    assert ok and pbox.currentText() == "lmstudio" and mbox.currentText() == "dolphin"
    assert "(LM Studio)" in asked[0] and marked == [("t", "lmstudio", "dolphin")]


def test_budget_offer_needs_a_local_provider_the_panel_offers(qapp, monkeypatch):
    import main
    monkeypatch.setitem(main.AGENT_SETUP_WIDGETS, "t", ("p", "m"))
    parent, host, *_ = _offer_host([_m("lmstudio", "dolphin")], ["openai", "ollama"])
    assert not main.GodAI._offer_local_fallback(
        host, "t", "openai", SimpleNamespace(scope="daily_cap", reason="x"), None)


def test_lmstudio_is_a_key_probe_and_a_stopped_server_does_not_read_as_reachable():
    assert "lmstudio" in api_keys.PROBES
    client, note = api_keys.prepare_probe("lmstudio")
    assert client is not None and note == ""
    down = SimpleNamespace(server_up=lambda: False, list_models=lambda: ["disk-model"])
    ok, text = api_keys.run_probe("lmstudio", down)
    assert not ok and "server off" in text
    up = SimpleNamespace(server_up=lambda: True, list_models=lambda: ["a", "b"])
    assert api_keys.run_probe("lmstudio", up) == (True, "2 model(s)")
    empty = SimpleNamespace(server_up=lambda: True, list_models=lambda: [])
    assert api_keys.run_probe("lmstudio", empty)[0] is False
