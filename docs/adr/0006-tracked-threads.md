# ADR 0006: Every QThread is a TrackedThread; shutdown sweeps the registry

Status: **Accepted** by the owner at the Architect gate, 2026-11-25 ("Approve as written (Recommended)"). Spec: `docs/specs/worker-crash-class.md`
(section "Architecture", A1, A2, A5).

## Context
A `QThread` whose Python object is destroyed while it runs aborts the process (Qt prints
`QThread: Destroyed while thread is still running`, exit 134). In Imprint that happened two ways
(audit 2026-11-23, code-review P1-1, architecture A-1):
- a start site overwrote the host attribute that held a running worker;
- `closeEvent` stopped workers from a hand-written list of attribute names, which missed two slots,
  and accepted the close after a 2 s wait per worker whether or not the thread had ended.

## Decision
1. Every `QThread` subclass in the app derives from `ui.worker_registry.TrackedThread`. Its
   `start()` adds the worker to a module-level registry that keeps a strong reference until the
   thread has finished. Pruning happens on the GUI thread only. A source test fails on any class
   that subclasses `QThread` directly.
2. A worker is stored in a host slot only through `start_in_slot`, after `refuse_if_busy` has
   checked the slot before any request is authorized. A busy slot is refused, never replaced.
3. Shutdown cancels and waits for `live_workers()`, against one shared budget. A worker still
   running after it is cut off with `os._exit(0)` after logging is flushed, never left to Qt's
   destructor and never stopped with `QThread.terminate()`.
4. Network-only work that holds no Qt objects and writes nothing may use `DaemonWorker` (a Python
   daemon thread) instead; it is not registered.

## Consequences
- A new worker class or start site cannot reintroduce the abort without failing a test.
- Quit takes at most about 3 s more than today's best case and never aborts.
- `os._exit` skips `atexit` handlers; the app registers none (checked 2026-11-25). Persistence
  must keep happening before the sweep (the manuscript save already does).
