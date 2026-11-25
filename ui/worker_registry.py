"""Live-worker registry and the one slot rule (ADR 0007).

A QThread whose Python object is destroyed while it runs aborts the process
("QThread: Destroyed while thread is still running", exit 134). Two things
used to cause it: a start site overwriting the host attribute that held a
running worker, and a quit that only knew a hand-written list of attribute
names. This module removes both:

- ``TrackedThread``: every QThread in the app derives from it. ``start()``
  keeps a strong reference until the thread has finished, so a running
  worker can never be garbage-collected whatever its slot does, and the
  shutdown sweep finds it without being told its name.
- ``refuse_if_busy`` / ``start_in_slot``: a busy slot is refused, never
  replaced. The check runs before any request is authorized, so a refused
  start reserves nothing and shows no cost dialog.

Pruning happens on the GUI thread only (in ``start()`` and
``live_workers()``), never from the worker's own ``finished`` signal:
dropping the last reference from inside the finishing thread is the crash.
"""

from __future__ import annotations

import logging
import os
import sys
import time

from PySide6.QtCore import QThread

BUSY_TEXT = "[Busy] The previous request is still finishing — one moment."
# One budget for the whole quit, not per worker (it used to be 2 s each).
SHUTDOWN_BUDGET_MS = 3000

_started: list[QThread] = []


class WorkerSlotBusy(RuntimeError):
    """A start site stored a worker over a running one without checking."""


def _prune() -> None:
    _started[:] = [w for w in _started if not w.isFinished()]


class TrackedThread(QThread):
    """A QThread that the live-worker registry holds until it finishes."""

    def start(self, *args, **kwargs):  # noqa: D401 - QThread's name
        _prune()
        if self not in _started:
            _started.append(self)
        super().start(*args, **kwargs)


def live_workers() -> list[QThread]:
    """Started workers that have not finished yet (GUI thread only)."""
    _prune()
    return list(_started)


def slot_busy(host, *slots: str) -> bool:
    """True when any named host slot holds a worker that is still running."""
    for slot in slots:
        running = getattr(getattr(host, slot, None), "isRunning", None)
        if callable(running) and running():
            return True
    return False


def refuse_if_busy(host, label, *slots: str) -> bool:
    """True (and the busy notice on ``label``) when a slot's worker runs.

    Call it before ``authorize_request``: a refused start must not reserve
    money or show a cost dialog.
    """
    if not slot_busy(host, *slots):
        return False
    if label is not None:
        label.setText(BUSY_TEXT)
    return True


def start_in_slot(host, slot: str, worker) -> None:
    """Store ``worker`` in ``host.<slot>`` and start it.

    Raises WorkerSlotBusy instead of replacing a running worker: a site that
    skipped ``refuse_if_busy`` fails loudly in a test rather than aborting
    the app in use.
    """
    if slot_busy(host, slot):
        raise WorkerSlotBusy(
            f"{slot} still holds a running worker; refuse_if_busy first")
    setattr(host, slot, worker)
    worker.start()


def stop_all(budget_ms: int = SHUTDOWN_BUDGET_MS) -> list[str]:
    """Cancel every live worker and wait for them against one budget.

    Returns the class names still running after the budget; never
    terminates a thread.
    """
    workers = live_workers()
    for worker in workers:
        if worker.isRunning() and hasattr(worker, "cancel"):
            try:
                worker.cancel()
            except Exception:   # noqa: BLE001 - quit must go on
                pass
    deadline = time.monotonic() + budget_ms / 1000.0
    for worker in workers:
        if worker.isRunning():
            left_ms = int(max(0.0, deadline - time.monotonic()) * 1000)
            worker.wait(left_ms)
    return [type(w).__name__ for w in workers if w.isRunning()]


def _flush_for_exit() -> None:
    logging.shutdown()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:   # noqa: BLE001
            pass


def leave_if_workers_alive(exit_fn=os._exit, flush=_flush_for_exit) -> list[str]:
    """After the event loop has ended: never let Qt destroy a running QThread.

    Interpreter shutdown would destroy any QThread still running, and Qt
    aborts the process when that happens. If one is left, flush what can be
    flushed and leave with exit code 0 instead. Called from ``main()`` after
    ``app.exec()``, never from a window's closeEvent, so a test that closes a
    window cannot end the test process.
    """
    alive = [type(w).__name__ for w in live_workers() if w.isRunning()]
    if not alive:
        return []
    logging.getLogger(__name__).warning(
        "Leaving with workers still running: %s", ", ".join(alive))
    flush()
    exit_fn(0)
    return alive
