"""Routing phase 2 (Imprint): the model picker (mockup A) and Settings → Local models (D).

Local models are grouped, described and tagged; they are router candidates from
any provider selection; discovery never runs on the UI thread.
"""

import os
from types import SimpleNamespace

import pytest

from services import local_models as lm
from services.local_models import LocalInventory, LocalModel, Snapshot

GB = 1e9
# The suite's conftest stubs discovery for the whole session; the tests of
# discovery itself need the real function, captured before the stub goes in.
REAL_DISCOVER = lm.discover


class FakeLM:
    def __init__(self, up=True, rows=()):
        self.up, self.rows, self.calls = up, list(rows), 0

    def server_up(self):
        self.calls += 1
        return self.up

    def model_details(self):
        self.calls += 1
        return self.rows


class FakeOllama:
    def __init__(self, details=None, up=True):
        self.details, self.up, self.calls = details or {}, up, 0

    def model_details(self):
        self.calls += 1
        return self.details

    def list_models(self):
        if not self.up:
            raise RuntimeError("down")
        return list(self.details)

    def loaded_models(self):
        return []


ROWS = [
    {"id": "deepseek-r1-distill-qwen-14b-abliterated", "name": "DeepSeek R1 Distill 14B",
     "publisher": "bartowski", "quant": "Q6_K", "size_bytes": 12 * GB, "state": "loaded"},
    {"id": "dolphin-3.0-llama3.1-8b", "name": "Dolphin 3.0 8B", "publisher": "cognitivecomputations",
     "quant": "Q8_0", "size_bytes": 9 * GB, "state": "not-loaded"},
    {"id": "dsr1-32b-iq3", "name": "DeepSeek R1 Distill 32B", "publisher": "x",
     "quant": "IQ3_M", "size_bytes": 15 * GB, "state": "not-loaded"},
]


def snap(up=True, ollama=None, free=12 * GB, total=24 * GB):
    return REAL_DISCOVER(FakeLM(up, ROWS), FakeOllama(ollama or {}),
                       memory=lambda: (free, total), lms_binary=lambda: None)


def test_states_sizes_and_too_big_now():
    s = snap()
    by = {m.id: m for m in s.models}
    assert by["deepseek-r1-distill-qwen-14b-abliterated"].state == "loaded"
    assert by["dolphin-3.0-llama3.1-8b"].state == "on disk, loads on first use"
    assert by["dsr1-32b-iq3"].state == "too big now"       # 15 GB x 1.2 > 12 GB free
    assert snap(up=False).models[1].state == "on disk, server off"


def test_detail_line_has_state_size_rating_and_free_tag():
    s = snap()
    detail = lm.detail_text(s.find("lmstudio", "dolphin-3.0-llama3.1-8b"))
    assert detail == "on disk, loads on first use · 9.0 GB · unrated · €0"
    assert lm.detail_text(s.find("lmstudio", "deepseek-r1-distill-qwen-14b-abliterated")
                          ).startswith("loaded · 12 GB")


def test_rating_hook_replaces_unrated_for_phase_3():
    lm.set_rating_lookup(lambda p, m: "measured 1281" if "14b" in m else None)
    try:
        s = snap()
        assert "measured 1281" in lm.detail_text(
            s.find("lmstudio", "deepseek-r1-distill-qwen-14b-abliterated"))
        assert "unrated" in lm.detail_text(s.find("lmstudio", "dsr1-32b-iq3"))
    finally:
        lm.set_rating_lookup(None)


def test_tags_follow_name_and_publisher():
    s = snap()
    tags = {m.id: m.tag for m in s.models}
    assert tags["deepseek-r1-distill-qwen-14b-abliterated"] == "abliterated"
    assert tags["dolphin-3.0-llama3.1-8b"] == "uncensored"
    assert tags["dsr1-32b-iq3"] is None


def test_sections_are_named_per_runtime():
    s = snap(ollama={"llama3:8b": {"size_bytes": 5 * GB, "quantization": "Q4_0"}})
    assert {r["section"] for r in lm.picker_entries(s, "lmstudio")} == {
        "On this Mac · LM Studio"}
    assert {r["section"] for r in lm.picker_entries(s, "ollama")} == {
        "On this Mac · Ollama"}
    assert lm.SECTION_ORDER == ("On this Mac · LM Studio", "On this Mac · Ollama", "Cloud")


def test_empty_runtimes_say_what_to_do():
    s = REAL_DISCOVER(FakeLM(False, []), FakeOllama({}, up=True),
                    memory=lambda: (1, 2), lms_binary=lambda: None)
    assert lm.empty_section_note(s, "ollama") == "No models · ollama pull …"
    assert "Start" in lm.empty_section_note(s, "lmstudio")
    assert "lms server start" in lm.start_server_hint(
        Snapshot(lms_found=True)) and "LM Studio" in lm.start_server_hint(Snapshot())


def test_the_ui_reads_a_cache_and_never_fetches():
    lmstudio, ollama = FakeLM(True, ROWS), FakeOllama({})
    inv = LocalInventory()
    inv.snapshot(); inv.stale()
    assert lmstudio.calls == 0 and ollama.calls == 0       # reading never fetches
    inv.store(REAL_DISCOVER(lmstudio, ollama, memory=lambda: (1, 2), lms_binary=lambda: None))
    assert lmstudio.calls and len(inv.snapshot().models) == 3


def test_a_broken_runtime_is_an_error_row_not_a_crash():
    class Boom(FakeLM):
        def server_up(self):
            raise OSError("nope")
    s = REAL_DISCOVER(Boom(), FakeOllama({}), memory=lambda: (1, 2), lms_binary=lambda: None)
    assert s.errors and not s.lmstudio_up


def test_table_rows_and_status_chips():
    s = snap(ollama={"llama3:8b": {"size_bytes": 5 * GB, "quantization": "Q4_0"}})
    rows = lm.table_rows(s, {("lmstudio", "dolphin-3.0-llama3.1-8b"): ["Chat", "Write"]})
    assert [r["source"] for r in rows] == ["LM Studio"] * 3 + ["Ollama"]
    dolphin = next(r for r in rows if r["id"] == "dolphin-3.0-llama3.1-8b")
    assert dolphin["used_by"] == "Chat, Write" and dolphin["rating"] == "unrated"
    chips = lm.status_lines(s)
    assert chips["lmstudio"] == "LM Studio server running"
    assert chips["ollama"] == "Ollama running · 1 models"
    assert chips["ram"] == "RAM free 12.0 / 24 GB"


# ── widgets ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_the_dropdown_delegate_draws_sections_once_and_sizes_for_the_detail(qapp):
    from PySide6.QtWidgets import QComboBox, QStyleOptionViewItem, QWidget
    from ui.widgets import (DETAIL_ROLE, LABEL_ROLE, SECTION_ROLE,
                            DropdownItemDelegate)
    parent = QWidget()
    combo = QComboBox(parent)
    entries = lm.picker_entries(snap(), "lmstudio")
    combo.addItems([e["id"] for e in entries])
    for i, e in enumerate(entries):
        combo.setItemData(i, e["section"], SECTION_ROLE)
        combo.setItemData(i, e["label"], LABEL_ROLE)
        combo.setItemData(i, e["detail"], DETAIL_ROLE)
    delegate = DropdownItemDelegate(parent)
    model = combo.model()
    headings = [delegate.section_heading(model.index(i, 0)) for i in range(3)]
    assert headings == ["On this Mac · LM Studio", "", ""]       # one header per section
    assert delegate.row_text(model.index(0, 0)) == "DeepSeek R1 Distill 14B · Q6_K"
    assert combo.itemText(0) == "deepseek-r1-distill-qwen-14b-abliterated"   # id stays the text
    option = QStyleOptionViewItem()
    first = delegate.sizeHint(option, model.index(0, 0))
    second = delegate.sizeHint(option, model.index(1, 0))
    assert first.height() == second.height() + delegate.HEADER_HEIGHT
    plain = QComboBox(parent)
    plain.addItem(entries[1]["id"])
    assert second.width() > delegate.sizeHint(option, plain.model().index(0, 0)).width()


def test_settings_page_lists_models_and_offers_start_when_the_server_is_off(qapp):
    from PySide6.QtWidgets import QWidget
    from ui.local_models_page import LocalModelsPage
    started = []
    host = QWidget()
    page = LocalModelsPage(on_start=lambda: started.append(1), parent=host)
    page.set_snapshot(snap(up=False), {("lmstudio", "dsr1-32b-iq3"): ["Chat"]})
    rows = page.rows()
    assert len(rows) == 3 and rows[0][1] == "LM Studio"
    assert "ABLITERATED" in rows[0][0] and rows[2][5] == "Chat" and rows[2][4] == "unrated"
    assert not page.start_button.isHidden() and not page.hint.isHidden()
    page.start_button.click()
    assert started == [1]
    page.set_snapshot(snap(up=True))
    assert page.start_button.isHidden() and "running" in page.lmstudio_status.text()


# ── the app: BEST FIT from any provider selection ──────────────────────────

@pytest.fixture(scope="module")
def window(qapp):
    import main
    from PySide6.QtWidgets import QMessageBox
    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved


def test_local_models_are_candidates_whatever_provider_is_selected(window, monkeypatch):
    """Imprint counted a local model only while its own provider was selected."""
    window.local_inventory.store(snap())
    window.provider_box.setCurrentText("openai")
    seen = {}
    real = window.recommendation_engine.recommend

    def spy(profile, candidates, context):
        seen.setdefault("candidates", list(candidates))
        return real(profile, candidates, context)

    monkeypatch.setattr(window.recommendation_engine, "recommend", spy)
    window._text_recommendations("chat")
    local = [c for c in seen["candidates"] if c.provider.casefold() == "lmstudio"]
    assert local, "LM Studio models never reached the engine"
    assert all(c.available for c in local)
    assert not [c for c in local if c.model_id == "not-installed"]


def test_models_for_provider_reads_the_cache_and_never_the_server(window, monkeypatch):
    window.local_inventory.store(snap())

    def boom(*a, **k):
        raise AssertionError("the GUI thread asked a server")

    monkeypatch.setattr(window.lmstudio, "list_models", boom)
    monkeypatch.setattr(window.ollama, "list_models", boom)
    assert window.models_for_provider("lmstudio") == [m["id"] for m in ROWS]


def test_apply_picker_roles_marks_rows_and_sections(window):
    from PySide6.QtWidgets import QComboBox
    from ui.widgets import DETAIL_ROLE, LABEL_ROLE, SECTION_ROLE
    window.local_inventory.store(snap())
    box = QComboBox(window)
    box.addItems([m["id"] for m in ROWS])
    window.apply_picker_roles("lmstudio", box)
    assert box.itemData(0, SECTION_ROLE) == "On this Mac · LM Studio"
    assert box.itemData(0, LABEL_ROLE) == "DeepSeek R1 Distill 14B · Q6_K"
    assert "€0" in box.itemData(1, DETAIL_ROLE)
    cloud = QComboBox(window)
    cloud.addItems(["gpt-4.1-mini"])
    window.apply_picker_roles("openai", cloud)
    assert cloud.itemData(0, SECTION_ROLE) == "Cloud"
