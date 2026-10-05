"""Structured release plans for the Music workspace.

A generated plan used to exist only as prose in a tab (and optionally a
.txt the user saved somewhere). These rows make the plan a record: the
inputs that produced it, the parsed sections, the owning Project — and,
once the release is out in the world, the measured outcome, which the
next plan's prompt feeds on so planning learns from reality instead of
starting from zero every time. Qt-free on purpose.
"""

import json
from datetime import datetime

from services.database import get_connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def save_plan(*, artist: str, genre: str, release_type: str,
              distributor: str, audience: str, description: str,
              plan_text: str, sections: dict, project=None) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO music_release_plans
                 (project, artist, genre, release_type, distributor,
                  audience, description, plan_text, sections_json,
                  created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (project, artist, genre, release_type, distributor, audience,
             description, plan_text, json.dumps(sections or {}), _now()))
        return int(cursor.lastrowid)


def get_plan(plan_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM music_release_plans WHERE id = ?",
            (plan_id,)).fetchone()
    return dict(row) if row else None


def list_plans(*, artist: str = "", project=None, limit: int = 20) -> list[dict]:
    """Newest first; filters are optional and combine."""
    clauses, params = [], []
    if artist:
        clauses.append("LOWER(artist) = LOWER(?)")
        params.append(artist)
    if project:
        clauses.append("project = ?")
        params.append(project)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(int(limit))
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT * FROM music_release_plans {where}
                 ORDER BY id DESC LIMIT ?""", params).fetchall()
    return [dict(row) for row in rows]


def record_outcome(plan_id: int, *, streams=None, revenue_usd=None,
                   notes: str = "") -> None:
    """What actually happened — user-entered, since no platform API is
    wired; the panel labels it as self-reported."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE music_release_plans
                  SET outcome_streams = ?, outcome_revenue_usd = ?,
                      outcome_notes = ?, outcome_recorded_at = ?
                WHERE id = ?""",
            (int(streams) if streams is not None else None,
             float(revenue_usd) if revenue_usd is not None else None,
             notes or "", _now(), plan_id))


def outcomes_context(artist: str, *, limit: int = 3) -> str:
    """A compact past-performance block for the next plan's prompt.

    Only plans WITH a recorded outcome qualify — an unreleased plan says
    nothing about reality. Empty string when there is nothing to learn
    from, so the prompt stays untouched for a first release.
    """
    if not artist:
        return ""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM music_release_plans
                WHERE LOWER(artist) = LOWER(?)
                  AND outcome_recorded_at != ''
                ORDER BY id DESC LIMIT ?""",
            (artist, int(limit))).fetchall()
    if not rows:
        return ""
    lines = ["Past releases and measured outcomes (self-reported; plan "
             "against these):"]
    for row in rows:
        date = (row["created_at"] or "")[:10]
        bits = [f"- {date} {row['release_type']} ({row['genre']})"]
        facts = []
        if row["outcome_streams"] is not None:
            facts.append(f"{row['outcome_streams']:,} streams")
        if row["outcome_revenue_usd"] is not None:
            facts.append(f"${row['outcome_revenue_usd']:,.2f} revenue")
        if facts:
            bits.append(": " + ", ".join(facts))
        if row["outcome_notes"]:
            bits.append(f" — {row['outcome_notes']}")
        lines.append("".join(bits))
    return "\n".join(lines)
