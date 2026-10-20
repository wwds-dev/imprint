"""gpt-4o-mini-tts is removed by OpenAI on 2027-01-06 (docs/local_model_routing_plan.html, Phase 0)."""
import re
from pathlib import Path

from agents.audiobook import panel
from services.narrator import converter

ROOT = Path(__file__).resolve().parents[1]


def test_panel_and_converter_agree_on_the_retirement_date():
    assert panel.NARRATION_ROUTES["openai"]["retires"] == converter.TTS_PROVIDERS["openai"]["retires"]


def test_a_retired_route_leaves_the_menu_but_stays_nameable():
    assert "openai" in panel.offered_routes("2027-01-05")
    assert "openai" not in panel.offered_routes("2027-01-06")
    assert "openai" in panel.NARRATION_ROUTES          # a paused OpenAI book can still be priced/resumed


def test_default_route_is_the_first_one_on_offer():
    assert panel.default_route("2026-10-19") == "openai"
    assert panel.default_route("2027-01-06") == "gemini"
    assert panel.default_route("2027-01-06") == converter.default_tts_provider("2027-01-06")


def test_new_jobs_without_a_route_get_the_current_default_not_a_hardcoded_model(monkeypatch):
    from agents.audiobook import conversions
    from services.database import get_connection
    monkeypatch.setattr(converter, "default_tts_provider", lambda today=None: "gemini")
    try:
        row = conversions.open_job(source_path="/b/x.epub", output_path="/o/x.mp3", voice="Kore",
                                   chunk_tokens=1200, estimate_eur=1.0)
        assert (row["provider"], row["model"]) == ("gemini", "gemini-3.8-flash-tts")
    finally:
        with get_connection() as conn:
            conn.execute("DELETE FROM audiobook_conversions")


def test_panel_has_no_hardcoded_model_fallback_for_new_work():
    src = (ROOT / "agents" / "audiobook" / "panel.py").read_text()
    # Legacy rows (written before routes existed) are OpenAI's by definition and keep that reading;
    # the command line for a new run must not.
    assert 'config.get("model", "gpt-4o-mini-tts")' not in src
    assert 'config.get("provider", "openai")' not in src


def test_legacy_column_defaults_still_describe_pre_route_rows():
    """Rows from before routes existed were OpenAI's; the schema default records that."""
    sql = (ROOT / "services" / "database.py").read_text()
    assert re.search(r"model\s+TEXT NOT NULL DEFAULT 'gpt-4o-mini-tts'", sql)
