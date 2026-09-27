"""Names that must never come back into the repository.

A venture that was moved out into its own, separate app on 2026-09-27 is not
to be referenced anywhere in Imprint — not in code, docs, tests, fixtures or
file names. The name is assembled at runtime so this file does not itself
contain it.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETIRED = ("only" + "fans",)
# Its workspace label, matched case-sensitively so "a group of agents" is fine.
RETIRED_LABEL = "OF" + " Agent"


def _tracked() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    return [name for name in result.stdout.split("\0") if name]


def test_retired_names_appear_in_no_tracked_path_or_file():
    hits = []
    for name in _tracked():
        if any(word in name.lower() for word in RETIRED):
            hits.append(f"{name} (path)")
            continue
        path = ROOT / name
        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or since-deleted
        for number, row in enumerate(original.splitlines(), 1):
            if RETIRED_LABEL in row or any(word in row.lower() for word in RETIRED):
                hits.append(f"{name}:{number}")
    assert not hits, "retired names found:\n" + "\n".join(hits)
