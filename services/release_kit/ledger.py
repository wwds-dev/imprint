"""Durable record of every release kit (spec A4). Qt-free; GUI thread only.

Pattern of agents/video/jobs.py: a row per job, a row per stage and a row per
item. An item that may call a provider is written `intent` in its own
committed transaction before the call, so a crash leaves evidence that
`recover()` resolves at the next launch.

States
- job:   running → paused | made | made_check; paused → running | discarded
- stage: waiting → running → done | incomplete | verify | paused;
         paused → waiting (resume); done → done_verified (resume check)
- item:  planned → intent → done | failed | verify | partial
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from services.database import get_connection
from services.release_kit.plan import STAGES, KitPlan, is_local_route

JOB_TRANSITIONS = {
    "running": {"paused", "made", "made_check"},
    "paused": {"running", "discarded"},
    "made": set(),
    "made_check": set(),
    "discarded": set(),
}
UNFINISHED = ("running", "paused")
STAGE_FINISHED = {"done", "done_verified", "incomplete", "verify", "not_included"}

PAUSE_REASONS = {
    "retired", "route_unavailable", "price_rose", "over_line", "advisor_hold",
    "cap_refused", "verify", "booth_settings_changed", "user_stop", "quit",
    "interrupted", "paid_output_changed", "no_quotes", "item_failed",
}


class KitBusy(RuntimeError):
    """Another release kit is already running (one at a time)."""


class TransitionError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def file_sha256(path: Path | str) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ── jobs ─────────────────────────────────────────────────────────────────────

def create_job(plan: KitPlan, *, plan_json: dict, start_label: str,
               total_eur: float = 0.0) -> str:
    """Write the approval and start the job as `running`.

    Raises KitBusy when another kit is running (partial unique index).
    """
    job_id = uuid.uuid4().hex
    now = _now()
    today = now[:10]
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO release_jobs (id, project_id, version, "
                "source_sha256, title, byline, words, characters, "
                "project_instructions, output_dir, status, approved_total_eur, "
                "budget_day, approval_seq, created_at, started_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,'running',?,?,1,?,?,?)",
                (job_id, plan.project_id, plan.version, plan.source_sha256,
                 plan.title, plan.byline, plan.words, plan.characters,
                 plan.project_instructions, plan.output_dir, total_eur, today,
                 now, now, now))
            conn.execute(
                "INSERT INTO release_job_approvals (job_id, seq, approved_at, "
                "budget_day, total_eur, plan_json, start_label) "
                "VALUES (?, 1, ?, ?, ?, ?, ?)",
                (job_id, now, today, total_eur,
                 json.dumps(plan_json, sort_keys=True), start_label))
            for stage in STAGES:
                route = plan.route_for(stage.key)
                kind = ("not_included" if stage.key == "audiobook"
                        else "local" if (not route.provider
                                         or route.provider == "local"
                                         or is_local_route(route.provider))
                        else "paid")
                conn.execute(
                    "INSERT INTO release_job_stages (job_id, stage, ordinal, "
                    "agent, provider, model, voice, route_kind, status) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (job_id, stage.key, stage.ordinal, stage.agent,
                     route.provider, route.model, route.voice, kind,
                     "not_included" if kind == "not_included" else "waiting"))
    except sqlite3.IntegrityError as exc:
        if "release_jobs.status" in str(exc) or "ux_release_jobs" in str(exc):
            raise KitBusy("A release kit is already running.") from exc
        raise
    return job_id


def get_job(job_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM release_jobs WHERE id = ?",
                           (job_id,)).fetchone()
    return dict(row) if row else None


def running_job() -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM release_jobs WHERE status = 'running'").fetchone()
    return dict(row) if row else None


def list_jobs(project_id: str | None = None, *, unfinished: bool = False) -> list[dict]:
    query = "SELECT * FROM release_jobs WHERE 1=1"
    params: list = []
    if project_id is not None:
        query += " AND project_id = ?"
        params.append(project_id)
    if unfinished:
        query += " AND status IN ('running', 'paused')"
    query += " ORDER BY created_at DESC, rowid DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(query, params)]


def latest_for_project(project_id: str) -> dict | None:
    jobs = list_jobs(project_id)
    for job in jobs:
        if job["status"] in UNFINISHED:
            return job
    return jobs[0] if jobs else None


def approval(job_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM release_job_approvals WHERE job_id = ? "
            "ORDER BY seq DESC LIMIT 1", (job_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["plan"] = json.loads(data["plan_json"] or "{}")
    return data


def set_job_status(job_id: str, status: str, *, reason: str = "",
                   detail: str = "") -> None:
    """Move a job along JOB_TRANSITIONS. Paused needs a reason code."""
    job = get_job(job_id)
    if job is None:
        raise TransitionError(f"no release kit {job_id}")
    if status not in JOB_TRANSITIONS[job["status"]]:
        raise TransitionError(f"{job['status']} → {status} is not allowed")
    if status == "paused" and reason not in PAUSE_REASONS:
        raise TransitionError(f"unknown pause reason {reason!r}")
    now = _now()
    ended = now if status in ("made", "made_check", "discarded") else ""
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE release_jobs SET status = ?, pause_reason = ?, "
                "pause_detail = ?, ended_at = CASE WHEN ? != '' THEN ? "
                "ELSE ended_at END, updated_at = ? WHERE id = ?",
                (status, reason if status == "paused" else "",
                 detail if status == "paused" else "", ended, ended, now,
                 job_id))
    except sqlite3.IntegrityError as exc:
        raise KitBusy("A release kit is already running.") from exc


# ── stages ───────────────────────────────────────────────────────────────────

def stages(job_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM release_job_stages WHERE job_id = ? ORDER BY ordinal",
            (job_id,)).fetchall()
    out = []
    for row in rows:
        data = dict(row)
        data["result"] = json.loads(data["result_json"] or "{}")
        out.append(data)
    return out


def stage(job_id: str, key: str) -> dict:
    for row in stages(job_id):
        if row["stage"] == key:
            return row
    raise KeyError(key)


def set_stage(job_id: str, key: str, **fields) -> None:
    if "result" in fields:
        fields["result_json"] = json.dumps(fields.pop("result"), sort_keys=True)
    if fields.get("status") == "running":
        fields.setdefault("started_at", _now())
    if fields.get("status") in STAGE_FINISHED:
        fields.setdefault("ended_at", _now())
    columns = ", ".join(f"{name} = ?" for name in fields)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE release_job_stages SET {columns} "
            "WHERE job_id = ? AND stage = ?",
            (*fields.values(), job_id, key))


# ── items ────────────────────────────────────────────────────────────────────

def items(job_id: str, stage_key: str | None = None) -> list[dict]:
    query = "SELECT * FROM release_job_items WHERE job_id = ?"
    params: list = [job_id]
    if stage_key:
        query += " AND stage = ?"
        params.append(stage_key)
    query += " ORDER BY id"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    out = []
    for row in rows:
        data = dict(row)
        data["ai"] = json.loads(data["ai_json"] or "{}")
        out.append(data)
    return out


def item(job_id: str, stage_key: str, item_key: str) -> dict | None:
    for row in items(job_id, stage_key):
        if row["item_key"] == item_key:
            return row
    return None


def ensure_item(job_id: str, stage_key: str, item_key: str) -> dict:
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO release_job_items (job_id, stage, item_key, "
            "state, created_at, updated_at) VALUES (?,?,?,'planned',?,?)",
            (job_id, stage_key, item_key, now, now))
    return item(job_id, stage_key, item_key)


def next_request_key(job_id: str, stage_key: str, base: str) -> str:
    """`<base>#<n>`: a new attempt never reuses an earlier item's key, so the
    one-usage-row-per-item index still holds after a failed attempt."""
    attempts = [r for r in items(job_id, stage_key)
                if r["item_key"].startswith(base + "#")]
    return f"{base}#{len(attempts) + 1}"


def mark_item(job_id: str, stage_key: str, item_key: str, state: str,
              **fields) -> None:
    if "ai" in fields:
        fields["ai_json"] = json.dumps(fields.pop("ai"), sort_keys=True)
    fields["state"] = state
    fields["updated_at"] = _now()
    columns = ", ".join(f"{name} = ?" for name in fields)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE release_job_items SET {columns} "
            "WHERE job_id = ? AND stage = ? AND item_key = ?",
            (*fields.values(), job_id, stage_key, item_key))


def done_outputs(job_id: str) -> list[dict]:
    return [r for r in items(job_id) if r["state"] == "done" and r["output_path"]]


# ── recovery and resume ──────────────────────────────────────────────────────

def recover(*, active: str | None = None) -> list[str]:
    """Launch-time recovery (A4), run before Booth's own scan.

    `active` is the kit this process is running, if any: it is not a
    leftover and is never touched.

    1. A `running` job belongs to a process that is gone → paused/interrupted.
    2. Intent items: a local request item is marked failed (its usage row, if
       any, stays; the retry takes the next `#n` key); a local file item goes
       back to planned — it costs nothing to redo. Paid cases (a), (b) and
       the audiobook (d) arrive with slice 2.
    Returns the ids of unfinished kits, for the Release Kits window.
    """
    now = _now()
    with get_connection() as conn:
        for row in conn.execute(
                "SELECT id FROM release_jobs WHERE status = 'running' "
                "AND id != ?", (active or "",)).fetchall():
            conn.execute(
                "UPDATE release_jobs SET status = 'paused', pause_reason = "
                "'interrupted', pause_detail = '', updated_at = ? WHERE id = ?",
                (now, row["id"]))
            conn.execute(
                "UPDATE release_job_stages SET status = 'paused' "
                "WHERE job_id = ? AND status = 'running'", (row["id"],))
        intents = conn.execute(
            "SELECT i.*, s.route_kind FROM release_job_items i "
            "JOIN release_job_stages s ON s.job_id = i.job_id "
            "AND s.stage = i.stage WHERE i.state = 'intent' "
            "AND i.job_id != ?", (active or "",)).fetchall()
        for row in intents:
            if row["route_kind"] != "local":
                continue        # slice 2: paid intent cases (a), (b), (d)
            state = "failed" if "#" in row["item_key"] else "planned"
            conn.execute(
                "UPDATE release_job_items SET state = ?, updated_at = ? "
                "WHERE id = ?", (state, now, row["id"]))
    return [job["id"] for job in list_jobs(unfinished=True)]


def verify_finished(job_id: str) -> dict[str, list[str]]:
    """Resume check (A4): every done item's file must be present with its
    SHA-256. A changed local item re-opens its stage. Returns
    {stage: [item keys re-opened]}; stages whose files all match become
    done_verified."""
    reopened: dict[str, list[str]] = {}
    for row in items(job_id):
        if row["state"] != "done" or not row["output_path"]:
            continue
        path = Path(row["output_path"])
        try:
            ok = path.is_file() and file_sha256(path) == row["output_sha256"]
        except OSError:
            ok = False
        if not ok:
            mark_item(job_id, row["stage"], row["item_key"], "planned",
                      output_sha256="")
            reopened.setdefault(row["stage"], []).append(row["item_key"])
    for st in stages(job_id):
        if st["stage"] in reopened:
            set_stage(job_id, st["stage"], status="waiting", ended_at="")
        elif st["status"] == "done":
            set_stage(job_id, st["stage"], status="done_verified")
    if reopened:
        # Later stages consume the re-made files' paths; the link stage
        # always re-checks every link, so it runs again too.
        set_stage(job_id, "link", status="waiting", ended_at="")
    return reopened


def resume(job_id: str) -> dict[str, list[str]]:
    """Paused → running after the file check. Raises KitBusy when another kit
    is running."""
    job = get_job(job_id)
    if job is None or job["status"] != "paused":
        raise TransitionError("Only a paused kit can resume.")
    running = running_job()
    if running and running["id"] != job_id:
        raise KitBusy("A release kit is already running.")
    reopened = verify_finished(job_id)
    for st in stages(job_id):
        if st["status"] in ("paused", "running"):
            set_stage(job_id, st["stage"], status="waiting", ended_at="")
    set_job_status(job_id, "running")
    return reopened
