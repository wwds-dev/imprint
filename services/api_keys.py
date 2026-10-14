"""Provider credentials: what the app reads, where it lives, and how to change it.

Until 2026-10-11 the only way to give Imprint a key was to edit the `.env` file
by hand — the one thing README §1's "a full Settings panel … without touching
any file" did not cover. The readiness-gate walk on the 9th then found that
the file held three rejected keys, which nothing in the app could have shown.
Settings → API keys now does it: paste, Test, Save, and the running window
picks the keys up without a restart.

This module is the Qt-free half. It owns:

- `CREDENTIALS`: the one list of every name the code reads, grouped for the
  page. `tests/test_env_template.py` holds it to the code — a module that
  starts reading a new secret fails the suite until the name is here.
- The file: the same `.env` `main.py` loads (`runtime_paths.user_data_base()`),
  rewritten in place so comments and unknown lines survive, created from
  `.env.example` when absent, kept at 0600, written atomically.
- The process: `apply()` puts the saved values into `os.environ`, which is
  what every client wrapper reads when the window rebuilds them.
- The probe: one metadata call per provider, the live one — `list_models()`
  swallows every error and returns KNOWN_MODELS, which would make a revoked
  key read OK. `scripts/check_keys.py` uses this same function.

Nothing here logs, prints or returns a key except to the caller that asked
for the file's values.
"""

from __future__ import annotations

import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from services.runtime_paths import resource_base, user_data_base


@dataclass(frozen=True)
class Credential:
    name: str            # the environment variable the code reads
    label: str           # what the page calls it
    group: str           # which card it sits in
    help: str            # one line: what it unlocks, where to get it
    secret: bool = True  # password echo and never shown; False for hosts/usernames
    probe: str | None = None   # key into PROBES, or None for presence-only
    aliases: tuple[str, ...] = ()  # other names the code accepts for the same value


MODEL = "Model providers"
MEDIA = "Images, video and voice"
ENDPOINTS = "Endpoints (optional)"
PRESS = "Press publishing data"
HERALD = "Herald publishing"
GROUPS = (MODEL, MEDIA, ENDPOINTS, PRESS, HERALD)

CREDENTIALS: tuple[Credential, ...] = (
    Credential("OPENAI_API_KEY", "OpenAI", MODEL,
               "Chat, GPT Image for Stamp and Reel's scenes, and Booth's OpenAI TTS narration. "
               "platform.openai.com → API keys.", probe="openai"),
    Credential("ANTHROPIC_API_KEY", "Anthropic", MODEL,
               "Claude for every text agent. console.anthropic.com → API keys.", probe="anthropic"),
    Credential("GOOGLE_API_KEY", "Gemini", MODEL,
               "Gemini text, Nano Banana images, Veo video and Booth's Gemini TTS route. "
               "aistudio.google.com → Get API key. (GEMINI_API_KEY is accepted too.)",
               probe="gemini", aliases=("GEMINI_API_KEY",)),
    Credential("DEEPSEEK_API_KEY", "DeepSeek", MODEL,
               "platform.deepseek.com → API keys.", probe="deepseek"),
    Credential("KIMI_API_KEY", "Kimi (Moonshot)", MODEL,
               "platform.moonshot.ai → API keys.", probe="kimi"),
    Credential("DASHSCOPE_API_KEY", "Qwen (Alibaba Model Studio)", MODEL,
               "Qwen text and images, Wan video. bailian.console.alibabacloud.com.", probe="qwen"),

    Credential("HF_API_KEY_ID", "Higgsfield key ID", MEDIA,
               "Muse's teasers and Reel's Higgsfield route. A key ID + secret pair, not a bearer token. "
               "cloud.higgsfield.ai.", aliases=("HIGGSFIELD_API_KEY_ID",)),
    Credential("HF_API_KEY_SECRET", "Higgsfield key secret", MEDIA,
               "The second half of the Higgsfield pair.", aliases=("HIGGSFIELD_API_KEY_SECRET",)),
    Credential("ELEVENLABS_API_KEY", "ElevenLabs", MEDIA,
               "Booth's ElevenLabs narration route, and the paid voice in Press's Shorts tab. "
               "elevenlabs.io → API keys."),

    Credential("DASHSCOPE_WORKSPACE_ID", "Qwen workspace ID", ENDPOINTS,
               "Optional. Your Alibaba Model Studio workspace ID, e.g. ws1 (not a web address). With it, "
               "Qwen chat uses your workspace host, which Alibaba recommends. Leave blank and the standard "
               "international host is used; it still works. Video is not affected.",
               secret=False),
    Credential("DASHSCOPE_BASE_URL", "Qwen chat endpoint", ENDPOINTS,
               "Leave blank for the standard international host, which still works, or set your "
               "workspace host: https://<WorkspaceId>.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1. "
               "If filled, this overrides the workspace ID.",
               secret=False),
    Credential("DASHSCOPE_VIDEO_BASE_URL", "Wan video endpoint", ENDPOINTS,
               "Leave blank for the default. A workspace host (https://<WorkspaceId>.ap-southeast-1.maas.aliyuncs.com/api/v1) is not yet confirmed to serve Wan video",
               secret=False),

    Credential("PUBLISHDRIVE_API_KEY", "PublishDrive", PRESS,
               "Sales and catalogue data for Press's Overview. Exports, KDP CSV import and the Submission "
               "Ledger work without it. The first Refresh Data is the test."),

    Credential("REDDIT_CLIENT_ID", "Reddit client ID", HERALD,
               "A script-type app at reddit.com/prefs/apps. Only needed to post; drafting needs none of these."),
    Credential("REDDIT_CLIENT_SECRET", "Reddit client secret", HERALD, "From the same app page."),
    Credential("REDDIT_USERNAME", "Reddit username", HERALD, "The account the app posts as.", secret=False),
    Credential("REDDIT_PASSWORD", "Reddit password", HERALD,
               "The script flow keeps this in the file; anyone who can read it can act as your account."),
    Credential("PINTEREST_ACCESS_TOKEN", "Pinterest access token", HERALD,
               "A business account's token with pins:write and boards:read. developers.pinterest.com."),
)

BY_NAME = {c.name: c for c in CREDENTIALS}
#: Every name the file or the environment may carry for a credential.
ALL_NAMES = tuple(n for c in CREDENTIALS for n in (c.name, *c.aliases))


def by_group() -> dict[str, list[Credential]]:
    out: dict[str, list[Credential]] = {g: [] for g in GROUPS}
    for cred in CREDENTIALS:
        out[cred.group].append(cred)
    return out


# ── the file ─────────────────────────────────────────────────────────────────

def env_path() -> Path:
    """The .env main.py loads: project root in a checkout, Application Support when frozen."""
    return user_data_base() / ".env"


def template_path() -> Path:
    return resource_base() / ".env.example"


_LINE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$")


def _unquote(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        inner = raw[1:-1]
        if raw[0] == '"':                      # undo what _quote_if_needed wrote
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    # an unquoted value ends at an inline comment
    if " #" in raw:
        raw = raw.split(" #", 1)[0].rstrip()
    return raw


def read_values(path: Path | None = None) -> dict[str, str]:
    """NAME → value for every assignment in the file. Missing file → {}."""
    path = path or env_path()
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _LINE.match(line)
        if match:
            values[match.group(1)] = _unquote(match.group(2))
    return values


def _quote_if_needed(value: str) -> str:
    if value == "" or re.fullmatch(r"[A-Za-z0-9_./:@+=,%-]*", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


# Everything str.splitlines() ends a line at, which is how this module reads
# the file back: \r and \n, and the rarer ones a paste can carry too.
_LINE_BREAKS = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"


def is_one_line(value: str) -> bool:
    """True when `value` has no line break the file reader would split on."""
    return not any(ch in value for ch in _LINE_BREAKS)


def write_values(updates: dict[str, str], path: Path | None = None) -> list[str]:
    """Set each NAME=value in the file, preserving every other line.

    A name already in the file is replaced where it is (first occurrence;
    later duplicates are dropped so the file cannot say two things). A name
    not in the file is appended under one header. A missing file is created
    from `.env.example` so the comments come along. The result is written to
    a temp file beside the target and moved into place, then chmod 0600.
    Returns the names whose stored value changed.

    A value with a line break raises ValueError (naming the variable, never
    the value) before the file is touched: pasted "ws1\\nDASHSCOPE_BASE_URL=…"
    would otherwise read back as a second, real assignment.
    """
    multiline = [name for name, value in updates.items() if not is_one_line(value)]
    if multiline:
        raise ValueError(f"{', '.join(multiline)}: one line only")
    path = path or env_path()
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    elif template_path().exists():
        lines = template_path().read_text(encoding="utf-8").splitlines()
    else:
        lines = ["# Imprint — API keys", ""]

    before = read_values(path) if path.exists() else {}
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        match = _LINE.match(line) if line.strip() and not line.lstrip().startswith("#") else None
        name = match.group(1) if match else None
        if name in updates:
            if name in seen:
                continue                       # drop a later duplicate
            seen.add(name)
            out.append(f"{name}={_quote_if_needed(updates[name])}")
        else:
            out.append(line)
    missing = [n for n in updates if n not in seen]
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.append("# ── Added from Settings → API keys ─────────────────────────────────────────")
        out += [f"{n}={_quote_if_needed(updates[n])}" for n in missing]

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".env.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(out) + "\n")
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return [n for n, v in updates.items() if before.get(n, "") != v]


# ── the process ──────────────────────────────────────────────────────────────

def apply(updates: dict[str, str]) -> None:
    """Make the saved values the running process's values. An empty value
    removes the variable, and removes the aliases too, so a cleared Gemini key
    cannot live on as GEMINI_API_KEY."""
    for name, value in updates.items():
        names = (name, *BY_NAME[name].aliases) if name in BY_NAME else (name,)
        if value:
            os.environ[name] = value
            for alias in names[1:]:
                os.environ.pop(alias, None)
        else:
            for n in names:
                os.environ.pop(n, None)


def effective(name: str) -> str:
    """The value the app is using right now, under any accepted name."""
    cred = BY_NAME.get(name)
    for n in ((name, *cred.aliases) if cred else (name,)):
        value = os.environ.get(n, "")
        if value:
            return value
    return ""


def overridden_by_environment(name: str, file_values: dict[str, str] | None = None) -> bool:
    """True when the shell gave this process a value the file does not hold.
    load_dotenv never overrides a variable that is already set, so a key
    saved in the file is ignored at the next launch while the shell sets it."""
    file_values = read_values() if file_values is None else file_values
    cred = BY_NAME.get(name)
    in_file = next((file_values[n] for n in ((name, *cred.aliases) if cred else (name,))
                    if file_values.get(n)), "")
    live = effective(name)
    return bool(live) and live != in_file


# ── the probe ────────────────────────────────────────────────────────────────

def _client(kind: str):
    if kind == "anthropic":
        from services.anthropic_client import AnthropicClientWrapper as C
    elif kind == "openai":
        from services.openai_client import OpenAIClientWrapper as C
    elif kind == "gemini":
        from services.gemini_client import GeminiClientWrapper as C
    elif kind == "deepseek":
        from services.deepseek_client import DeepSeekClientWrapper as C
    elif kind == "kimi":
        from services.kimi_client import KimiClientWrapper as C
    elif kind == "qwen":
        from services.qwen_client import QwenClientWrapper as C
    else:
        raise KeyError(kind)
    return C()


PROBES: tuple[str, ...] = ("anthropic", "openai", "gemini", "deepseek", "kimi", "qwen", "ollama")


def _names_for_probe(kind: str) -> tuple[str, ...]:
    return tuple(n for c in CREDENTIALS if c.probe == kind for n in (c.name, *c.aliases))


def prepare_probe(kind: str, values: dict[str, str] | None = None):
    """Main-thread half of a probe: build the client with `values` in place.

    The wrappers read their key from the environment at construction, so the
    typed value is swapped in only for that moment and restored before this
    returns — never while another thread might be reading it. Returns
    (client, note); client is None when there is nothing to call and the note
    says why ("not set", "no probe").
    """
    # Main thread only; the swap is briefly process-wide: a client built elsewhere now sees it.
    saved = {n: os.environ.get(n) for n in (values or {})}
    try:
        for name, value in (values or {}).items():
            if value:
                os.environ[name] = value
            else:
                os.environ.pop(name, None)
        if kind == "ollama":
            from services.ollama_client import OllamaClient
            return OllamaClient(), ""
        if kind not in PROBES:
            return None, "no probe"
        if not any(os.environ.get(n) for n in _names_for_probe(kind)):
            return None, "not set"
        return _client(kind), ""
    finally:
        for name, old in saved.items():
            if old is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old


def run_probe(kind: str, client) -> tuple[bool, str]:
    """Any-thread half: the one metadata call. Costs and bills nothing.

    The live call, not `list_models()`, which falls back to KNOWN_MODELS on
    any error and would make a revoked key read as reachable. The note is the
    exception type and the first line of its message, cut short, because a
    provider's error can echo the request.
    """
    try:
        if kind == "ollama":
            models = client.list_models()
            return bool(models), (f"{len(models)} model(s) pulled"
                                  if models else "daemon up but nothing pulled")
        models = client.list_models_live()
        return bool(models), f"{len(models)} model(s)"
    except Exception as exc:                       # noqa: BLE001 — the point is to report it
        if kind == "qwen" and getattr(exc, "status_code", None) == 401:
            from services.qwen_client import workspace_auth_hint
            hint = workspace_auth_hint(getattr(client, "base_url", ""))
            if hint:
                return False, hint
        reason = str(exc).splitlines()[0][:90] if str(exc) else ""
        return False, f"{type(exc).__name__}: {reason}" if reason else type(exc).__name__


def probe(kind: str, values: dict[str, str] | None = None) -> tuple[bool, str]:
    """Both halves in one call, for the command line (`scripts/check_keys.py`)
    and tests. Settings uses the halves separately so the network call can
    leave the UI thread."""
    client, note = prepare_probe(kind, values)
    if client is None:
        return False, note
    return run_probe(kind, client)
