"""`release-kit-report.md`, built from the ledger alone (spec D6, legal N4).

Rewritten at every pause and at the end. Never claims income, reach or
results; the last line says nothing was posted.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from services import money_text
from services.release_kit import ledger
from services.release_kit.plan import NOTICES, STAGE_BY_KEY

REPORT_NAME = "release-kit-report.md"

STATE_WORDS = {
    "running": "Running", "paused": "Paused", "made": "Made",
    "made_check": "Made, with items to check", "discarded": "Discarded",
}
STAGE_WORDS = {
    "waiting": "Waiting", "running": "Running", "done": "Done",
    "done_verified": "Done earlier", "paused": "Paused",
    "incomplete": "Incomplete", "verify": "Verify",
    "not_included": "Not included",
}


def _when(stamp: str) -> str:
    if not stamp:
        return "—"
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return stamp
    return f"{moment.day} {moment:%b %Y, %H:%M}"


def _route(st: dict) -> str:
    if st["route_kind"] == "not_included":
        return "Not included"
    if st["stage"] == "shorts":
        return f"On-device voice (macOS) · {st['voice']}"
    if st["model"]:
        runtime = {"ollama": "Ollama", "lmstudio": "LM Studio"}.get(
            st["provider"], st["provider"])
        return f"{runtime} · {st['model']}"
    return "On this Mac"


def _result(st: dict, files: int) -> str:
    word = STAGE_WORDS.get(st["status"], st["status"])
    detail = st.get("detail") or ""
    if st["status"] in ("done", "done_verified") and files:
        return f"{word}, {files} file{'s' if files != 1 else ''}"
    return f"{word}, {detail}" if detail and st["status"] != "not_included" else word


def _line(st: dict) -> str:
    if st["route_kind"] == "not_included":
        return "—"
    if st["route_kind"] == "local":
        return "local, no charge"
    return money_text.up_to(st["line_eur"])


def _cost(st: dict) -> str:
    if st["route_kind"] != "paid":
        return "local, no charge" if st["route_kind"] == "local" else "—"
    return money_text.paid(st["recorded_eur"])


def ai_used_lines(stages: dict) -> list[str]:
    """Legal N4, slice-1 form: no narration in this kit."""
    quotes, captions, shorts = stages["quotes"], stages["captions"], stages["shorts"]
    lines = []
    lines.append("Audiobook: not included in this kit.")
    lines.append(f"Shorts: synthetic voice {shorts['voice']} (macOS on-device "
                 "voice, `say`).")
    lines.append(f"Quotes: chosen by {quotes['model']} from your text. "
                 "The words are yours.")
    lines.append(f"Captions: written by {captions['model']}. "
                 "Read each one before you post it.")
    lines.append("EPUB and quote graphics: made on this Mac without an AI model.")
    lines.append("Stores and platforms have their own rules for AI narration "
                 "and AI labels. Check them when you publish.")
    return lines


def build(job_id: str) -> str:
    job = ledger.get_job(job_id)
    if job is None:
        raise KeyError(job_id)
    stage_rows = ledger.stages(job_id)
    by_key = {st["stage"]: st for st in stage_rows}
    outputs = ledger.done_outputs(job_id)
    per_stage: dict[str, int] = {}
    for row in outputs:
        per_stage[row["stage"]] = per_stage.get(row["stage"], 0) + 1

    out = [f"# Release kit: {job['title']}, version {job['version']}", ""]
    out.append(f"Project: {job['project_id']} · source SHA-256 "
               f"{job['source_sha256'][:12]} · {job['words']:,} words")
    out.append(f"Started {_when(job['started_at'] or job['created_at'])} · "
               f"ended {_when(job['ended_at'])} · "
               f"{STATE_WORDS.get(job['status'], job['status'])}")
    if job["status"] == "paused" and job["pause_detail"]:
        out += ["", job["pause_detail"]]
    out += ["", "| Step | Route | Result | Cost | Approved line |",
            "|---|---|---|---|---|"]
    for st in stage_rows:
        label = STAGE_BY_KEY[st["stage"]].label
        out.append(f"| {label} | {_route(st)} | "
                   f"{_result(st, per_stage.get(st['stage'], 0))} | "
                   f"{_cost(st)} | {_line(st)} |")
    total = sum(st["recorded_eur"] for st in stage_rows)
    if any(st["route_kind"] == "paid" for st in stage_rows):
        out += ["", f"Total recorded: {money_text.paid(total)} of "
                    f"{money_text.up_to(job['approved_total_eur'])} approved."]
    else:
        out += ["", "Total recorded: nothing. Every step ran on this Mac."]

    incomplete = []
    captions = by_key.get("captions")
    if captions and captions["status"] == "incomplete":
        blank = captions["result"].get("blank", [])
        slots = captions["result"].get("slots", 0)
        incomplete.append(
            f"Captions and CSV: {len(blank)} of {slots} posts have no caption. "
            f"{captions['result'].get('why', '')} Write them in Press → "
            "Calendar.".replace("  ", " "))
    quotes = by_key.get("quotes")
    if quotes and quotes["result"].get("too_long"):
        incomplete.append(
            f"Quotes: {quotes['result']['too_long']} suggested quotes were "
            "longer than 280 characters and were not used.")
    if quotes and quotes["result"].get("not_found"):
        incomplete.append(
            f"Quotes: {quotes['result']['not_found']} suggested quotes were "
            "not found word for word in the book and were not used.")
    if incomplete:
        out += ["", "## Incomplete", ""] + [f"- {line}" for line in incomplete]

    checks = [st for st in stage_rows if st["status"] == "verify"]
    if checks:
        out += ["", "## Check", ""]
        out += [f"- {STAGE_BY_KEY[st['stage']].label}: recorded at its maximum, "
                f"{money_text.paid(st['recorded_eur'])}. Compare with "
                f"{st['provider']}'s usage page." for st in checks]

    out += ["", "## AI used in this kit", ""]
    out += [f"- {line}" for line in ai_used_lines(by_key)]
    out += ["", f"Note: {NOTICES['N2']}"]

    out += ["", "## Files", ""]
    if outputs:
        out += [f"- {row['output_path']}" for row in outputs]
        out.append("")
        out.append(f"All linked to the Project {job['project_id']}.")
    else:
        out.append("None yet.")
    out += ["", "Nothing was posted, scheduled or submitted.", ""]
    return "\n".join(out)


def write(job_id: str) -> Path | None:
    job = ledger.get_job(job_id)
    if not job or not job["output_dir"]:
        return None
    path = Path(job["output_dir"]) / REPORT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(job_id), encoding="utf-8")
    return path
