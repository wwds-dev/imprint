"""Pure state machine for a release kit (spec A4). No I/O.

The driver (ui/release_kit/driver.py) asks `next_action` after every stage
and performs what it returns. Stages run strictly in order (owner decision 9).
"""

from __future__ import annotations

from dataclasses import dataclass

TERMINAL_STAGE = {"done", "done_verified", "incomplete", "verify", "not_included"}
CHECK_STAGE = {"incomplete", "verify"}


@dataclass(frozen=True)
class RunStage:
    stage: str


@dataclass(frozen=True)
class Finish:
    status: str          # made | made_check


def next_action(job: dict, stages: list[dict]):
    """None when the job is not running; else the next stage, or Finish."""
    if not job or job.get("status") != "running":
        return None
    ordered = sorted(stages, key=lambda s: s["ordinal"])
    for st in ordered:
        if st["status"] not in TERMINAL_STAGE:
            return RunStage(st["stage"])
    if any(st["status"] in CHECK_STAGE for st in ordered):
        return Finish("made_check")
    return Finish("made")


def progress(stages: list[dict]) -> tuple[int, int, str]:
    """(step number, step count, label key) for the D3 headline."""
    ordered = sorted(stages, key=lambda s: s["ordinal"])
    for st in ordered:
        if st["status"] not in TERMINAL_STAGE:
            return st["ordinal"], len(ordered), st["stage"]
    return len(ordered), len(ordered), ordered[-1]["stage"] if ordered else ""
