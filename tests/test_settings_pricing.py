"""Regression coverage for the complete Settings pricing catalog."""

from __future__ import annotations

import os
import sqlite3

import pytest


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _pricing_connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE pricing (
            backend TEXT NOT NULL,
            model TEXT NOT NULL,
            input_per_1m_usd REAL NOT NULL DEFAULT 0,
            output_per_1m_usd REAL NOT NULL DEFAULT 0,
            cached_input_per_1m_usd REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (backend, model)
        )
    """)
    return conn


def test_catalog_exposes_every_provider_even_when_database_only_has_anthropic():
    from services.pricing_catalog import build_token_price_catalog

    conn = _pricing_connection()
    conn.execute(
        "INSERT INTO pricing VALUES ('anthropic', 'default', 3, 15, 0)"
    )
    entries = build_token_price_catalog(conn)

    providers = {entry.provider for entry in entries}
    assert providers == {
        "openai", "anthropic", "deepseek", "kimi", "gemini", "qwen", "ollama"
    }
    assert any(entry.provider == "openai" and entry.model == "gpt-4.1" for entry in entries)
    assert any(entry.provider == "ollama" and entry.status == "Local compute" for entry in entries)


def test_unpriced_models_are_unknown_not_free():
    from services.pricing_catalog import build_token_price_catalog

    conn = _pricing_connection()
    entries = build_token_price_catalog(conn)
    openai = next(entry for entry in entries if entry.provider == "openai")
    assert openai.input_usd is None
    assert openai.output_usd is None
    assert openai.status == "Price unknown"


def test_settings_dialog_has_searchable_complete_pricing_tables(app, monkeypatch):
    from PySide6.QtWidgets import QComboBox, QDialog, QLineEdit, QTableWidget, QWidget
    from services.database import init_db
    from services.registry import Registry
    from ui.dialogs import show_settings

    init_db()
    monkeypatch.setattr(QDialog, "exec", lambda self: None)

    class Host(QWidget):
        def __init__(self):
            super().__init__()
            self.registry = Registry()
            self.session_budget_eur = 1.0
            self.daily_budget_eur = 5.0

        def update_usage_labels(self): ...

    dialog = show_settings(Host())
    table = dialog.findChild(QTableWidget, "SettingsPricingTable")
    per_unit = dialog.findChild(QTableWidget, "SettingsPerUnitTable")
    provider_filter = dialog.findChild(QComboBox, "PricingProviderFilter")
    search = dialog.findChild(QLineEdit, "PricingSearch")

    assert table is not None and table.rowCount() >= 20
    assert per_unit is not None and per_unit.rowCount() >= 6
    assert search is not None
    assert {provider_filter.itemText(i) for i in range(provider_filter.count())} >= {
        "OpenAI", "Anthropic", "DeepSeek", "Kimi", "Gemini", "Qwen", "Ollama"
    }

    provider_filter.setCurrentText("OpenAI")
    shown = [row for row in range(table.rowCount()) if not table.isRowHidden(row)]
    assert shown
    assert {table.item(row, 0).text() for row in shown} == {"OpenAI"}

    search.setText("gpt-4.1")
    shown = [row for row in range(table.rowCount()) if not table.isRowHidden(row)]
    assert shown
    assert all("gpt-4.1" in table.item(row, 1).text() for row in shown)



# ── The price table cannot fall behind the model lists again ────────────────
# Found 2026-10-07: claude-fable-5-1 billed at the $3/$15 default instead of
# $10/$50, gpt-4o at gpt-4o-mini's rate, deepseek-v4-pro at ~1/9 of its price —
# each because an offered model had no row of its own. These pin the rules.

PROVIDERS = ("openai", "anthropic", "gemini", "deepseek", "kimi", "qwen")


def _json_table():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    return json.loads((root / "config" / "pricing.json").read_text())


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_offered_model_has_a_price_of_its_own(provider):
    from services.recommendations.catalog import known_text_models
    table = _json_table()[provider]
    missing = [m for m in known_text_models(provider) if m not in table]
    assert not missing, (
        f"{provider}: offered offline but billed at the provider default: {missing}")


@pytest.mark.parametrize("provider", PROVIDERS)
def test_the_default_row_is_the_dearest_rate(provider):
    """An unpriced (new) model is over-, never under-estimated."""
    table = _json_table()[provider]
    default = table["default"]
    for model, row in table.items():
        assert row["input_per_1m_usd"] <= default["input_per_1m_usd"], model
        assert row["output_per_1m_usd"] <= default["output_per_1m_usd"], model


def test_a_dated_snapshot_or_alias_bills_at_its_models_rate():
    from services.pricing_catalog import has_exact_price, resolve_price_row
    conn = _pricing_connection()
    conn.executemany("INSERT INTO pricing VALUES (?,?,?,?,?)", [
        ("openai", "default", 10, 50, 1),
        ("openai", "gpt-4o", 2.5, 10, 1.25),
        ("anthropic", "claude-haiku-4-5-20251001", 1, 5, 0.1),
        ("gemini", "gemini-3.8-flash", 0.75, 3.75, 0.075),
    ])
    row, source = resolve_price_row(conn, "openai", "gpt-4o-2024-08-06")
    assert (source, row["input_per_1m_usd"]) == ("alias", 2.5)
    row, source = resolve_price_row(conn, "anthropic", "claude-haiku-4-5")
    assert (source, row["input_per_1m_usd"]) == ("alias", 1)
    row, source = resolve_price_row(conn, "gemini", "gemini-3.8-flash-001")
    assert source == "alias"
    row, source = resolve_price_row(conn, "openai", "gpt-9-preview")
    assert (source, row["input_per_1m_usd"]) == ("default", 10)
    assert resolve_price_row(conn, "kimi", "kimi-k9") == (None, "unknown")
    assert has_exact_price(conn, "openai", "gpt-4o-2024-08-06")
    assert not has_exact_price(conn, "openai", "gpt-9-preview")


def _seeded_database(tmp_path, monkeypatch):
    from services import database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "imprint.db")
    db.init_db()
    return db


def test_stale_shipped_rates_are_corrected_and_edits_are_not(tmp_path, monkeypatch):
    db = _seeded_database(tmp_path, monkeypatch)
    conn = db.get_connection()
    # Put back two shipped-stale values and one user edit, then re-run.
    conn.execute("UPDATE pricing SET input_per_1m_usd=1.65, output_per_1m_usd=4.951 "
                 "WHERE backend='qwen' AND model='qwen3.8-max'")
    conn.execute("UPDATE pricing SET input_per_1m_usd=0.15, output_per_1m_usd=0.6 "
                 "WHERE backend='openai' AND model='default'")
    conn.execute("UPDATE pricing SET input_per_1m_usd=7, output_per_1m_usd=9 "
                 "WHERE backend='qwen' AND model='default'")          # a user edit
    conn.execute("DELETE FROM settings WHERE key='pricing_correction_2026_10'")
    conn.commit()
    db._correct_pricing_2026_10(conn)
    rate = lambda b, m: tuple(conn.execute(
        "SELECT input_per_1m_usd, output_per_1m_usd FROM pricing "
        "WHERE backend=? AND model=?", (b, m)).fetchone())
    assert rate("qwen", "qwen3.8-max") == (2.0, 6.0)
    assert rate("openai", "default") == (10.0, 50.0)
    assert rate("qwen", "default") == (7.0, 9.0)
    conn.close()


def test_scheduled_price_changes_apply_on_their_date_only(tmp_path, monkeypatch):
    db = _seeded_database(tmp_path, monkeypatch)
    conn = db.get_connection()
    rate = lambda: tuple(conn.execute(
        "SELECT input_per_1m_usd, output_per_1m_usd, cached_input_per_1m_usd "
        "FROM pricing WHERE backend='gemini' AND model='gemini-3.8-flash'").fetchone())
    db._apply_scheduled_pricing(conn, today="2026-12-31")
    assert rate() == (0.75, 3.75, 0.075)
    db._apply_scheduled_pricing(conn, today="2027-01-01")
    assert rate() == (1.5, 7.5, 0.15)
    db._apply_scheduled_pricing(conn, today="2027-06-01")       # idempotent
    assert rate() == (1.5, 7.5, 0.15)
    conn.close()


def test_the_model_guide_lists_what_the_app_offers_at_what_it_bills(tmp_path,
                                                                    monkeypatch):
    from html import unescape
    import re
    db = _seeded_database(tmp_path, monkeypatch)
    from ui.dialogs import model_guide_html
    text = " ".join(unescape(re.sub(r"<[^>]+>", " ", model_guide_html())).split())
    assert "claude-opus-5-5 — $4 in / $20 out" in text
    assert "deepseek-flash — $0.3 in / $1.2 out" in text
    for retired in ("claude-3-", "gemini-1.5", "deepseek-chat", "qwen3-max"):
        assert retired not in text, retired
