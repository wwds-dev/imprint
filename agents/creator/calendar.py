"""Week-calendar logic for the Brand Creator's content plan.

Qt-free on purpose: parsing, week arithmetic and the two export formats
are plain functions a test can call without a window.

`scheduled_for` stays TEXT in creator_content. The panel's pickers write
ISO (`YYYY-MM-DDTHH:MM`); everything older was free text typed into an
input box, so `parse_scheduled` is tolerant and anything it cannot read
is surfaced in the Undated lane rather than guessed at or lost.
"""

import csv
from datetime import date, datetime, timedelta, timezone

# Hard-coded English names: strftime %a/%b follow the process locale,
# which Qt resets to the system's — the calendar header should not
# change language with the OS, and neither should the tests.
_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# The formats the app has ever written, most specific first. `has_time`
# distinguishes a real time from a date-only entry so the week grid and
# the ICS export can treat "sometime that day" honestly.
_FORMATS = (
    ("%Y-%m-%dT%H:%M:%S.%f", True),
    ("%Y-%m-%dT%H:%M:%S", True),
    ("%Y-%m-%dT%H:%M", True),
    ("%Y-%m-%d %H:%M:%S", True),
    ("%Y-%m-%d %H:%M", True),
    ("%Y-%m-%d", False),
)


def parse_scheduled(text) -> tuple[datetime, bool] | None:
    """(when, has_time) for anything ISO-shaped; None for legacy prose."""
    raw = (text or "").strip()
    if not raw:
        return None
    for fmt, has_time in _FORMATS:
        try:
            return datetime.strptime(raw, fmt), has_time
        except ValueError:
            continue
    return None


def week_start(anchor: date) -> date:
    """The Monday of `anchor`'s week."""
    return anchor - timedelta(days=anchor.weekday())


def week_label(start: date) -> str:
    end = start + timedelta(days=6)
    if start.month == end.month:
        return f"{start.day}–{end.day} {_MONTHS[end.month - 1]} {end.year}"
    if start.year == end.year:
        return (f"{start.day} {_MONTHS[start.month - 1]} – "
                f"{end.day} {_MONTHS[end.month - 1]} {end.year}")
    return (f"{start.day} {_MONTHS[start.month - 1]} {start.year} – "
            f"{end.day} {_MONTHS[end.month - 1]} {end.year}")


def day_headers(start: date) -> list[str]:
    headers = []
    for i in range(7):
        day = start + timedelta(days=i)
        headers.append(
            f"{_DAYS[day.weekday()]} {day.day:02d} {_MONTHS[day.month - 1]}")
    return headers


def _ics_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """RFC 5545 folding: lines over 75 octets continue with a space."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        piece = char.encode("utf-8")
        if len(current) + len(piece) > 74:
            parts.append(current.decode("utf-8"))
            current = piece
        else:
            current += piece
    if current:
        parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def export_ics(rows: list[dict], path) -> tuple[int, int]:
    """Write dated rows as floating local VEVENTs; returns (written, skipped).

    Undated rows cannot become events without inventing a date, so they
    are skipped and counted — the caller says so instead of hiding it.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Imprint//Brand Creator Calendar//EN",
        "CALSCALE:GREGORIAN",
    ]
    written = skipped = 0
    for row in rows:
        parsed = parse_scheduled(row.get("scheduled_for"))
        if parsed is None:
            skipped += 1
            continue
        when, has_time = parsed
        written += 1
        summary = " · ".join(
            part for part in (row.get("kind", ""), row.get("title", ""))
            if part) or "Planned content"
        description_bits = []
        if row.get("channel"):
            description_bits.append(f"Channel: {row['channel']}")
        if row.get("campaign"):
            description_bits.append(f"Campaign: {row['campaign']}")
        if row.get("price_usd"):
            description_bits.append(f"Price: ${float(row['price_usd']):.2f}")
        if row.get("status"):
            description_bits.append(f"Status: {row['status']}")
        if row.get("body"):
            description_bits.append(row["body"])
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:creator-content-{row['id']}@imprint")
        lines.append(f"DTSTAMP:{stamp}")
        if has_time:
            lines.append(f"DTSTART:{when.strftime('%Y%m%dT%H%M%S')}")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{when.strftime('%Y%m%d')}")
        lines.append(f"SUMMARY:{_ics_escape(summary)}")
        if description_bits:
            lines.append(
                f"DESCRIPTION:{_ics_escape(chr(10).join(description_bits))}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("\r\n".join(_fold(line) for line in lines) + "\r\n")
    return written, skipped


def _defuse(value) -> str:
    """A leading apostrophe stops spreadsheets executing cell content."""
    text = str(value or "")
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def export_csv(rows: list[dict], path) -> int:
    """Write every row — dated or not — with the raw text preserved
    (formula-triggering first characters are defused with an apostrophe)."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scheduled_for", "kind", "title", "status",
                         "price_usd", "channel", "campaign", "body"])
        for row in rows:
            writer.writerow([
                _defuse(row.get("scheduled_for", "")),
                _defuse(row.get("kind", "")),
                _defuse(row.get("title", "")),
                _defuse(row.get("status", "")),
                row.get("price_usd", 0.0),
                _defuse(row.get("channel", "")),
                _defuse(row.get("campaign", "")),
                _defuse(row.get("body", "")),
            ])
    return len(rows)
