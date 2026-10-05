"""Royalties render as a shared chart, fed from the KDP CSVs on disk."""

import os

import pytest

from agents.manuscript import kdp_csv_parser


CSV = """Marketplace,Units Sold,Royalty,KENP Read
Amazon.com,10,25.50,100
Amazon.de,4,9.10,0
Amazon.com,2,5.00,40
"""


def test_marketplace_summary_merges_every_report(tmp_path, monkeypatch):
    monkeypatch.setattr(kdp_csv_parser, "KDP_REPORTS_DIR", tmp_path)
    (tmp_path / "jan.csv").write_text(CSV, encoding="utf-8")
    (tmp_path / "feb.csv").write_text(CSV, encoding="utf-8")
    (tmp_path / "broken.csv").write_bytes(b"\xff\xfe not a csv")
    summary = kdp_csv_parser.marketplace_summary()
    by_market = {m["marketplace"]: m for m in summary["by_marketplace"]}
    assert by_market["Amazon.com"]["units"] == 24
    assert by_market["Amazon.com"]["royalties"] == pytest.approx(61.0)
    assert by_market["Amazon.de"]["royalties"] == pytest.approx(18.2)


def test_summary_is_empty_when_no_reports_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(kdp_csv_parser, "KDP_REPORTS_DIR",
                        tmp_path / "missing")
    assert kdp_csv_parser.marketplace_summary()["by_marketplace"] == []


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


def test_chart_shows_royalties_sorted_and_units_as_second_series(
        window, monkeypatch):
    panel = window.manuscript_panel
    monkeypatch.setattr(
        kdp_csv_parser, "marketplace_summary",
        lambda: {"by_marketplace": [
            {"marketplace": "Amazon.de", "units": 4, "royalties": 9.1},
            {"marketplace": "Amazon.com", "units": 12, "royalties": 30.5},
        ]})
    panel.refresh_royalty_chart()
    chart = panel.manuscript_royalty_chart
    assert chart.row_count == 2
    assert chart.value_at("Amazon.com") == pytest.approx(30.5)
    assert chart.value_at("Amazon.de", series=1) == 4
    # Sorted by royalties, biggest first.
    assert chart._labels[0] == "Amazon.com"


def test_chart_clears_honestly_without_data(window, monkeypatch):
    panel = window.manuscript_panel
    monkeypatch.setattr(kdp_csv_parser, "marketplace_summary",
                        lambda: {"by_marketplace": []})
    panel.refresh_royalty_chart()
    assert panel.manuscript_royalty_chart.row_count == 0


# ── integration sync/error states (P2, 2026-10-06) ──────────────────────────

def test_sync_states_persist_and_render(window, monkeypatch):
    panel = window.manuscript_panel
    panel._record_sync("publishdrive", True, "last 30 days fetched")
    panel._record_sync("kdp", False, "folder unreadable")
    text = panel.manuscript_sync_label.text()
    assert "PublishDrive: ok" in text
    assert "KDP reports: FAILED" in text and "folder unreadable" in text
    # Persisted: a fresh render from storage shows the same states.
    panel.manuscript_sync_label.setText("")
    panel.refresh_sync_states()
    assert "FAILED" in panel.manuscript_sync_label.text()


def test_failed_publishdrive_fetch_records_the_error(window, monkeypatch):
    panel = window.manuscript_panel
    from agents.manuscript import publishdrive_client

    class ExplodingClient:
        def get_last_30_days(self):
            raise RuntimeError("401 from PublishDrive")
    monkeypatch.setattr(publishdrive_client, "PublishDriveClient",
                        ExplodingClient)
    panel.refresh_data()
    assert "FAILED" in panel.manuscript_sync_label.text()
    assert "401" in panel.manuscript_sync_label.text()


def test_kdp_ingest_records_a_clean_sync(window, monkeypatch):
    panel = window.manuscript_panel
    from agents.manuscript import kdp_csv_parser as parser_module
    import agents.manuscript.panel as panel_module
    monkeypatch.setattr(parser_module, "ingest_new_reports", lambda: ["a.csv"])
    panel.ingest_kdp()
    text = panel.manuscript_sync_label.text()
    assert "KDP reports: ok" in text and "1 new report(s)" in text
