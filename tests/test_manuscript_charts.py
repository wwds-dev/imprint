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


# ── wave-two hardening: skipped files, currencies, strip elision, widget ─────

def test_unreadable_reports_are_listed_not_swallowed(tmp_path, monkeypatch):
    monkeypatch.setattr(kdp_csv_parser, "KDP_REPORTS_DIR", tmp_path)
    (tmp_path / "jan.csv").write_text(CSV, encoding="utf-8")
    (tmp_path / "broken.csv").write_bytes(b"\xff\xfe not a csv")
    summary = kdp_csv_parser.marketplace_summary()
    assert summary["skipped_files"] == ["broken.csv"]
    # The readable file still feeds the chart.
    assert summary["by_marketplace"]


def test_skipped_files_warn_in_the_status_line(window, monkeypatch):
    panel = window.manuscript_panel
    monkeypatch.setattr(
        kdp_csv_parser, "marketplace_summary",
        lambda: {"by_marketplace": [
            {"marketplace": "Amazon.com", "units": 1, "royalties": 2.0,
             "currencies": ["USD"]}],
            "skipped_files": ["broken.csv"]})
    panel.refresh_royalty_chart()
    status = panel.manuscript_status_label.text()
    assert "[Warning]" in status and "broken.csv" in status
    assert "missing from the chart" in status


def test_summary_carries_each_marketplaces_currencies(tmp_path, monkeypatch):
    monkeypatch.setattr(kdp_csv_parser, "KDP_REPORTS_DIR", tmp_path)
    (tmp_path / "mix.csv").write_text(
        "Marketplace,Units Sold,Royalty,Currency,KENP Read\n"
        "Amazon.com,10,25.50,USD,100\n"
        "Amazon.de,4,9.10,EUR,0\n"
        "Amazon.de,1,2.00,USD,0\n", encoding="utf-8")
    summary = kdp_csv_parser.marketplace_summary()
    by_market = {m["marketplace"]: m for m in summary["by_marketplace"]}
    assert by_market["Amazon.com"]["currencies"] == ["USD"]
    assert by_market["Amazon.de"]["currencies"] == ["EUR", "USD"]


def test_mixed_currencies_drop_the_dollar_sign_and_say_so(window, monkeypatch):
    panel = window.manuscript_panel
    chart = panel.manuscript_royalty_chart
    monkeypatch.setattr(
        kdp_csv_parser, "marketplace_summary",
        lambda: {"by_marketplace": [
            {"marketplace": "Amazon.com", "units": 10, "royalties": 25.5,
             "currencies": ["USD"]},
            {"marketplace": "Amazon.de", "units": 4, "royalties": 9.1,
             "currencies": ["EUR"]},
        ]})
    panel.refresh_royalty_chart()
    assert "$" not in chart._value_format, \
        "summed EUR+USD rows rendered with a dollar sign"
    assert "EUR" in chart.toolTip() and "not converted" in chart.toolTip()
    # Back to USD-only data: the format returns and the warning clears.
    monkeypatch.setattr(
        kdp_csv_parser, "marketplace_summary",
        lambda: {"by_marketplace": [
            {"marketplace": "Amazon.com", "units": 10, "royalties": 25.5,
             "currencies": ["USD"]}]})
    panel.refresh_royalty_chart()
    assert "$" in chart._value_format
    assert chart.toolTip() == ""


def test_long_sync_notes_elide_with_the_full_text_in_the_tooltip(window):
    panel = window.manuscript_panel
    note = "x" * 150
    panel._record_sync("kdp", False, note)
    label = panel.manuscript_sync_label
    assert note not in label.text()
    assert "…" in label.text()
    assert note in label.toolTip()


# ── BarChart widget contract ─────────────────────────────────────────────────

def test_set_data_rejects_misaligned_series(app):
    from ui.charts import BarChart
    chart = BarChart()
    with pytest.raises(ValueError):
        chart.set_data(["a", "b"], [1.0])
    with pytest.raises(ValueError):
        chart.set_data(["a"], [1.0], second=[1.0, 2.0])


def test_clear_resets_the_grown_height_floor(app):
    from ui.charts import BarChart, _ROW_HEIGHT
    chart = BarChart()
    chart.set_data([f"row {i}" for i in range(20)], [float(i) for i in range(20)],
                   second=[1.0] * 20)
    assert chart.minimumHeight() > _ROW_HEIGHT * 3
    chart.clear()
    assert chart.minimumHeight() == _ROW_HEIGHT * 3


def test_negative_values_keep_their_sign_and_still_paint(app):
    from ui.charts import BarChart
    chart = BarChart()
    chart.set_data(["refund month", "good month"], [-12.5, 30.0])
    assert chart.value_at("refund month") == pytest.approx(-12.5)
    chart.resize(400, 200)
    assert not chart.grab().isNull()      # paintEvent survives a negative


def test_unstated_currency_is_not_presumed_to_be_dollars(window, monkeypatch):
    # The canonical KDP CSV has no Currency column; "$" on those rows
    # would be a guess wearing a label.
    panel = window.manuscript_panel
    chart = panel.manuscript_royalty_chart
    monkeypatch.setattr(
        kdp_csv_parser, "marketplace_summary",
        lambda: {"by_marketplace": [
            {"marketplace": "Amazon.de", "units": 4, "royalties": 9.1,
             "currencies": ["unstated"]}]})
    panel.refresh_royalty_chart()
    assert "$" not in chart._value_format
    assert "do not state a currency" in chart.toolTip()


def test_parser_marks_currency_less_rows_as_unstated(tmp_path, monkeypatch):
    monkeypatch.setattr(kdp_csv_parser, "KDP_REPORTS_DIR", tmp_path)
    (tmp_path / "jan.csv").write_text(CSV, encoding="utf-8")   # no Currency col
    summary = kdp_csv_parser.marketplace_summary()
    assert summary["currencies"] == ["unstated"]
    for market in summary["by_marketplace"]:
        assert market["currencies"] == ["unstated"]


def test_uniform_non_usd_data_is_labelled_not_called_mixed(window, monkeypatch):
    panel = window.manuscript_panel
    chart = panel.manuscript_royalty_chart
    monkeypatch.setattr(
        kdp_csv_parser, "marketplace_summary",
        lambda: {"by_marketplace": [
            {"marketplace": "Amazon.de", "units": 4, "royalties": 9.1,
             "currencies": ["EUR"]}]})
    panel.refresh_royalty_chart()
    assert "$" not in chart._value_format
    assert chart.toolTip() == "Amounts in EUR."
    assert "Mixed" not in chart.toolTip()


def test_emptying_the_chart_clears_the_currency_caveat(window, monkeypatch):
    panel = window.manuscript_panel
    chart = panel.manuscript_royalty_chart
    monkeypatch.setattr(
        kdp_csv_parser, "marketplace_summary",
        lambda: {"by_marketplace": [
            {"marketplace": "Amazon.com", "units": 1, "royalties": 2.0,
             "currencies": ["USD"]},
            {"marketplace": "Amazon.de", "units": 1, "royalties": 2.0,
             "currencies": ["EUR"]}]})
    panel.refresh_royalty_chart()
    assert "Mixed currencies" in chart.toolTip()
    monkeypatch.setattr(kdp_csv_parser, "marketplace_summary",
                        lambda: {"by_marketplace": []})
    panel.refresh_royalty_chart()
    assert chart.toolTip() == "", \
        "an emptied chart kept a money caveat about vanished data"


def test_malformed_money_rows_are_counted_not_swallowed(tmp_path, monkeypatch):
    monkeypatch.setattr(kdp_csv_parser, "KDP_REPORTS_DIR", tmp_path)
    (tmp_path / "locale.csv").write_text(
        "Marketplace,Units Sold,Royalty,KENP Read\n"
        "Amazon.com,10,25.50,100\n"
        "Amazon.de,4,\"9,10\",0\n", encoding="utf-8")   # locale decimal comma
    summary = kdp_csv_parser.marketplace_summary()
    assert summary["skipped_rows"] == 1
    assert summary["total_royalties_usd"] == pytest.approx(25.5)


def test_dropped_rows_warn_in_the_status_line(window, monkeypatch):
    panel = window.manuscript_panel
    monkeypatch.setattr(
        kdp_csv_parser, "marketplace_summary",
        lambda: {"by_marketplace": [
            {"marketplace": "Amazon.com", "units": 1, "royalties": 2.0,
             "currencies": ["USD"]}],
            "skipped_rows": 3})
    panel.refresh_royalty_chart()
    status = panel.manuscript_status_label.text()
    assert "[Warning]" in status and "3 row(s)" in status
    assert "dropped" in status
