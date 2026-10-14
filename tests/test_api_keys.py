"""Settings → API keys: the file, the process, and the one list of names.

Qt-free. Every test writes to a tmp_path .env; `services.api_keys.env_path`
is monkeypatched so nothing here can touch the checkout's own file, and the
conftest has already emptied every credential in the environment.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

import pytest

from services import api_keys

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.setattr(api_keys, "env_path", lambda: path)
    return path


# ── the spec ─────────────────────────────────────────────────────────────────

def test_every_credential_has_a_group_the_page_knows():
    assert set(c.group for c in api_keys.CREDENTIALS) <= set(api_keys.GROUPS)
    assert len({c.name for c in api_keys.CREDENTIALS}) == len(api_keys.CREDENTIALS)


def test_every_probe_names_a_real_client():
    for cred in api_keys.CREDENTIALS:
        if cred.probe:
            assert cred.probe in api_keys.PROBES
            assert api_keys._client(cred.probe) is not None


def test_spec_covers_every_secret_the_code_reads():
    """The page is only complete while it names everything a module can read."""
    secret = re.compile(r"^[A-Z0-9_]*(API_KEY|KEY_ID|KEY_SECRET|ACCESS_TOKEN|PASSWORD"
                        r"|CLIENT_ID|CLIENT_SECRET|TOKEN)$")
    read: set[str] = set()
    for folder in ("services", "providers", "agents"):
        for path in (ROOT / folder).rglob("*.py"):
            if "__pycache__" in path.parts or path.parts[-2] == "avatar":
                continue
            read |= set(re.findall(r"os\.(?:getenv|environ\.get)\(\s*[\"']([A-Z0-9_]+)[\"']",
                                   path.read_text(encoding="utf-8")))
    read |= set(re.findall(r"os\.(?:getenv|environ\.get)\(\s*[\"']([A-Z0-9_]+)[\"']",
                           (ROOT / "main.py").read_text(encoding="utf-8")))
    secrets = {n for n in read if secret.match(n)}
    missing = sorted(secrets - set(api_keys.ALL_NAMES))
    assert not missing, f"read by the code but not on the API keys page: {missing}"


# ── the file ─────────────────────────────────────────────────────────────────

def test_write_preserves_comments_and_replaces_in_place(env_file):
    env_file.write_text("# keys\nOPENAI_API_KEY=old\n\n# herald\nREDDIT_USERNAME=me\n", encoding="utf-8")
    changed = api_keys.write_values({"OPENAI_API_KEY": "sk-new", "REDDIT_USERNAME": "me"}, env_file)
    text = env_file.read_text(encoding="utf-8")
    assert text.splitlines() == ["# keys", "OPENAI_API_KEY=sk-new", "", "# herald", "REDDIT_USERNAME=me"]
    assert changed == ["OPENAI_API_KEY"], "an unchanged value is not reported as changed"


def test_write_appends_names_the_file_lacks_under_one_header(env_file):
    env_file.write_text("OPENAI_API_KEY=\n", encoding="utf-8")
    api_keys.write_values({"KIMI_API_KEY": "k1", "DEEPSEEK_API_KEY": "d1"}, env_file)
    lines = env_file.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "OPENAI_API_KEY="
    assert any(line.startswith("# ── Added from Settings") for line in lines)
    assert "KIMI_API_KEY=k1" in lines and "DEEPSEEK_API_KEY=d1" in lines
    assert api_keys.read_values(env_file) == {"OPENAI_API_KEY": "", "KIMI_API_KEY": "k1",
                                              "DEEPSEEK_API_KEY": "d1"}


def test_a_missing_file_is_created_from_the_template(env_file, monkeypatch):
    template = env_file.parent / "example"
    template.write_text("# Imprint — API keys\nOPENAI_API_KEY=\nANTHROPIC_API_KEY=\n", encoding="utf-8")
    monkeypatch.setattr(api_keys, "template_path", lambda: template)
    api_keys.write_values({"ANTHROPIC_API_KEY": "a1"}, env_file)
    assert env_file.read_text(encoding="utf-8").splitlines() == [
        "# Imprint — API keys", "OPENAI_API_KEY=", "ANTHROPIC_API_KEY=a1"]


def test_the_file_is_owner_only(env_file):
    api_keys.write_values({"OPENAI_API_KEY": "x"}, env_file)
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert not list(env_file.parent.glob(".env.*")), "no temp file left beside it"


def test_duplicates_collapse_to_one_line(env_file):
    env_file.write_text("OPENAI_API_KEY=a\nOPENAI_API_KEY=b\n", encoding="utf-8")
    api_keys.write_values({"OPENAI_API_KEY": "c"}, env_file)
    assert env_file.read_text(encoding="utf-8").splitlines() == ["OPENAI_API_KEY=c"]


def test_values_with_spaces_or_hashes_are_quoted_and_read_back(env_file):
    odd = 'pa ss#word "quoted"'
    api_keys.write_values({"REDDIT_PASSWORD": odd}, env_file)
    assert api_keys.read_values(env_file)["REDDIT_PASSWORD"] == odd


def test_read_understands_export_quotes_and_inline_comments(env_file):
    env_file.write_text('export OPENAI_API_KEY="sk-1"\nKIMI_API_KEY=\'k\'\nDEEPSEEK_API_KEY=d # note\n',
                        encoding="utf-8")
    assert api_keys.read_values(env_file) == {"OPENAI_API_KEY": "sk-1", "KIMI_API_KEY": "k",
                                              "DEEPSEEK_API_KEY": "d"}


def test_clearing_a_value_leaves_the_name_empty_not_deleted(env_file):
    env_file.write_text("OPENAI_API_KEY=sk\n", encoding="utf-8")
    api_keys.write_values({"OPENAI_API_KEY": ""}, env_file)
    assert env_file.read_text(encoding="utf-8").splitlines() == ["OPENAI_API_KEY="]


@pytest.mark.parametrize("brk", ["\n", "\r", "\r\n", "\u2028"])
def test_a_value_with_a_line_break_is_refused_and_the_file_is_unchanged(env_file, brk):
    """A two-line paste would read back as a second, real assignment."""
    env_file.write_text("# keys\nDASHSCOPE_WORKSPACE_ID=ws1\n", encoding="utf-8")
    before = env_file.read_bytes()
    pasted = f"ws2{brk}DASHSCOPE_BASE_URL=https://evil.example/v1"
    with pytest.raises(ValueError) as refused:
        api_keys.write_values({"OPENAI_API_KEY": "fine", "DASHSCOPE_WORKSPACE_ID": pasted}, env_file)
    assert "DASHSCOPE_WORKSPACE_ID" in str(refused.value) and "one line only" in str(refused.value)
    assert "evil" not in str(refused.value), "the value is never echoed"
    assert env_file.read_bytes() == before
    assert not list(env_file.parent.glob(".env.*")), "no temp file left beside it"


def test_every_character_the_reader_splits_on_counts_as_a_line_break():
    """read_values uses str.splitlines(), so the check must refuse all of its breaks."""
    breaks = [chr(c) for c in range(0x110000) if len(f"a{chr(c)}b".splitlines()) > 1]
    assert "\n" in breaks and "\u2028" in breaks
    assert [ch for ch in breaks if api_keys.is_one_line(f"a{ch}b")] == []
    assert api_keys.is_one_line("ws1") and api_keys.is_one_line("") and api_keys.is_one_line("a b\tc")


# ── the process ──────────────────────────────────────────────────────────────

def test_apply_sets_and_clears_including_aliases(monkeypatch):
    # apply() pops a cleared name; recording it first puts the conftest's blank back
    monkeypatch.setenv("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
    monkeypatch.setenv("GEMINI_API_KEY", "old-alias")
    api_keys.apply({"GOOGLE_API_KEY": "g1"})
    assert os.environ["GOOGLE_API_KEY"] == "g1"
    assert "GEMINI_API_KEY" not in os.environ, "the alias must not outlive the new value"
    api_keys.apply({"GOOGLE_API_KEY": ""})
    assert "GOOGLE_API_KEY" not in os.environ


def test_effective_reads_either_accepted_name(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "via-alias")
    assert api_keys.effective("GOOGLE_API_KEY") == "via-alias"


def test_overridden_by_environment_means_the_shell_wins_at_launch(env_file, monkeypatch):
    env_file.write_text("OPENAI_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "from-shell")
    assert api_keys.overridden_by_environment("OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "from-file")
    assert not api_keys.overridden_by_environment("OPENAI_API_KEY")
    monkeypatch.delenv("OPENAI_API_KEY")
    assert not api_keys.overridden_by_environment("OPENAI_API_KEY")


# ── the probe ────────────────────────────────────────────────────────────────

def test_probe_reports_a_missing_key_as_not_set_not_ok(monkeypatch):
    """The wrappers' live call answers KNOWN_MODELS with no key — right for
    the model-watch, wrong for a reachability check."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert api_keys.probe("deepseek") == (False, "not set")


def test_probe_tests_the_typed_value_and_puts_the_environment_back(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "saved-key")
    seen = []

    class Fake:
        def __init__(self):
            seen.append(os.environ.get("ANTHROPIC_API_KEY"))
        def list_models_live(self):
            return ["m"]

    monkeypatch.setattr(api_keys, "_client", lambda kind: Fake())
    assert api_keys.probe("anthropic", {"ANTHROPIC_API_KEY": "typed-key"}) == (True, "1 model(s)")
    assert seen == ["typed-key"], "the probe must see the value under test"
    assert os.environ["ANTHROPIC_API_KEY"] == "saved-key", "and leave the process as it was"
    assert api_keys.probe("anthropic", {"ANTHROPIC_API_KEY": ""}) == (False, "not set")
    assert os.environ["ANTHROPIC_API_KEY"] == "saved-key"


def test_probe_uses_the_live_call_not_the_fallback(monkeypatch):
    calls = []

    class Fake:
        def list_models(self):
            calls.append("fallback"); return ["known"]
        def list_models_live(self):
            calls.append("live"); raise RuntimeError("401 bad key")

    monkeypatch.setattr(api_keys, "_client", lambda kind: Fake())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "some-key")
    ok, note = api_keys.probe("anthropic")
    assert not ok and "401" in note
    assert calls == ["live"]


def test_probe_never_echoes_more_than_one_short_line(monkeypatch):
    class Fake:
        def list_models_live(self):
            raise RuntimeError("line one with the request body sk-secret-" + "x" * 300 + "\nline two")

    monkeypatch.setattr(api_keys, "_client", lambda kind: Fake())
    monkeypatch.setenv("OPENAI_API_KEY", "some-key")
    ok, note = api_keys.probe("openai")
    assert not ok
    assert "\n" not in note and len(note) < 120


def test_unknown_probe_is_a_quiet_no(monkeypatch):
    assert api_keys.probe("elevenlabs") == (False, "no probe")
