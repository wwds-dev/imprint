"""`.env.example` has to be enough to configure every provider.

It is the file a fresh checkout copies, so a credential missing from it is a
credential the user cannot find. That already happened once: Herald's publishing
keys were only in `agents/social/publishing.py` and the in-app guide, so the
template named no way to post at all (fixed 2026-10-06, pinned in
`test_social_onboarding.py`). This is the same check for the model providers,
read off the clients rather than from a second hardcoded list.

Several providers accept more than one name for the same credential — Gemini
takes `GEMINI_API_KEY` or `GOOGLE_API_KEY`, Higgsfield takes the `HF_` pair or
the `HIGGSFIELD_` pair. The template only needs to name one of each, and
listing every alias would make it harder to read, not easier.

Run with:  pytest tests/test_env_template.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".env.example"
# Every module that reads a credential, not just the chat clients: ElevenLabs
# lives under providers/ and was missing from the template precisely because an
# earlier version of this test looked only at services/*_client.py.
CLIENTS = sorted(
    [*(ROOT / "services").glob("*_client.py"),
     *(ROOT / "providers").rglob("*.py")],
    key=lambda path: path.name)

# Names that carry a secret, as opposed to a host or endpoint override. A
# missing endpoint override falls back to a working default; a missing secret
# means the provider cannot be used at all.
SECRET = re.compile(
    r"^[A-Z0-9_]*(API_KEY|KEY_ID|KEY_SECRET|ACCESS_TOKEN|PASSWORD"
    r"|CLIENT_ID|CLIENT_SECRET|TOKEN)$")

# Modules that read no credential of their own.
NO_CREDENTIAL = {"ollama_client.py", "mock.py", "base.py", "__init__.py",
                 "registry.py"}

# `providers/avatar/` reads HEYGEN_API_KEY and SYNTHESIA_API_KEY but nothing
# outside that directory imports it — there is no avatar feature in the app, so
# the keys would configure nothing and belong in no template. Excluded rather
# than skipped silently, so that if the subsystem is ever wired up this list is
# where the omission shows. See TODO: wire it or remove it.
UNWIRED = {"heygen.py", "synthesia.py"}


def _env_names(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    return set(re.findall(r"os\.(?:getenv|environ\.get)\(\s*[\"']([A-Z0-9_]+)[\"']",
                          source))


def _declared() -> set[str]:
    text = TEMPLATE.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z0-9_]+)=", text, re.M))


@pytest.mark.parametrize("client", CLIENTS, ids=lambda p: p.name)
def test_every_provider_can_be_configured_from_the_template(client):
    """At least one accepted name per client, not every alias."""
    if client.name in NO_CREDENTIAL:
        pytest.skip(f"{client.name} reads no credential")
    if client.name in UNWIRED:
        pytest.skip(f"{client.name} is not reachable from the app")
    secrets = {name for name in _env_names(client) if SECRET.match(name)}
    if not secrets:
        pytest.skip(f"{client.name} reads no credential")
    declared = _declared()
    assert secrets & declared, (
        f"{client.name} needs one of {sorted(secrets)} and .env.example "
        "declares none of them, so nothing in the template configures it")


def test_the_template_declares_no_value_for_any_secret():
    """A shipped template with a value in it is how a key reaches a commit.
    Endpoint and base-URL defaults are fine and are deliberately prefilled."""
    filled = []
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Z0-9_]+)=(.+)$", line)
        if match and SECRET.match(match.group(1)):
            filled.append(match.group(1))
    assert not filled, f".env.example ships a value for: {', '.join(filled)}"


def test_the_template_is_not_tracked_as_the_real_env():
    """`.env.example` is committed; `.env` must never be."""
    import subprocess

    result = subprocess.run(["git", "check-ignore", ".env"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, (
        ".env is not gitignored — a pasted key would be committable")


def test_the_key_checker_names_every_provider_the_app_has():
    """`scripts/check_keys.py` is what a user runs before a paid pass. If a
    provider is missing from it, the check passes while that provider is
    silently unconfigured."""
    checker = (ROOT / "scripts" / "check_keys.py").read_text(encoding="utf-8")
    for client in CLIENTS:
        if client.name in NO_CREDENTIAL or client.name in UNWIRED:
            continue
        secrets = {n for n in _env_names(client) if SECRET.match(n)}
        if not secrets:
            continue
        assert any(name in checker for name in secrets), (
            f"scripts/check_keys.py checks none of {sorted(secrets)}, so "
            f"{client.name} would read as configured when it is not")


def test_the_unwired_providers_are_still_unwired():
    """The exclusion above is only honest while it is true. If something starts
    importing providers/avatar, its keys become real configuration and have to
    reach `.env.example` and the key check like any other."""
    import subprocess

    result = subprocess.run(
        ["git", "grep", "-l", "-E", "providers\\.avatar|providers/avatar",
         "--", "*.py"],
        cwd=ROOT, capture_output=True, text=True)
    importers = [line for line in result.stdout.splitlines()
                 if line and not line.startswith("providers/avatar/")
                 and not line.startswith("tests/")]
    assert not importers, (
        "providers/avatar is now imported by "
        f"{importers} — remove it from UNWIRED and add its keys to "
        ".env.example and scripts/check_keys.py")
