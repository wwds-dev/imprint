"""Press calendar captions and CSV, now Qt-free (spec one-click-release, A5 E2)."""

from __future__ import annotations

import csv
import json
from datetime import date

from agents.manuscript.calendar_export import (
    AI_COLUMN, CSV_HEADER, apply_captions, caption_items, write_calendar_csv)
from agents.manuscript.content_calendar import build_calendar


def _slots():
    return build_calendar(["Café at dawn.", "=cmd|' /C calc'!A0"], 1,
                          date(2026, 11, 20), ["TikTok", "Pinterest"])


def test_caption_items_match_the_old_panel_json():
    slots = _slots()
    old = json.dumps([{"quote": s.quote, "platform": s.platform.lower()}
                      for s in slots])
    assert caption_items(slots) == old
    assert "Café" in caption_items(slots, ensure_ascii=False)
    assert "Caf\\u00e9" in caption_items(slots)


def test_apply_captions_fills_in_order_and_reports_blanks():
    slots = _slots()
    blank = apply_captions(slots, json.dumps(["one", "two", ""]))
    assert [s.caption for s in slots[:3]] == ["one", "two", ""]
    assert blank == [2] + list(range(3, len(slots)))
    assert apply_captions(slots, "") == list(range(len(slots)))


def test_csv_header_rows_and_formula_cells_stay_text(tmp_path):
    slots = _slots()
    apply_captions(slots, json.dumps(["+1 caption"] * len(slots)))
    path = write_calendar_csv(slots, tmp_path / "c.csv")
    rows = list(csv.reader(path.open(encoding="utf-8")))
    assert rows[0] == CSV_HEADER
    assert len(rows) == len(slots) + 1
    formula = [r for r in rows[1:] if "calc" in r[3]]
    assert formula and all(r[3].startswith("'=") for r in formula)
    assert all(r[4] == "'+1 caption" for r in rows[1:])
    plain = [r for r in rows[1:] if "Café" in r[3]]
    assert plain[0][3] == "Café at dawn."
    assert rows[1][0] == slots[0].day.strftime("%Y-%m-%d")


def test_ai_column_is_optional_and_per_slot(tmp_path):
    slots = _slots()
    path = write_calendar_csv(slots, tmp_path / "c.csv",
                              ai_column=lambda s: f"caption: model for {s.platform}")
    rows = list(csv.reader(path.open(encoding="utf-8")))
    assert rows[0] == CSV_HEADER + [AI_COLUMN]
    assert rows[1][5].startswith("caption: model for ")
