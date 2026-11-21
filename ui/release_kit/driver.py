"""Runs one release kit on the GUI thread (spec A6).

The driver is the only caller of the guard and the ledger for a kit. It asks
the pure runner what comes next, then runs one unit of work at a time: an
EPUB export inline, and each text request, graphic or Short on a
`StageItemWorker` that never touches the database or the guard. It opens no
dialog: anything that would need the owner pauses the kit (D5).

Every exit from `running` goes through `_leave`: ledger status, keep-awake
released, report and provenance rewritten.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from agents.manuscript.calendar_export import (
    apply_captions, caption_items, write_calendar_csv)
from agents.manuscript.content_calendar import build_calendar
from agents.manuscript.quote_finder import (
    MAX_QUOTES, build_quote_messages, parse_verified_quotes, sample_windows)
from services.release_kit import ledger, provenance, report, runner, stages
from services.release_kit.ledger import file_sha256
from services.release_kit.plan import STAGE_BY_KEY, KitPlan, safe_name
from services.release_kit.power import KeepAwake

RUNTIME_NAMES = {"ollama": "Ollama", "lmstudio": "LM Studio",
                 "system": "The on-device voice"}

ARTIFACT_KINDS = {"epub": "approved_epub", "graphics": "quote_graphic",
                  "shorts": "short", "captions": "calendar_csv"}


class StageItemWorker(QThread):
    """One Qt-free callable off the GUI thread; emits its result or error."""
    done = Signal(object)
    error = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn
        self._cancelled = False

    def cancel(self):
        # The callable cannot be interrupted (Pillow, `say`, ffmpeg, a local
        # model); the result of a cancelled item is simply not used.
        self._cancelled = True

    def run(self):
        try:
            result = self._fn()
        except Exception as exc:          # reported, never raised in a thread
            self.error.emit(str(exc) or exc.__class__.__name__)
            return
        self.done.emit(result)


def default_renderers() -> dict:
    return {
        "epub": stages.make_epub,
        "text": stages.ask_text,
        "graphic": stages.render_graphic,
        "short": stages.render_short_item,
    }


class ReleaseKitDriver(QObject):
    changed = Signal(str)            # job id: ledger state moved
    progress = Signal(str, str)      # job id, step progress text

    def __init__(self, host, *, keep_awake: KeepAwake | None = None,
                 run_inline: bool = False, renderers: dict | None = None):
        super().__init__(host if isinstance(host, QObject) else None)
        self.host = host
        self.keep_awake = keep_awake or KeepAwake()
        self.run_inline = run_inline
        self.render = {**default_renderers(), **(renderers or {})}
        self.job_id: str | None = None
        self.status_text = ""
        self._stop = False
        self._worker: StageItemWorker | None = None
        # The last finished worker stays referenced until the next one
        # replaces it: Python owns it and frees it outside its own signal
        # delivery. No deleteLater(): a queued delete on a parentless object
        # that the collector also frees has crashed this suite before
        # (tests/test_model_watch_media.py, `owned`).
        self._retired: StageItemWorker | None = None
        self._callbacks = None
        self._grant = None
        self._queue: deque = deque()
        self._draining = False

    # ── public ───────────────────────────────────────────────────────────────

    def is_running(self) -> bool:
        return self.job_id is not None

    def start(self, job_id: str) -> None:
        """Run a job the ledger already has as `running`."""
        if self.job_id is not None:
            raise ledger.KitBusy("A release kit is already running.")
        self.job_id = job_id
        self._stop = False
        self.keep_awake.acquire()
        self.changed.emit(job_id)
        self._schedule(self._step)

    def resume(self, job_id: str) -> dict:
        """Resume a paused job: file check, then run from the first open step."""
        reopened = ledger.resume(job_id)
        self.start(job_id)
        return reopened

    def stop(self) -> None:
        """Pause after the current item (D3 Stop). Deletes nothing."""
        if self.job_id is None:
            return
        # Checked at the next item or step boundary. A running kit always has
        # a worker or a scheduled step, so nothing else needs waking here.
        self._stop = True
        self._say("Stopping after the current item…")

    def stop_now(self, reason: str = "quit") -> None:
        """Quit and Pause: synchronous. An item still running after 2 s stays
        `intent` and is resolved by recovery at the next launch."""
        if self.job_id is None:
            return
        self._stop = True
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.wait(2000)
            # Still referenced by host.release_kit_worker, so closeEvent's
            # sweep waits for it again rather than it being destroyed live.
        if self._grant is not None:
            self.host.close_job_item(self._grant, "cancelled",
                                     "Imprint closed during this item")
            self._grant = None
        self._worker = None
        self._callbacks = None
        key = self._current_stage()
        label = STAGE_BY_KEY[key].label if key else "the kit"
        self._leave("paused", reason,
                    f"Interrupted: Imprint closed during {label}. "
                    "Finished work is kept.")

    def discard(self, job_id: str) -> None:
        ledger.set_job_status(job_id, "discarded")
        report.write(job_id)
        self.changed.emit(job_id)

    # ── scheduling ───────────────────────────────────────────────────────────

    def _guarded(self, fn, where: str = "step"):
        """Every slot and scheduled callback runs through this: an exception
        pauses the kit instead of stranding it `running` (review P1-1)."""
        def run(*args):
            try:
                return fn(*args)
            except Exception as exc:
                self._crash(where, exc)
        return run

    def _crash(self, where: str, exc: Exception) -> None:
        """Turn an unexpected error into a pause: grant closed, stage and job
        paused (`item_failed`), keep-awake released, report rewritten."""
        if self.job_id is None:
            return
        message = str(exc) or exc.__class__.__name__
        note = getattr(self.host, "_note_failure", None)
        if note:
            try:
                note(f"release kit: {where}", exc)
            except Exception:
                pass
        grant, self._grant = self._grant, None
        if grant is not None:
            try:
                self.host.close_job_item(grant, "error", message)
            except Exception:
                pass
        key = ""
        try:
            key = self._current_stage()
        except Exception:
            pass
        label = STAGE_BY_KEY[key].label if key in STAGE_BY_KEY else "the kit"
        detail = (f"Paused during {label}: {message}. Finished work is kept. "
                  "Fix it, then resume.")
        try:
            self._pause("item_failed", detail, key or None)
        except Exception:
            if self.job_id is not None:      # _leave was never reached
                try:
                    self._leave("paused", "interrupted", detail)
                except Exception:
                    pass                     # recovery at the next launch

    def _schedule(self, fn) -> None:
        fn = self._guarded(fn)
        if not self.run_inline:
            QTimer.singleShot(0, fn)
            return
        # Inline (tests): a trampoline, so a long kit never recurses deeply.
        self._queue.append(fn)
        if self._draining:
            return
        self._draining = True
        try:
            while self._queue:
                self._queue.popleft()()
        finally:
            self._draining = False

    def _run_unit(self, fn, on_done, on_error) -> None:
        if self.run_inline:
            job_id = self.job_id

            def still(callback, value):
                # As on the threaded path: a result that arrives after the
                # kit left `running` (Quit and Pause) is not used.
                if self.job_id == job_id:
                    callback(value)
            try:
                result = fn()
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                self._schedule(lambda: still(on_error, message))
                return
            self._schedule(lambda: still(on_done, result))
            return
        worker = StageItemWorker(fn)
        self._worker = worker
        self.host.release_kit_worker = worker
        self._callbacks = (on_done, on_error)
        worker.done.connect(self._on_unit_done)
        worker.error.connect(self._on_unit_error)
        worker.start()

    def _finish_unit(self):
        worker, self._worker = self._worker, None
        callbacks, self._callbacks = self._callbacks, None
        if worker is not None:
            worker.wait()
            self._retired = worker
            if getattr(self.host, "release_kit_worker", None) is worker:
                self.host.release_kit_worker = None
        return callbacks

    def _on_unit_done(self, result) -> None:
        callbacks = self._finish_unit()
        if callbacks and self.job_id is not None:
            self._guarded(callbacks[0], "item result")(result)

    def _on_unit_error(self, message: str) -> None:
        callbacks = self._finish_unit()
        if callbacks and self.job_id is not None:
            self._guarded(callbacks[1], "item error")(message)

    # ── the loop ─────────────────────────────────────────────────────────────

    def _job(self) -> dict:
        return ledger.get_job(self.job_id)

    def _plan(self) -> KitPlan:
        return KitPlan.from_json(ledger.approval(self.job_id)["plan"]["kit"])

    def _current_stage(self) -> str:
        if self.job_id is None:
            return ""
        for st in ledger.stages(self.job_id):
            if st["status"] not in runner.TERMINAL_STAGE:
                return st["stage"]
        return ""

    def _say(self, text: str) -> None:
        self.status_text = text
        if self.job_id is not None:
            self.progress.emit(self.job_id, text)

    def _step(self) -> None:
        if self.job_id is None:
            return
        action = runner.next_action(self._job(), ledger.stages(self.job_id))
        if action is None:
            # The job left `running` without this driver (discarded, or
            # paused by another window's recovery): stop holding it.
            self._leave("paused", "interrupted")
            return
        if isinstance(action, runner.Finish):
            self._leave(action.status)
            return
        if self._stop:
            label = STAGE_BY_KEY[action.stage].label
            ledger.set_stage(self.job_id, action.stage, status="paused")
            self._leave("paused", "user_stop",
                        f"Paused by you. Finished steps stay done. Resume "
                        f"continues from {label}.")
            return
        ledger.set_stage(self.job_id, action.stage, status="running")
        self.changed.emit(self.job_id)
        getattr(self, f"_stage_{action.stage}")()

    def _stage_done(self, key: str, *, status: str = "done", **fields) -> None:
        ledger.set_stage(self.job_id, key, status=status, **fields)
        self.changed.emit(self.job_id)
        self._schedule(self._step)

    def _pause(self, reason: str, detail: str, stage_key: str | None = None) -> None:
        if stage_key:
            ledger.set_stage(self.job_id, stage_key, status="paused",
                             detail=detail)
        self._leave("paused", reason, detail)

    def _leave(self, status: str, reason: str = "", detail: str = "") -> None:
        """The single exit hook from `running` (A4)."""
        job_id = self.job_id
        if job_id is None:
            return
        try:
            if (ledger.get_job(job_id) or {}).get("status") == "running":
                ledger.set_job_status(job_id, status, reason=reason,
                                      detail=detail)
        finally:
            self.keep_awake.release()
            self.job_id = None
            self._stop = False
            self._grant = None
            for write in (report.write, provenance.write_sidecar):
                try:
                    write(job_id)
                except Exception as exc:
                    note = getattr(self.host, "_note_failure", None)
                    if note:
                        note("release kit: write report", exc)
            self.status_text = ""
            self.changed.emit(job_id)

    # ── helpers for items ────────────────────────────────────────────────────

    def _link(self, key: str, path: Path) -> int | None:
        from services.project_artifacts import record
        job = self._job()
        if not job["project_id"]:
            return None
        return record(job["project_id"], STAGE_BY_KEY[key].agent,
                      ARTIFACT_KINDS.get(key, key), path,
                      f"Release kit v{job['version']} · {Path(path).name}")

    def _finish_item(self, key: str, item_key: str, path: Path,
                     ai: dict, **fields) -> None:
        artifact_id = None
        try:
            artifact_id = self._link(key, path)
        except Exception as exc:          # stage 8 links any that are missing
            self.host._note_failure("release kit: link output", exc)
        ledger.mark_item(self.job_id, key, item_key, "done",
                         output_path=str(path), output_sha256=file_sha256(path),
                         output_kind=ARTIFACT_KINDS.get(key, key),
                         artifact_id=artifact_id, ai=ai, **fields)

    def _refused(self, key: str, refusal) -> None:
        label = STAGE_BY_KEY[key].label
        reason = "route_unavailable" if refusal.scope in (
            "not_in_this_version", "route") else "cap_refused"
        self._pause(reason, f"Paused before {label}: {refusal.reason} "
                            "Nothing was sent.", key)

    def _unavailable(self, key: str, provider: str, error: str) -> None:
        label = STAGE_BY_KEY[key].label
        who = RUNTIME_NAMES.get(provider, provider)
        self._pause("route_unavailable",
                    f"Paused during {label}: {who} did not answer ({error}). "
                    "Nothing more was sent. Start it, then resume.", key)

    def _out(self) -> Path:
        return Path(self._job()["output_dir"])

    # ── stages ───────────────────────────────────────────────────────────────

    def _stage_epub(self) -> None:
        job = self._job()
        item = ledger.ensure_item(self.job_id, "epub", "epub:file")
        if item["state"] == "done":
            return self._stage_done("epub")
        self._say("Making the EPUB…")
        path = self._out() / f"{safe_name(job['title'])}_v{job['version']}.epub"
        n = 2
        while path.exists():              # a changed earlier file stays put
            path = path.with_name(
                f"{safe_name(job['title'])}_v{job['version']}-{n}.epub")
            n += 1
        ledger.mark_item(self.job_id, "epub", "epub:file", "intent")
        try:
            # EbookLib plus a receipt row: quick, and it writes the database,
            # so it runs here rather than on a worker.
            receipt = self.render["epub"](job["project_id"], job["version"], path)
        except Exception as exc:
            ledger.mark_item(self.job_id, "epub", "epub:file", "failed")
            return self._pause("item_failed",
                               f"Paused during EPUB: {exc}. Fix it, then resume.",
                               "epub")
        self._finish_item("epub", "epub:file", path,
                          provenance.ai_facts(ledger.stage(self.job_id, "epub")))
        self._stage_done("epub", result={"receipt_id": receipt.get("id"),
                                         "path": str(path)})

    def _stage_audiobook(self) -> None:      # slice 1: never included
        self._stage_done("audiobook", status="not_included")

    def _stage_quotes(self) -> None:
        from services.project_manuscripts import get_version
        job = self._job()
        st = ledger.stage(self.job_id, "quotes")
        source = get_version(job["project_id"], job["version"])
        if not source:
            return self._pause("item_failed",
                               "Paused before Quotes: the approved version is "
                               "no longer in the Project.", "quotes")
        windows = sample_windows(source["body"])
        messages = build_quote_messages(windows, MAX_QUOTES)
        try:
            stages.check_quote_bound(messages)
        except stages.BoundExceeded as exc:
            return self._pause("over_line", f"Paused before Quotes: {exc}. "
                                            "Nothing was sent.", "quotes")
        key = ledger.next_request_key(self.job_id, "quotes", "quotes:request")
        ledger.ensure_item(self.job_id, "quotes", key)
        grant = self.host.authorize_job_item(
            self.job_id, "quotes", key, provider=st["provider"],
            model=st["model"], messages=messages)
        if not grant:
            ledger.mark_item(self.job_id, "quotes", key, "failed")
            return self._refused("quotes", grant)
        self._grant = grant
        ledger.mark_item(self.job_id, "quotes", key, "intent")
        self._say(f"Asking {st['model']} for quotes from "
                  f"{len(windows)} passage{'s' if len(windows) != 1 else ''}…")
        prompt = messages[-1]["content"]
        instructions = job["project_instructions"]

        def done(reply):
            self._grant = None
            entry = self.host.record_job_item(grant, reply.text, reply.usage) or {}
            parsed = parse_verified_quotes(reply.text, windows)
            ledger.mark_item(self.job_id, "quotes", key, "done",
                             usage_id=entry.get("usage_id"),
                             ai=provenance.ai_facts(st))
            result = {"quotes": parsed.quotes, "too_long": parsed.too_long,
                      "not_found": parsed.not_found,
                      "duplicates": parsed.duplicates,
                      "over_limit": parsed.over_limit,
                      "passages": len(windows),
                      "stop_reason": (reply.usage or {}).get("stop_reason", "")}
            if not parsed.quotes:
                ledger.set_stage(self.job_id, "quotes", result=result)
                return self._pause(
                    "no_quotes",
                    "Paused after Quotes: the model suggested no quote found "
                    "word for word in the book. Nothing more ran. Resume asks "
                    "again.", "quotes")
            self._stage_done("quotes", result=result,
                             detail=f"{len(parsed.quotes)} quotes")

        def failed(message):
            self._grant = None
            self.host.close_job_item(grant, "error", message)
            ledger.mark_item(self.job_id, "quotes", key, "failed")
            self._unavailable("quotes", st["provider"], message)

        self._run_unit(
            lambda: self.render["text"](grant, self.host.run_backend, messages,
                                        prompt, instructions),
            done, failed)

    def _stage_calendar(self) -> None:
        plan = self._plan()
        quotes = ledger.stage(self.job_id, "quotes")["result"].get("quotes", [])
        slots = build_calendar(quotes, plan.weeks, plan.start_date, plan.platforms)
        ids = {quote: f"q{i + 1:02d}" for i, quote in enumerate(quotes)}
        self._stage_done("calendar", result={
            "slots": stages.slots_to_json(slots), "quote_ids": ids},
            detail=f"{len(slots)} posts")

    def _next_open(self, key: str, keys: list[str]) -> str | None:
        for item_key in keys:
            row = ledger.ensure_item(self.job_id, key, item_key)
            if row["state"] != "done":
                return item_key
        return None

    def _stage_graphics(self) -> None:
        job = self._job()
        cal = ledger.stage(self.job_id, "calendar")["result"]
        ids = cal["quote_ids"]
        by_key = {f"graphic:{qid}": quote for quote, qid in ids.items()}
        quote_model = ledger.stage(self.job_id, "quotes")["model"]
        st = ledger.stage(self.job_id, "graphics")
        keys = list(by_key)
        if self._stop:
            return self._schedule(self._step)
        item_key = self._next_open("graphics", keys)
        if item_key is None:
            return self._stage_done("graphics", detail=f"{len(keys)} graphics")
        done_count = keys.index(item_key)
        self._say(f"Quote graphic {done_count + 1} of {len(keys)}")
        path = self._out() / "graphics" / f"{item_key.split(':')[1]}.png"
        quote = by_key[item_key]
        ledger.mark_item(self.job_id, "graphics", item_key, "intent")

        def done(_result):
            self._finish_item("graphics", item_key, path,
                              provenance.ai_facts(st, quote_model=quote_model))
            self._schedule(self._stage_graphics)

        def failed(message):
            ledger.mark_item(self.job_id, "graphics", item_key, "failed")
            self._pause("item_failed",
                        f"Paused during Quote graphics: {message}. "
                        f"{done_count} of {len(keys)} graphics are made and "
                        "kept. Fix it, then resume.", "graphics")

        self._run_unit(
            lambda: self.render["graphic"](quote, path, job["byline"]),
            done, failed)

    def _stage_shorts(self) -> None:
        cal = ledger.stage(self.job_id, "calendar")["result"]
        ids = cal["quote_ids"]
        shorts = [s for s in cal["slots"] if s["format"] == "short"]
        keys = [f"short:s{i + 1:02d}" for i in range(len(shorts))]
        st = ledger.stage(self.job_id, "shorts")
        quote_model = ledger.stage(self.job_id, "quotes")["model"]
        if self._stop:
            return self._schedule(self._step)
        item_key = self._next_open("shorts", keys)
        if item_key is None:
            return self._stage_done("shorts", detail=f"{len(keys)} Shorts")
        index = keys.index(item_key)
        slot = shorts[index]
        image = self._out() / "graphics" / f"{ids[slot['quote']]}.png"
        path = self._out() / "shorts" / f"{item_key.split(':')[1]}.mp4"
        self._say(f"Short {index + 1} of {len(keys)}")
        grant = self.host.authorize_job_item(
            self.job_id, "shorts", item_key, provider=st["provider"],
            model="say", flat_cost_eur=0.0)
        if not grant:
            ledger.mark_item(self.job_id, "shorts", item_key, "failed")
            return self._refused("shorts", grant)
        self._grant = grant
        ledger.mark_item(self.job_id, "shorts", item_key, "intent")

        def done(_result):
            self._grant = None
            self.host.close_job_item(grant, "success")
            self._finish_item("shorts", item_key, path,
                              provenance.ai_facts(st, quote_model=quote_model))
            self._schedule(self._stage_shorts)

        def failed(message):
            self._grant = None
            self.host.close_job_item(grant, "error", message)
            ledger.mark_item(self.job_id, "shorts", item_key, "failed")
            self._pause("item_failed",
                        f"Paused during Shorts: {message}. {index} of "
                        f"{len(keys)} Shorts are made and kept. Fix it, then "
                        "resume.", "shorts")

        self._run_unit(
            lambda: self.render["short"](grant, slot["quote"], image, path,
                                         st["voice"]),
            done, failed)

    def _stage_captions(self) -> None:
        job = self._job()
        cal = ledger.stage(self.job_id, "calendar")["result"]
        slots = stages.slots_from_json(cal["slots"])
        st = ledger.stage(self.job_id, "captions")
        shorts_row = ledger.stage(self.job_id, "shorts")
        messages = stages.caption_messages(caption_items(slots, ensure_ascii=False))
        try:
            stages.check_caption_bound(messages, len(slots))
        except stages.BoundExceeded as exc:
            return self._pause("over_line", f"Paused before Captions and CSV: "
                                            f"{exc}. Nothing was sent.", "captions")
        key = ledger.next_request_key(self.job_id, "captions", "captions:request")
        ledger.ensure_item(self.job_id, "captions", key)
        grant = self.host.authorize_job_item(
            self.job_id, "captions", key, provider=st["provider"],
            model=st["model"], messages=messages)
        if not grant:
            ledger.mark_item(self.job_id, "captions", key, "failed")
            return self._refused("captions", grant)
        self._grant = grant
        ledger.mark_item(self.job_id, "captions", key, "intent")
        self._say(f"Writing {len(slots)} captions with {st['model']}…")
        prompt = messages[-1]["content"]

        def done(reply):
            self._grant = None
            entry = self.host.record_job_item(grant, reply.text, reply.usage) or {}
            ledger.mark_item(self.job_id, "captions", key, "done",
                             usage_id=entry.get("usage_id"),
                             ai=provenance.ai_facts(st))
            blank = apply_captions(slots, reply.text)
            path = self._out() / "calendar.csv"
            write_calendar_csv(slots, path, ai_column=lambda s: provenance.csv_ai_cell(
                s.format, shorts_row, st, bool(s.caption.strip())))
            ledger.ensure_item(self.job_id, "captions", "calendar:csv")
            self._finish_item("captions", "calendar:csv", path,
                              provenance.ai_facts(st))
            cut = (reply.usage or {}).get("stop_reason") == "length"
            result = {"slots": len(slots), "blank": blank,
                      "calendar": stages.slots_to_json(slots),
                      "why": ("The reply stopped at the 8,192-token limit."
                              if cut else "The reply had fewer captions than posts."
                              if blank else "")}
            if blank:
                return self._stage_done(
                    "captions", status="incomplete", result=result,
                    detail=f"{len(slots) - len(blank)} of {len(slots)} captions")
            self._stage_done("captions", result=result,
                             detail=f"{len(slots)} captions")

        def failed(message):
            self._grant = None
            self.host.close_job_item(grant, "error", message)
            ledger.mark_item(self.job_id, "captions", key, "failed")
            self._unavailable("captions", st["provider"], message)

        self._run_unit(
            lambda: self.render["text"](grant, self.host.run_backend, messages,
                                        prompt, job["project_instructions"]),
            done, failed)

    def _stage_link(self) -> None:
        """Stage 8: link anything a crash left unlinked, then the report."""
        self._say("Linking files to the Project…")
        for row in ledger.done_outputs(self.job_id):
            if row["artifact_id"] or not Path(row["output_path"]).is_file():
                continue
            try:
                artifact_id = self._link(row["stage"], Path(row["output_path"]))
            except Exception as exc:
                self.host._note_failure("release kit: link output", exc)
                continue
            ledger.mark_item(self.job_id, row["stage"], row["item_key"], "done",
                             artifact_id=artifact_id)
        for path, kind in ((report.write(self.job_id), "release_kit_report"),
                           (provenance.write_sidecar(self.job_id), "provenance")):
            if path is None:
                continue
            try:
                from services.project_artifacts import record
                job = self._job()
                if job["project_id"]:
                    record(job["project_id"], "manuscript", kind, path,
                           f"Release kit v{job['version']} · {path.name}")
            except Exception as exc:
                self.host._note_failure("release kit: link report", exc)
        self._stage_done("link", detail="every file linked")

