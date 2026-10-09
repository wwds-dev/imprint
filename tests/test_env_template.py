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
CONFTEST = ROOT / "tests" / "conftest.py"

# Names that carry a secret, as opposed to a host or endpoint override. A
# missing endpoint override falls back to a working default; a missing secret
# means the provider cannot be used at all.
SECRET = re.compile(
    r"^[A-Z0-9_]*(API_KEY|KEY_ID|KEY_SECRET|ACCESS_TOKEN|PASSWORD"
    r"|CLIENT_ID|CLIENT_SECRET|TOKEN)$")


def _env_names(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    return set(re.findall(r"os\.(?:getenv|environ\.get)\(\s*[\"']([A-Z0-9_]+)[\"']",
                          source))


def _secret_names(path: Path) -> set[str]:
    return {name for name in _env_names(path) if SECRET.match(name)}


# Every module that reads a credential, wherever it lives. Each widening of
# this scan was forced by a miss: ElevenLabs sat under providers/ when the test
# looked only at services/*_client.py (2026-10-06), and PublishDrive's key was
# read by agents/manuscript/ and main.py while the scan stopped at providers/
# (found by the 2026-10-09 readiness audit — the key was in neither the
# template, the key checker nor conftest's scrub list). So: every Python file
# under the app's own packages plus main.py, filtered to the ones that read a
# secret, so the parametrize ids name only the files that matter.
_SCANNED = [
    ROOT / "main.py",
    *(ROOT / "services").rglob("*.py"),
    *(ROOT / "providers").rglob("*.py"),
    *(ROOT / "agents").rglob("*.py"),
]
CLIENTS = sorted(
    (p for p in _SCANNED if "__pycache__" not in p.parts and _secret_names(p)),
    key=lambda path: str(path.relative_to(ROOT)))

# `providers/avatar/` reads HEYGEN_API_KEY and SYNTHESIA_API_KEY but nothing
# outside that directory imports it — there is no avatar feature in the app, so
# the keys would configure nothing and belong in no template. Excluded rather
# than skipped silently, so that if the subsystem is ever wired up this list is
# where the omission shows. See TODO: wire it or remove it.
UNWIRED = {"heygen.py", "synthesia.py"}


def _declared() -> set[str]:
    text = TEMPLATE.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z0-9_]+)=", text, re.M))


# One credential under several names. The template names one per group; a
# secret outside every group has to appear under its own name.
ALIASES = (
    frozenset({"GEMINI_API_KEY", "GOOGLE_API_KEY"}),
    frozenset({"HF_API_KEY_ID", "HIGGSFIELD_API_KEY_ID"}),
    frozenset({"HF_API_KEY_SECRET", "HIGGSFIELD_API_KEY_SECRET"}),
)


def _satisfied(secret: str, declared: set[str]) -> bool:
    for group in ALIASES:
        if secret in group:
            return bool(group & declared)
    return secret in declared


@pytest.mark.parametrize("client", CLIENTS,
                         ids=lambda p: str(p.relative_to(ROOT)))
def test_every_provider_can_be_configured_from_the_template(client):
    """Every secret a module reads is in the template under one accepted name.

    "Every", not "any": the earlier form passed a module as soon as one of its
    secrets was declared, which is how `agents/manuscript/panel.py` — reading
    both ELEVENLABS_API_KEY and PUBLISHDRIVE_API_KEY — passed with the second
    one missing."""
    if client.name in UNWIRED:
        pytest.skip(f"{client.name} is not reachable from the app")
    secrets = _secret_names(client)
    declared = _declared()
    missing = sorted(s for s in secrets if not _satisfied(s, declared))
    assert not missing, (
        f"{client.relative_to(ROOT)} reads {missing} and .env.example declares "
        "no accepted name for them, so nothing in the template configures it")


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
        if client.name in UNWIRED:
            continue
        secrets = _secret_names(client)
        assert any(name in checker for name in secrets), (
            f"scripts/check_keys.py checks none of {sorted(secrets)}, so "
            f"{client.name} would read as configured when it is not")


def test_conftest_scrubs_every_secret_the_app_reads():
    """`tests/conftest.py` empties every credential before a test module can
    import `main` and its `load_dotenv()`. A secret the app reads that is not
    in that list is a secret a developer's `.env` can hand to the suite — the
    exact hole the list exists to close. Read off the code, like the template
    check, so adding a provider cannot leave the list behind."""
    source = CONFTEST.read_text(encoding="utf-8")
    match = re.search(r"_CREDENTIAL_ENV\s*=\s*\((.*?)\)\n", source, re.S)
    assert match, "tests/conftest.py no longer defines _CREDENTIAL_ENV"
    scrubbed = set(re.findall(r"[\"']([A-Z0-9_]+)[\"']", match.group(1)))
    read = set()
    for client in CLIENTS:
        read |= _secret_names(client)
    missing = sorted(read - scrubbed)
    assert not missing, (
        f"conftest._CREDENTIAL_ENV does not scrub {missing}; a developer .env "
        "holding one of them would reach the test suite")


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


def test_the_key_checker_imports_classes_that_exist_and_probes_live():
    """2026-10-09: the first run with a key in .env showed every keyed provider
    as FAIL — the probe imported AnthropicClient, GeminiClient, … which do not
    exist (the classes are *Wrapper). Import each name the checker uses, and
    make sure the probe is the live call: list_models() falls back to
    KNOWN_MODELS on any error, which would make a revoked key read OK."""
    import importlib

    checker = (ROOT / "scripts" / "check_keys.py").read_text(encoding="utf-8")
    pairs = re.findall(r"from (services\.\w+) import (\w+)", checker)
    assert pairs, "the checker imports no client at all"
    for module, name in pairs:
        assert hasattr(importlib.import_module(module), name), (
            f"scripts/check_keys.py imports {name} from {module}, which has no such name")
    assert "list_models_live()" in checker
    assert re.search(r"C\(\)\.list_models\(\)", checker) is None, (
        "the probe must not use list_models(), which hides a bad key behind KNOWN_MODELS")
