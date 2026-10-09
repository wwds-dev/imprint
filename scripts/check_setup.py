#!/usr/bin/env python3
"""What this machine has, before a hand-test session or a first real run.

    .venv/bin/python scripts/check_setup.py

`scripts/check_keys.py` answers "which providers will accept my key". This
answers the question underneath it: can the app run at all here, and which
features will quietly be missing. Imprint leans on five things outside Python,
and until 2026-10-09 nothing checked for any of them — Booth, Reel and Press's
Shorts each failed in their own way when `ffmpeg` was absent, and MOBI/AZW3
books simply did not convert without Calibre (readiness audit, gate item D).

Two kinds of row. **Required** means the app or a whole workspace does not work
without it, and the script exits 1. **Optional** means one feature degrades or
is unavailable, and the row says which; the exit code is unaffected.

Nothing here contacts a provider or prints a key.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MIN_PYTHON = (3, 11)


@dataclass(frozen=True)
class Check:
    label: str
    ok: bool
    note: str
    required: bool


# ── individual checks (each takes its collaborators as arguments so a test can
# run them without the binaries, and so a missing tool is a result, not a crash)

def check_python(version_info=sys.version_info) -> Check:
    have = f"{version_info[0]}.{version_info[1]}"
    ok = tuple(version_info[:2]) >= MIN_PYTHON
    return Check("Python", ok,
                 f"{have}" + ("" if ok else f" — needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+"),
                 required=True)


def _first_line(run: Callable, argv: list[str]) -> str:
    try:
        result = run(argv, capture_output=True, text=True, timeout=10)
    except Exception as exc:                       # noqa: BLE001 — report, don't crash
        return f"present, version unknown ({type(exc).__name__})"
    text = (result.stdout or result.stderr or "").strip().splitlines()
    return text[0][:60] if text else "present"


def check_tool(name: str, label: str, needed_by: str, *, required: bool,
               version_argv: list[str] | None = None,
               which: Callable = shutil.which, run: Callable = subprocess.run) -> Check:
    path = which(name)
    if not path:
        return Check(label, False, f"not found — {needed_by}", required)
    note = _first_line(run, version_argv or [name, "-version"])
    return Check(label, True, note, required)


def check_say(*, system: str = platform.system(), which: Callable = shutil.which) -> Check:
    if system != "Darwin":
        return Check("say (on-device voice)", False,
                     f"not macOS ({system}) — Shorts' free voice needs espeak here",
                     required=False)
    return check_tool("say", "say (on-device voice)",
                      "Press's Shorts free narrator is unavailable",
                      required=False, version_argv=["say", "-v", "?"], which=which,
                      run=lambda *a, **k: subprocess.CompletedProcess(a, 0, "present", ""))


def check_ollama(list_models: Callable[[], list[str]] | None = None) -> Check:
    """Required for the FREE pass and for Local-only mode; the app runs without it."""
    if list_models is None:
        from services.ollama_client import OllamaClient
        list_models = OllamaClient().list_models
    try:
        models = list(list_models())
    except Exception as exc:                       # noqa: BLE001
        return Check("Ollama", False,
                     f"daemon not reachable ({type(exc).__name__}) — no free local "
                     "models; the FREE UAT pass cannot run", required=False)
    if not models:
        return Check("Ollama", False,
                     "daemon up but nothing pulled — `ollama pull llama3.1:8b`",
                     required=False)
    reasoning_only = all("deepseek-r1" in m or "r1" == m.split(":")[0] for m in models)
    note = f"{len(models)} model(s) pulled"
    if reasoning_only:
        note += " — all reasoning models; pull a general instruct model for UAT"
    return Check("Ollama", True, note, required=False)


def check_data_dir(base: Path | None = None) -> Check:
    if base is None:
        from services.runtime_paths import user_data_base
        base = user_data_base()
    try:
        probe = base / ".setup-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check("Data directory", False, f"{base} is not writable ({exc.strerror})",
                     required=True)
    inside_bundle = ".app/Contents/" in str(base)
    return Check("Data directory", not inside_bundle,
                 f"{base}" + (" — INSIDE the bundle" if inside_bundle else ""),
                 required=True)


def run_checks(*, which: Callable = shutil.which, run: Callable = subprocess.run,
               system: str = platform.system(), version_info=sys.version_info,
               list_models: Callable[[], list[str]] | None = None,
               data_dir: Path | None = None) -> list[Check]:
    return [
        check_python(version_info),
        check_data_dir(data_dir),
        check_tool("ffmpeg", "ffmpeg", "Booth, Reel and Shorts cannot render",
                   required=True, which=which, run=run),
        check_tool("ffprobe", "ffprobe", "Booth cannot read audio lengths",
                   required=True, which=which, run=run),
        check_tool("ebook-convert", "Calibre (ebook-convert)",
                   "MOBI and AZW3 books will not convert in Booth",
                   required=False, version_argv=["ebook-convert", "--version"],
                   which=which, run=run),
        check_say(system=system, which=which),
        check_ollama(list_models),
    ]


def required_failures(checks: list[Check]) -> list[Check]:
    return [c for c in checks if c.required and not c.ok]


def main() -> int:
    checks = run_checks()
    print("Imprint setup check\n")
    for c in checks:
        mark = "OK" if c.ok else ("FAIL" if c.required else "—")
        print(f"  {mark:4} {c.label:26} {c.note}")
    failed = required_failures(checks)
    if failed:
        print(f"\n  {len(failed)} required item(s) missing — the app will not run "
              "correctly until they are installed.")
    else:
        print("\n  Everything required is present. Next: scripts/check_keys.py")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
