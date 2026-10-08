"""
Model ratings fetcher — drift guard
===================================
Type: Cross-repository consistency check.

The LMArena ratings module exists twice in this workspace:

    imprint/services/benchmarks.py
    sentinel/services/benchmarks.py

Imprint's is a copy of Sentinel's (2026-10-08), not a shared package, and
copies drift — the narrator converter's did, for three days, before its own
guard (test_converter_drift.py) existed. The fragile parts here are the ones a
fix is likely to land in on one side only: the name matching (`arena_key`,
`ALIASES`) and the paging around Hugging Face's rate limit.

So this test compares the two line by line after removing the differences
Imprint's copy is *allowed* to have, listed in LOCAL below. It skips when
Sentinel is not checked out beside this repository, which is normal for a
clone or a worktree.

**If this fails**, do not edit the normaliser to make it pass. Port the
change to the other copy, or add a genuinely local difference to LOCAL with a
comment saying why it is local.
"""

import difflib
import itertools
import re
from pathlib import Path

import pytest

SELF = "imprint"

_HERE = Path(__file__).resolve()
MINE = _HERE.parents[1] / "services" / "benchmarks.py"
ROOT = _HERE.parents[2]
SIBLINGS = {
    "sentinel": "sentinel/services/benchmarks.py",
}

LOCAL = (
    # The module docstring describes how each app uses the ratings.
    (re.compile(r'\A""".*?"""', re.S), '"""<local docstring>"""'),
    # Each app names itself to Hugging Face.
    (re.compile(r'headers=\{"User-Agent": "[^"]*"\}'), "headers=<local>"),
    # Imprint ranks on quality against the table's best rating, which needs
    # one helper Sentinel's router does not (best_rating). Kept in one marked
    # block so the rest stays comparable.
    (re.compile(r"^# ── Imprint only ─+$.*?^# ── end Imprint only ─+$",
                re.M | re.S), ""),
)


def _normalised(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    for pattern, placeholder in LOCAL:
        text = pattern.sub(placeholder, text)
    return [line for line in text.splitlines() if line.strip()]


def test_the_local_differences_are_still_there():
    """Each LOCAL pattern must match Imprint's copy, or it has gone stale and
    is hiding nothing — or something else now carries the difference."""
    text = MINE.read_text(encoding="utf-8")
    for pattern, _placeholder in LOCAL:
        assert pattern.search(text), pattern.pattern


@pytest.mark.parametrize("other", list(SIBLINGS))
def test_benchmarks_copies_have_not_drifted(other):
    theirs = ROOT / SIBLINGS[other]
    if not theirs.is_file():
        pytest.skip(f"{other} is not checked out beside this repository")

    a, b = _normalised(MINE), _normalised(theirs)
    if a == b:
        return

    diff = "\n".join(itertools.islice(difflib.unified_diff(
        a, b, fromfile=SELF, tofile=other, lineterm="", n=1), 60))
    pytest.fail(
        f"{SELF} and {other} copies of services/benchmarks.py have drifted."
        f"\n\n{diff}\n\nPort the change to both copies, or add a genuinely "
        "local difference to LOCAL in this file with a comment saying why."
    )
