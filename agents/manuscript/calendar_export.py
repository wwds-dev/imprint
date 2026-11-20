"""Qt-free calendar captions and CSV for Press and the release kit (A5 E2).

Press's calendar used to build the caption request, fill the captions and write
the CSV inside panel methods. Both Press and the release kit now call these.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable, Sequence

from agents.manuscript.llm_parsing import parse_string_list

CSV_HEADER = ["Date", "Platform", "Format", "Quote", "Caption"]
AI_COLUMN = "AI used"

# A spreadsheet treats a cell starting with one of these as a formula. Quotes
# and captions come from a manuscript and a model, so a cell such as
# "=HYPERLINK(...)" must stay text when the CSV is opened (CSV injection).
_FORMULA_START = ("=", "+", "-", "@")


def _safe_cell(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA_START) else text


def caption_items(slots: Sequence, ensure_ascii: bool = True) -> str:
    """The caption request's JSON: one {quote, platform} per slot, in order."""
    items = [{"quote": s.quote, "platform": s.platform.lower()} for s in slots]
    return json.dumps(items, ensure_ascii=ensure_ascii)


def apply_captions(slots: Sequence, reply: str) -> list[int]:
    """Fill each slot's caption from the reply; return the blank slots' indices.

    A reply cut at the output limit parses to fewer captions than slots; the
    later slots stay blank and are reported, never invented.
    """
    captions = parse_string_list(reply or "")
    blank = []
    for i, slot in enumerate(slots):
        slot.caption = captions[i] if i < len(captions) else ""
        if not slot.caption.strip():
            blank.append(i)
    return blank


def write_calendar_csv(slots: Sequence, path: Path | str,
                       ai_column: Callable[[object], str] | None = None) -> Path:
    """Write the calendar CSV. With `ai_column`, add a factual "AI used" cell
    per slot (legal L5); the app never labels or posts anything itself."""
    path = Path(path)
    header = CSV_HEADER + ([AI_COLUMN] if ai_column else [])
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for slot in slots:
            row = [slot.day.strftime("%Y-%m-%d"), slot.platform, slot.format,
                   slot.quote, slot.caption]
            if ai_column:
                row.append(ai_column(slot))
            writer.writerow([_safe_cell(cell) for cell in row])
    return path
