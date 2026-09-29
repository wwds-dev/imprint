"""Durable record of audiobook conversions for the Audiobook Producer.

The narrator converter already resumes chunk-by-chunk from its on-disk
manifest; this row is the app-level memory of it: which book was in
flight when the process died, how far it got, and how much of the
estimate has been billed — so a restart surfaces the interruption
instead of forgetting it, and the money stays truthful across as many
runs as a book takes. Qt-free on purpose.

Billing model: `estimate_eur` is the whole-book flat estimate captured
at first start; `billed_eur` accumulates what has actually been logged.
Each run authorizes only the remaining fraction, an interrupted run
bills the fraction it generated, and a completed run bills the rest —
so the sum over any number of interruptions converges on one estimate,
never more.
"""

from datetime import datetime

from services.database import get_connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def find_open(source_path: str, output_path: str):
    """The unfinished job for this book, if a previous run left one."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM audiobook_conversions
                WHERE source_path = ? AND output_path = ?
                  AND status != 'completed'
                ORDER BY id DESC LIMIT 1""",
            (source_path, output_path)).fetchone()
    return dict(row) if row else None


def remaining_fraction(row) -> float:
    """How much of the book is still unpaid-for, from the last run's count."""
    if not row or not row.get("chunks_total"):
        return 1.0
    done = min(row.get("chunks_done", 0), row["chunks_total"])
    return max(0.0, 1.0 - done / row["chunks_total"])


def open_job(*, source_path: str, output_path: str, voice: str,
             chunk_tokens: int, estimate_eur: float, project=None,
             reset_progress: bool = False) -> dict:
    """Reuse the book's unfinished row (keeping billed_eur) or create one.

    run_baseline records where this run starts, so its own spend can be
    measured as (chunks_done - run_baseline) even after a crash.
    reset_progress=True is the fresh-start path (settings changed, cache
    invalid): the chunk counts restart at zero — billed_eur is history
    and always survives.
    """
    now = _now()
    existing = find_open(source_path, output_path)
    with get_connection() as conn:
        if existing:
            if reset_progress:
                conn.execute(
                    """UPDATE audiobook_conversions
                          SET voice = ?, chunk_tokens = ?, estimate_eur = ?,
                              project = ?, status = 'running', error = '',
                              chunks_done = 0, chunks_total = 0,
                              run_baseline = 0, updated_at = ?
                        WHERE id = ?""",
                    (voice, int(chunk_tokens), float(estimate_eur), project,
                     now, existing["id"]))
            else:
                conn.execute(
                    """UPDATE audiobook_conversions
                          SET voice = ?, chunk_tokens = ?, estimate_eur = ?,
                              project = ?, status = 'running', error = '',
                              run_baseline = chunks_done, updated_at = ?
                        WHERE id = ?""",
                    (voice, int(chunk_tokens), float(estimate_eur), project,
                     now, existing["id"]))
            row = conn.execute(
                "SELECT * FROM audiobook_conversions WHERE id = ?",
                (existing["id"],)).fetchone()
            return dict(row)
        cursor = conn.execute(
            """INSERT INTO audiobook_conversions
                 (source_path, output_path, voice, chunk_tokens,
                  estimate_eur, billed_eur, chunks_done, chunks_total,
                  run_baseline, project, status, error,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0.0, 0, 0, 0, ?, 'running', '', ?, ?)""",
            (source_path, output_path, voice, int(chunk_tokens),
             float(estimate_eur), project, now, now))
        row = conn.execute(
            "SELECT * FROM audiobook_conversions WHERE id = ?",
            (cursor.lastrowid,)).fetchone()
        return dict(row)


def update_progress(job_id: int, done: int, total: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE audiobook_conversions
                  SET chunks_done = ?, chunks_total = ?, updated_at = ?
                WHERE id = ?""",
            (int(done), int(total), _now(), job_id))


def run_spend_eur(row) -> float:
    """What THIS run generated, priced from the whole-book estimate.

    Chunks cached by earlier runs were paid then; only the delta above
    run_baseline is new spend.
    """
    total = row.get("chunks_total") or 0
    if not total:
        return 0.0
    new_chunks = max(0, min(row.get("chunks_done", 0), total)
                     - row.get("run_baseline", 0))
    return round(float(row.get("estimate_eur", 0.0)) * new_chunks / total, 6)


def settle(job_id: int, *, status: str, billed_add: float = 0.0,
           error: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE audiobook_conversions
                  SET status = ?, billed_eur = billed_eur + ?,
                      error = CASE WHEN ? = '' THEN error ELSE ? END,
                      updated_at = ?
                WHERE id = ?""",
            (status, float(billed_add), error, error, _now(), job_id))


def get_job(job_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM audiobook_conversions WHERE id = ?",
            (job_id,)).fetchone()
    return dict(row) if row else None


def dead_runs() -> list[dict]:
    """Rows still 'running' at startup: the app died mid-conversion."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM audiobook_conversions
                WHERE status = 'running' ORDER BY id""").fetchall()
    return [dict(row) for row in rows]
