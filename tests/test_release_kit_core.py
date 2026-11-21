"""Release kit, Qt-free parts (spec one-click-release, slice 1).

Plan and estimate, ledger states and recovery, the pure runner, keep-awake,
report and provenance. Temp database, no network, no Qt.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import date
from pathlib import Path

import pytest

from services import database
from services.release_kit import ledger, plan as kitplan, provenance, report, runner
from services.release_kit.plan import KitPlan, Route
from services.release_kit.power import KeepAwake


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "kit.db")
    database.init_db()
    with database.get_connection() as conn:
        conn.execute("INSERT INTO projects (id, name) VALUES ('book', 'Book')")
    return tmp_path


def _plan(tmp_path, **kw) -> KitPlan:
    values = dict(
        project_id="book", project_name="Book", version=3, title="The Salt Road",
        byline="A. Writer", source_sha256="ab" * 32, words=84_210,
        characters=512_300, output_dir=str(tmp_path / "kit"),
        quotes=Route("ollama", "local:8b"), captions=Route("ollama", "local:8b"),
        start_date=date(2026, 11, 20))
    values.update(kw)
    return KitPlan(**values)


def _job(tmp_path, **kw) -> str:
    p = _plan(tmp_path, **kw)
    return ledger.create_job(p, plan_json={"kit": p.to_json()},
                             start_label="Start")


# ── plan and estimate ────────────────────────────────────────────────────────

def test_four_weeks_on_three_platforms_is_56_posts_22_shorts_34_graphics(tmp_path):
    est = kitplan.estimate(_plan(tmp_path))
    assert (est.slots, est.shorts, est.graphic_slots) == (56, 22, 34)
    assert est.can_start and est.figure == "No charge"
    assert [r.stage for r in est.rows] == [s.key for s in kitplan.STAGES]
    rows = {r.stage: r for r in est.rows}
    assert rows["calendar"].basis == "56 posts: 22 Shorts, 34 graphic posts"
    assert rows["quotes"].basis.startswith(
        "Up to 20 quotes from 12 passages across the whole book")
    assert all(r.maximum == "local, no charge" for r in est.rows
               if r.stage != "audiobook")


def test_audiobook_row_is_visible_and_not_included_in_slice_1(tmp_path):
    row = {r.stage: r for r in kitplan.estimate(_plan(tmp_path)).rows}["audiobook"]
    assert (row.route, row.maximum, row.route_kind) == ("Not included", "—",
                                                        "not_included")
    assert "Narrate in Booth" in row.basis


def test_on_device_shorts_carry_notice_n2(tmp_path):
    est = kitplan.estimate(_plan(tmp_path))
    assert est.notices_shown() == ["N2"]
    assert "personal, non-commercial" in kitplan.NOTICES["N2"]


@pytest.mark.parametrize("stage", ["quotes", "captions"])
def test_a_paid_text_route_blocks_the_whole_estimate(tmp_path, stage):
    est = kitplan.estimate(_plan(tmp_path, **{stage: Route("anthropic", "claude")}))
    assert not est.can_start
    assert est.blocked[0][0] == stage
    assert kitplan.blocking_sentence(est).startswith("Cannot start: ")
    assert "local steps only" in kitplan.blocking_sentence(est)


def test_a_paid_shorts_voice_blocks(tmp_path):
    est = kitplan.estimate(_plan(tmp_path, shorts=Route("elevenlabs", "", "Rachel")))
    assert ("shorts" in dict(est.blocked)) and not est.can_start


def test_no_local_model_blocks_with_check_again_wording(tmp_path):
    est = kitplan.estimate(_plan(tmp_path, quotes=Route()))
    assert kitplan.blocking_sentence(est) == (
        "Cannot start: No local model answered. Start Ollama or LM Studio, "
        "then press Check again.")


@pytest.mark.parametrize("value,local", [
    ("", True), ("127.0.0.1:11434", True), (":11500", True),
    ("http://localhost:11434", True), ("0.0.0.0", True), ("[::1]:11434", True),
    ("http://192.168.1.20:11434", False), ("gpu-box.local", False),
    ("https://ollama.example.com", False)])
def test_a_local_runtime_pointed_at_another_machine_blocks(
        tmp_path, monkeypatch, value, local):
    """Review P2-1: "on this Mac" holds only for a loopback address."""
    monkeypatch.setenv("OLLAMA_HOST", value)
    assert (kitplan.endpoint_problem("ollama") == "") is local
    est = kitplan.estimate(_plan(tmp_path))
    assert est.can_start is local
    if not local:
        assert "not this Mac" in kitplan.blocking_sentence(est)
    monkeypatch.setenv("LMSTUDIO_URL", "http://10.0.0.5:1234/v1")
    assert "10.0.0.5" in kitplan.endpoint_problem("lmstudio")
    assert kitplan.endpoint_problem("system") == ""
    # The client's own address wins over the environment.
    assert kitplan.endpoint_problem("ollama", "http://127.0.0.1:11434") == ""


def test_empty_title_or_no_platform_blocks(tmp_path):
    assert not kitplan.estimate(_plan(tmp_path, byline=" ")).can_start
    assert not kitplan.estimate(_plan(tmp_path, platforms=[])).can_start


def test_a_short_book_is_one_passage(tmp_path):
    rows = {r.stage: r for r in kitplan.estimate(_plan(tmp_path, characters=20_000)).rows}
    assert "from 1 passage across" in rows["quotes"].basis


def test_output_folder_is_new_and_never_reused(tmp_path):
    first = kitplan.default_output_dir(tmp_path, "The Salt Road: A Novel", 3,
                                       date(2026, 11, 20))
    assert first.name == "The_Salt_Road_A_Novel_v3_2026-11-20"
    first.mkdir()
    second = kitplan.default_output_dir(tmp_path, "The Salt Road: A Novel", 3,
                                        date(2026, 11, 20))
    assert second.name.endswith("-2")
    assert kitplan.output_dir_problem(first) == ""          # empty: fine
    (first / "x.txt").write_text("x")
    assert "already has files" in kitplan.output_dir_problem(first)
    assert kitplan.output_dir_problem(tmp_path / "new" / "deeper") == ""


def test_plan_round_trips_through_json(tmp_path):
    p = _plan(tmp_path)
    assert KitPlan.from_json(json.loads(json.dumps(p.to_json()))) == p


# ── ledger ───────────────────────────────────────────────────────────────────

def test_create_job_writes_approval_and_eight_stages(db):
    job_id = _job(db)
    job = ledger.get_job(job_id)
    assert job["status"] == "running" and job["approval_seq"] == 1
    stages = ledger.stages(job_id)
    assert [s["stage"] for s in stages] == [s.key for s in kitplan.STAGES]
    by = {s["stage"]: s for s in stages}
    assert by["audiobook"]["status"] == "not_included"
    assert by["quotes"]["route_kind"] == "local"
    assert by["shorts"]["provider"] == "system"
    assert by["shorts"]["voice"] == "Samantha"
    assert ledger.approval(job_id)["plan"]["kit"]["version"] == 3


def test_only_one_kit_runs_at_a_time(db):
    first = _job(db)
    with pytest.raises(ledger.KitBusy):
        _job(db)
    ledger.set_job_status(first, "paused", reason="user_stop")
    second = _job(db)                       # a paused kit may wait
    with pytest.raises(ledger.KitBusy):
        ledger.resume(first)
    assert ledger.running_job()["id"] == second


@pytest.mark.parametrize("start,target,ok", [
    ("running", "paused", True), ("running", "made", True),
    ("running", "made_check", True), ("running", "discarded", False),
    ("paused", "running", True), ("paused", "discarded", True),
    ("paused", "made", False),
])
def test_job_transitions(db, start, target, ok):
    job_id = _job(db)
    if start == "paused":
        ledger.set_job_status(job_id, "paused", reason="user_stop")
    if ok:
        ledger.set_job_status(job_id, target, reason="user_stop")
        assert ledger.get_job(job_id)["status"] == target
    else:
        with pytest.raises(ledger.TransitionError):
            ledger.set_job_status(job_id, target, reason="user_stop")


def test_a_pause_needs_a_known_reason(db):
    with pytest.raises(ledger.TransitionError):
        ledger.set_job_status(_job(db), "paused", reason="tired")


def test_request_keys_take_the_next_attempt(db):
    job_id = _job(db)
    first = ledger.next_request_key(job_id, "quotes", "quotes:request")
    ledger.ensure_item(job_id, "quotes", first)
    assert first == "quotes:request#1"
    assert ledger.next_request_key(job_id, "quotes", "quotes:request") == \
        "quotes:request#2"


def test_recovery_pauses_a_running_kit_and_resolves_local_intents(db):
    job_id = _job(db)
    ledger.set_stage(job_id, "quotes", status="running")
    ledger.ensure_item(job_id, "quotes", "quotes:request#1")
    ledger.mark_item(job_id, "quotes", "quotes:request#1", "intent")
    ledger.ensure_item(job_id, "graphics", "graphic:q01")
    ledger.mark_item(job_id, "graphics", "graphic:q01", "intent")
    assert ledger.recover() == [job_id]
    job = ledger.get_job(job_id)
    assert (job["status"], job["pause_reason"]) == ("paused", "interrupted")
    assert ledger.stage(job_id, "quotes")["status"] == "paused"
    # (c) local: a request attempt is closed as failed (a retry gets #2),
    # a file item goes back to planned.
    assert ledger.item(job_id, "quotes", "quotes:request#1")["state"] == "failed"
    assert ledger.item(job_id, "graphics", "graphic:q01")["state"] == "planned"
    assert ledger.recover() == [job_id]     # idempotent


def test_resume_verifies_files_and_reopens_only_changed_local_stages(db):
    job_id = _job(db)
    out = Path(ledger.get_job(job_id)["output_dir"])
    out.mkdir(parents=True)
    files = {}
    for stage, key in (("epub", "epub:file"), ("graphics", "graphic:q01"),
                       ("graphics", "graphic:q02")):
        path = out / key.replace(":", "_")
        path.write_bytes(key.encode())
        files[key] = path
        ledger.ensure_item(job_id, stage, key)
        ledger.mark_item(job_id, stage, key, "done", output_path=str(path),
                         output_sha256=ledger.file_sha256(path))
    for stage in ("epub", "quotes", "calendar", "graphics"):
        ledger.set_stage(job_id, stage, status="done")
    ledger.set_job_status(job_id, "paused", reason="user_stop")
    files["graphic:q02"].write_bytes(b"edited")
    reopened = ledger.resume(job_id)
    assert reopened == {"graphics": ["graphic:q02"]}
    by = {s["stage"]: s["status"] for s in ledger.stages(job_id)}
    assert by["epub"] == by["quotes"] == by["calendar"] == "done_verified"
    assert by["graphics"] == "waiting"
    assert ledger.item(job_id, "graphics", "graphic:q01")["state"] == "done"
    assert ledger.item(job_id, "graphics", "graphic:q02")["state"] == "planned"
    assert ledger.get_job(job_id)["status"] == "running"


# ── runner ───────────────────────────────────────────────────────────────────

def _stages(**status):
    return [{"stage": s.key, "ordinal": s.ordinal,
             "status": status.get(s.key, "waiting")} for s in kitplan.STAGES]


def test_runner_runs_stages_in_order_and_finishes():
    job = {"status": "running"}
    assert runner.next_action(job, _stages(audiobook="not_included")) == \
        runner.RunStage("epub")
    done = {s.key: "done" for s in kitplan.STAGES}
    done["audiobook"] = "not_included"
    assert runner.next_action(job, _stages(**{**done, "graphics": "waiting"})) \
        == runner.RunStage("graphics")
    assert runner.next_action(job, _stages(**done)) == runner.Finish("made")
    assert runner.next_action(job, _stages(**{**done, "captions": "incomplete"})) \
        == runner.Finish("made_check")
    assert runner.next_action({"status": "paused"}, _stages()) is None
    assert runner.progress(_stages(**{**done, "shorts": "running"})) == (6, 8, "shorts")


# ── keep-awake ───────────────────────────────────────────────────────────────

class _Proc:
    def __init__(self, args, **kw):
        self.args, self.alive, self.terminated = args, True, 0

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.terminated += 1
        self.alive = False

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.alive = False


def test_keep_awake_spawns_caffeinate_bound_to_the_app_pid_and_releases():
    spawned = []

    def popen(args, **kw):
        spawned.append(_Proc(args, **kw))
        return spawned[-1]

    awake = KeepAwake(popen=popen, which=lambda name: "/usr/bin/" + name, pid=4242)
    assert awake.acquire() and awake.held
    assert awake.acquire()                       # idempotent: one holder
    assert len(spawned) == 1
    assert spawned[0].args == ["/usr/bin/caffeinate", "-i", "-w", "4242"]
    awake.release()
    assert not awake.held and spawned[0].terminated == 1
    awake.release()                              # safe twice


def test_keep_awake_without_caffeinate_is_a_no_op():
    awake = KeepAwake(popen=lambda *a, **k: pytest.fail("spawned"),
                      which=lambda name: None)
    assert awake.acquire() is False and not awake.held


def test_keep_awake_kills_a_holder_that_ignores_terminate():
    class Stubborn(_Proc):
        def wait(self, timeout=None):
            if not getattr(self, "killed", False) and self.terminated:
                self.killed = True
                raise subprocess.TimeoutExpired("caffeinate", timeout)
            return 0

    proc = Stubborn([])
    awake = KeepAwake(popen=lambda *a, **k: proc, which=lambda n: n)
    awake.acquire()
    awake.release()
    assert proc.killed


# ── report and provenance ────────────────────────────────────────────────────

def test_report_is_built_from_the_ledger_and_claims_nothing(db):
    job_id = _job(db)
    out = Path(ledger.get_job(job_id)["output_dir"])
    out.mkdir(parents=True)
    path = out / "q01.png"
    path.write_bytes(b"png")
    ledger.ensure_item(job_id, "graphics", "graphic:q01")
    ledger.mark_item(job_id, "graphics", "graphic:q01", "done",
                     output_path=str(path), output_sha256="x",
                     ai={"ai": False})
    ledger.set_stage(job_id, "quotes", status="done",
                     result={"quotes": ["a"], "too_long": 2, "not_found": 1})
    ledger.set_stage(job_id, "captions", status="incomplete",
                     result={"slots": 56, "blank": list(range(14)),
                             "why": "The reply stopped at the 8,192-token limit."})
    ledger.set_job_status(job_id, "made_check")
    text = report.build(job_id)
    assert text.startswith("# Release kit: The Salt Road, version 3")
    assert "Made, with items to check" in text
    assert "| Audiobook | Not included | Not included | — | — |" in text
    assert "Captions and CSV: 14 of 56 posts have no caption." in text
    assert "2 suggested quotes were longer than 280 characters" in text
    assert "## AI used in this kit" in text
    assert "Quotes: chosen by local:8b from your text. The words are yours." in text
    assert "Total recorded: nothing. Every step ran on this Mac." in text
    assert text.rstrip().endswith("Nothing was posted, scheduled or submitted.")
    for word in ("income", "sales", "earn", "reach", "revenue", "royalt"):
        assert word not in text.lower()
    written = report.write(job_id)
    assert written.read_text(encoding="utf-8") == text


def test_provenance_sidecar_records_facts_and_embeds_nothing(db):
    job_id = _job(db)
    out = Path(ledger.get_job(job_id)["output_dir"])
    out.mkdir(parents=True)
    png = out / "q01.png"
    png.write_bytes(b"png-bytes")
    st = ledger.stage(job_id, "graphics")
    ledger.ensure_item(job_id, "graphics", "graphic:q01")
    ledger.mark_item(job_id, "graphics", "graphic:q01", "done",
                     output_path=str(png), output_sha256=ledger.file_sha256(png),
                     output_kind="quote_graphic",
                     ai=provenance.ai_facts(st, quote_model="local:8b"))
    sidecar = provenance.write_sidecar(job_id)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["approved_version"] == 3
    assert data["outputs"][0]["ai"]["quote_chosen_by"] == "local:8b"
    assert "No AI marking is embedded" in data["note"]
    assert png.read_bytes() == b"png-bytes"
    shorts = ledger.stage(job_id, "shorts")
    captions = ledger.stage(job_id, "captions")
    assert provenance.csv_ai_cell("short", shorts, captions) == (
        "voice: synthetic (macOS Samantha); caption: written by local:8b "
        "(Ollama, on this Mac)")
    assert provenance.csv_ai_cell("graphic", shorts, captions, False) == "caption: none"


def test_usage_row_per_item_survives_in_the_real_tracker(db):
    from services.usage_tracker import UsageTracker
    tracker = UsageTracker()
    entry = tracker.log_request("manuscript", "ollama", "local:8b", "p", "r",
                                job_id="j", job_item="quotes:request#1")
    assert entry["usage_id"] and entry["cost_eur"] == 0
    with pytest.raises(sqlite3.IntegrityError):
        tracker.log_request("manuscript", "ollama", "local:8b", "p", "r",
                            job_id="j", job_item="quotes:request#1")
