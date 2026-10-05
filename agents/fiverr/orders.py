"""One durable record per client order for the Client Gigs workspace.

The order log was an in-memory table that vanished with the window, and a
returning client's brief, revisions, deliveries and gig listing lived in
whichever tab still happened to hold them. One row per open order now
carries all of it — the brief, the brand kit, every event (a revision is
an event on the same order, not a new order), the generated image paths,
the delivery text and the gig listing. Qt-free on purpose.
"""

import json
from datetime import datetime

from services.database import get_connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def open_order(brief: dict) -> dict:
    """Reuse the client's open order (a returning client is a revision on
    the same record) or create one. The brief and brand kit refresh on
    every reuse — the newest instructions win, the history keeps the past.
    """
    client = (brief.get("business_name") or "").strip()
    now = _now()
    with get_connection() as conn:
        row = None
        if client:
            row = conn.execute(
                """SELECT * FROM fiverr_orders
                    WHERE LOWER(client) = LOWER(?) AND status = 'open'
                    ORDER BY id DESC LIMIT 1""", (client,)).fetchone()
        if row is not None:
            conn.execute(
                """UPDATE fiverr_orders
                      SET industry = ?, style = ?, colors = ?, notes = ?,
                          brand_fonts = ?, brand_voice = ?, brand_rules = ?,
                          updated_at = ?
                    WHERE id = ?""",
                (brief.get("industry", ""), brief.get("style", ""),
                 brief.get("colors", ""), brief.get("notes", ""),
                 brief.get("brand_fonts", ""), brief.get("brand_voice", ""),
                 brief.get("brand_rules", ""), now, row["id"]))
            fresh = conn.execute(
                "SELECT * FROM fiverr_orders WHERE id = ?",
                (row["id"],)).fetchone()
            return dict(fresh)
        cursor = conn.execute(
            """INSERT INTO fiverr_orders
                 (client, industry, style, colors, notes, brand_fonts,
                  brand_voice, brand_rules, status, history_json,
                  image_paths_json, delivery_text, gig_text,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', '[]', '[]', '', '',
                       ?, ?)""",
            (client, brief.get("industry", ""), brief.get("style", ""),
             brief.get("colors", ""), brief.get("notes", ""),
             brief.get("brand_fonts", ""), brief.get("brand_voice", ""),
             brief.get("brand_rules", ""), now, now))
        fresh = conn.execute("SELECT * FROM fiverr_orders WHERE id = ?",
                             (cursor.lastrowid,)).fetchone()
        return dict(fresh)


def record_event(order_id: int, kind: str, detail: str = "") -> None:
    """Append to the order's history — requests, revisions, deliveries."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT history_json FROM fiverr_orders WHERE id = ?",
            (order_id,)).fetchone()
        if row is None:
            return
        history = json.loads(row["history_json"] or "[]")
        history.append({"at": _now(), "kind": kind, "detail": detail})
        conn.execute(
            "UPDATE fiverr_orders SET history_json = ?, updated_at = ? "
            "WHERE id = ?", (json.dumps(history), _now(), order_id))


def attach(order_id: int, **fields) -> None:
    """Store a produced artifact on the order (images, delivery, gig)."""
    allowed = {"image_paths_json", "delivery_text", "gig_text", "status"}
    sets, params = [], []
    for column, value in fields.items():
        if column not in allowed:
            raise ValueError(f"not an order artifact column: {column}")
        sets.append(f"{column} = ?")
        params.append(value)
    if not sets:
        return
    sets.append("updated_at = ?")
    params += [_now(), order_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE fiverr_orders SET {', '.join(sets)} WHERE id = ?",
            params)


def get_order(order_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM fiverr_orders WHERE id = ?",
                           (order_id,)).fetchone()
    return dict(row) if row else None


def list_orders(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM fiverr_orders ORDER BY updated_at DESC, id DESC "
            "LIMIT ?", (int(limit),)).fetchall()
    return [dict(row) for row in rows]


def latest_for_client(client: str):
    """The client's most recent order, open or not — the reusable
    preferences a returning client's empty fields fill from."""
    if not (client or "").strip():
        return None
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM fiverr_orders
                WHERE LOWER(client) = LOWER(?)
                ORDER BY id DESC LIMIT 1""", (client.strip(),)).fetchone()
    return dict(row) if row else None
