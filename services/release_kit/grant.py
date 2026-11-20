"""The job-scoped request token a release-kit item must hold (spec A1, A8 SM6).

A `JobGrant` is minted only by `GodAI.authorize_job_item`, which passes the
private `_MINT` key. Every provider or voice call in the kit's code path sits
in a function that takes `grant: JobGrant` and calls `grant.check()` first;
tests/test_release_kit_contract.py walks the source to keep it that way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

_MINT = object()


class GrantClosed(RuntimeError):
    """The grant's request was recorded, voided or never opened."""


@dataclass(frozen=True)
class JobRefusal:
    """Why a job item was not authorized. Never shown as a dialog: the kit
    pauses and the window shows `reason`."""
    scope: str
    reason: str

    def __bool__(self) -> bool:      # a refusal is never a token
        return False


class JobGrant:
    __slots__ = ("token", "job_id", "stage", "item_key", "provider", "model",
                 "_is_open")

    def __init__(self, key, *, token: str, job_id: str, stage: str,
                 item_key: str, provider: str, model: str,
                 is_open: Callable[[str], bool]):
        if key is not _MINT:
            raise TypeError("JobGrant is minted only by authorize_job_item")
        self.token = token
        self.job_id = job_id
        self.stage = stage
        self.item_key = item_key
        self.provider = provider
        self.model = model
        self._is_open = is_open

    def check(self) -> None:
        if not self._is_open(self.token):
            raise GrantClosed(
                f"{self.stage} item {self.item_key} has no open job token")

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return (f"JobGrant({self.job_id[:8]}, {self.stage}, {self.item_key}, "
                f"{self.provider}/{self.model})")
