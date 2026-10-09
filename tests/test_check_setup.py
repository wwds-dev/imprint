"""`scripts/check_setup.py` says what is missing instead of letting a panel find out.

Pure: every check takes its collaborators (which / run / platform / version)
as arguments, so these tests run on a machine with none of the tools and
never touch the Ollama daemon. Run with:  pytest tests/test_check_setup.py -v
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_setup", ROOT / "scripts" / "check_setup.py")
check_setup = importlib.util.module_from_spec(_spec)
# @dataclass resolves the class's module through sys.modules, so a spec-loaded
# module has to be registered before it executes.
sys.modules["check_setup"] = check_setup
_spec.loader.exec_module(check_setup)


def _which(present: set[str]):
    return lambda name: f"/usr/bin/{name}" if name in present else None


def _run_ok(argv, **kwargs):
    return subprocess.CompletedProcess(argv, 0, stdout=f"{argv[0]} version 9.9", stderr="")


ALL_TOOLS = {"ffmpeg", "ffprobe", "ebook-convert", "say"}


def _all_good(tmp_path, **overrides):
    kwargs = dict(which=_which(ALL_TOOLS), run=_run_ok, system="Darwin",
                  version_info=(3, 12, 1), list_models=lambda: ["llama3.1:8b"],
                  data_dir=tmp_path)
    kwargs.update(overrides)
    return check_setup.run_checks(**kwargs)


def test_a_complete_machine_passes_every_row(tmp_path):
    checks = _all_good(tmp_path)
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert check_setup.required_failures(checks) == []


def test_missing_ffmpeg_is_required_and_names_who_needs_it(tmp_path):
    checks = _all_good(tmp_path, which=_which(ALL_TOOLS - {"ffmpeg"}))
    failed = check_setup.required_failures(checks)
    assert [c.label for c in failed] == ["ffmpeg"]
    assert "Booth" in failed[0].note and "Shorts" in failed[0].note


def test_missing_calibre_degrades_but_does_not_fail(tmp_path):
    checks = _all_good(tmp_path, which=_which(ALL_TOOLS - {"ebook-convert"}))
    calibre = next(c for c in checks if c.label.startswith("Calibre"))
    assert not calibre.ok and not calibre.required
    assert "MOBI" in calibre.note and "AZW3" in calibre.note
    assert check_setup.required_failures(checks) == []


def test_python_below_3_11_fails(tmp_path):
    checks = _all_good(tmp_path, version_info=(3, 10, 12))
    py = checks[0]
    assert py.label == "Python" and not py.ok and py.required
    assert "3.11+" in py.note


def test_ollama_daemon_down_is_optional_but_blocks_the_free_pass(tmp_path):
    def down():
        raise ConnectionError("refused")
    checks = _all_good(tmp_path, list_models=down)
    ollama = next(c for c in checks if c.label == "Ollama")
    assert not ollama.ok and not ollama.required
    assert "FREE" in ollama.note


def test_ollama_with_nothing_pulled_says_what_to_pull(tmp_path):
    checks = _all_good(tmp_path, list_models=lambda: [])
    ollama = next(c for c in checks if c.label == "Ollama")
    assert not ollama.ok and "pull" in ollama.note


def test_ollama_with_only_reasoning_models_warns_for_uat(tmp_path):
    checks = _all_good(tmp_path, list_models=lambda: ["deepseek-r1:8b", "deepseek-r1:14b"])
    ollama = next(c for c in checks if c.label == "Ollama")
    assert ollama.ok and "instruct" in ollama.note


def test_say_is_only_expected_on_macos(tmp_path):
    checks = _all_good(tmp_path, system="Linux", which=_which(ALL_TOOLS - {"say"}))
    say = next(c for c in checks if c.label.startswith("say"))
    assert not say.ok and not say.required and "espeak" in say.note


def test_unwritable_data_dir_is_required(tmp_path):
    missing = tmp_path / "does-not-exist" / "deeper"
    check = check_setup.check_data_dir(missing)
    assert not check.ok and check.required


def test_data_dir_inside_a_bundle_fails(tmp_path):
    bundle = tmp_path / "Imprint.app" / "Contents" / "Resources"
    bundle.mkdir(parents=True)
    check = check_setup.check_data_dir(bundle)
    assert not check.ok and "INSIDE" in check.note


def test_a_tool_whose_version_call_blows_up_is_still_present(tmp_path):
    def exploding(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 10)
    check = check_setup.check_tool("ffmpeg", "ffmpeg", "x", required=True,
                                   which=_which({"ffmpeg"}), run=exploding)
    assert check.ok and "version unknown" in check.note


def test_exit_code_follows_required_failures(tmp_path, monkeypatch, capsys):
    # Build both result lists before patching: _all_good calls run_checks.
    broken = _all_good(tmp_path, which=_which(ALL_TOOLS - {"ffprobe"}))
    healthy = _all_good(tmp_path)
    monkeypatch.setattr(check_setup, "run_checks", lambda **kw: broken)
    assert check_setup.main() == 1
    assert "FAIL" in capsys.readouterr().out
    monkeypatch.setattr(check_setup, "run_checks", lambda **kw: healthy)
    assert check_setup.main() == 0
    assert "check_keys.py" in capsys.readouterr().out
