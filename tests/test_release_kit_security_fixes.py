"""Security review fixes for one-click release slice 1
(docs/audit/one-click-release-security-engineer.md): S-1 proxies, S-2 URL
parser mismatch, S-3 `say` argument injection, S-4 default kit folder."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from services import local_endpoint, lmstudio_client, ollama_client
from services.release_kit import plan as kitplan

ROOT = Path(__file__).resolve().parent.parent
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
              "http_proxy", "https_proxy", "all_proxy")


# ── S-1: a proxy never carries a local request ───────────────────────────────

class _Local(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.end_headers()
        if self.path == "/api/chat":
            for frame in ({"message": {"content": "local"}}, {"done": True}):
                self.wfile.write(json.dumps(frame).encode() + b"\n")
        else:
            chunk = {"choices": [{"delta": {"content": "local"}}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")


@pytest.fixture
def local_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Local)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def dead_proxy(monkeypatch):
    """Every proxy variable points at a port nothing listens on, so a request
    that went through the proxy fails instead of reaching the server."""
    for name in PROXY_VARS:
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)


def test_ollama_stream_reaches_the_local_server_with_a_proxy_set(
        local_server, dead_proxy):
    stream = ollama_client.OllamaClient(local_server).stream_chat(
        "m", [{"role": "user", "content": "x"}], max_tokens=8192)
    assert "".join(stream) == "local"


def test_lm_studio_stream_reaches_the_local_server_with_a_proxy_set(
        local_server, dead_proxy):
    stream = local_endpoint.LocalLMStudioClient(local_server + "/v1").stream_chat(
        "m", [{"role": "user", "content": "x"}], max_tokens=8192)
    assert "".join(stream) == "local"


def test_without_no_proxies_the_same_request_would_go_to_the_proxy(dead_proxy):
    """The control for the two tests above: requests' own merge picks the
    environment proxy unless NO_PROXIES is passed."""
    import requests
    url = "http://127.0.0.1:11434/api/chat"
    session = requests.Session()
    picked = session.merge_environment_settings(url, {}, None, None, None)
    assert requests.utils.select_proxy(url, picked["proxies"])
    picked = session.merge_environment_settings(
        url, dict(local_endpoint.NO_PROXIES), None, None, None)
    assert requests.utils.select_proxy(
        url, {k: v for k, v in picked["proxies"].items() if v}) is None


@pytest.mark.parametrize("path", ["services/ollama_client.py",
                                  "services/local_endpoint.py"])
def test_every_local_client_request_passes_no_proxies(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and isinstance(node.func.value, ast.Name)
             and node.func.value.id == "requests"
             and node.func.attr in {"get", "post", "put", "delete", "request"}]
    assert calls
    for call in calls:
        kwargs = {k.arg: k.value for k in call.keywords}
        assert "proxies" in kwargs, f"{path}:{call.lineno} sends without proxies="
        assert ast.unparse(kwargs["proxies"]) == "NO_PROXIES"


# ── S-2: the host checked is the host dialled ────────────────────────────────

@pytest.mark.parametrize("value", [
    "http://evil.com\\@127.0.0.1:11434", "http://user@127.0.0.1:11434",
    "http://127.0.0.1@evil.com:11434", "http://127.0.0.%31:11434"])
def test_an_endpoint_whose_parsers_could_disagree_is_refused(monkeypatch, value):
    monkeypatch.setenv("OLLAMA_HOST", value)
    assert kitplan.endpoint_problem("ollama"), value
    assert kitplan.endpoint_problem("ollama", value)


@pytest.mark.parametrize("value", [
    "http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"])
def test_a_plain_loopback_endpoint_is_accepted(value):
    assert kitplan.endpoint_problem("ollama", value) == ""


def test_url_host_is_the_host_requests_dials():
    from urllib3.util import parse_url
    for url in ("http://evil.com\\@127.0.0.1:11434", "http://[::1]:11434",
                "http://127.0.0.1:1234/v1"):
        assert local_endpoint.url_host(url) == (parse_url(url).host or "").strip("[]")
    assert local_endpoint.url_host("http://evil.com\\@127.0.0.1:11434") == "evil.com"


# ── S-3: a quote that starts with "-" is text, never an option ───────────────

@pytest.mark.parametrize("engine", ["macos", "linux"])
@pytest.mark.parametrize("quote", ["-f ~/notes.txt and the forty",
                                   "-o/tmp/elsewhere.aiff", "- Run, she said."])
def test_the_on_device_voice_ends_options_before_the_quote(
        monkeypatch, tmp_path, engine, quote):
    from providers.voice import mock
    seen = []

    def run(cmd, **kwargs):
        seen.append(cmd)
        if cmd[0] in ("say", "espeak"):
            produced = cmd[cmd.index("-o") + 1] if cmd[0] == "say" \
                else cmd[cmd.index("-w") + 1]
            Path(produced).write_bytes(b"audio")
        else:                                   # ffmpeg
            Path(cmd[-1]).write_bytes(b"mp3")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(mock.subprocess, "run", run)
    provider = mock.MockVoiceProvider()
    out = str(tmp_path / "s.mp3")
    if engine == "macos":
        provider._synthesize_macos(quote, out, None)
    else:
        provider._synthesize_linux(quote, out)
    engine_cmd = seen[0]
    assert engine_cmd[-2:] == ["--", quote]


@pytest.mark.skipif(shutil.which("say") is None, reason="macOS `say` only")
def test_say_speaks_a_dash_quote_and_writes_nothing_else(tmp_path):
    """Measured on the real binary: with `--`, an `-o<path>` quote is spoken
    and no stray file appears."""
    stray = tmp_path / "stray.aiff"
    out = tmp_path / "a.aiff"
    done = subprocess.run(["say", "-o", str(out), "--", f"-o{stray}"],
                          capture_output=True, timeout=60)
    assert done.returncode == 0 and out.is_file() and not stray.exists()


# ── S-4: the default kit folder is never in the repo's tracked tree ──────────

def test_kits_from_source_go_under_an_ignored_output_folder(tmp_path):
    assert kitplan.default_kit_base(tmp_path, frozen=True) == tmp_path
    assert kitplan.default_kit_base(tmp_path, frozen=False) == (
        tmp_path / "output" / "release_kits")


@pytest.mark.skipif(not (ROOT / ".git").exists(), reason="needs a git checkout")
def test_the_source_default_kit_folder_is_git_ignored():
    folder = kitplan.default_output_dir(
        kitplan.default_kit_base(ROOT, frozen=False), "My Novel", 3)
    probe = folder / "My_Novel_v3.epub"
    done = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q",
                           str(probe.relative_to(ROOT))])
    assert done.returncode == 0, f"{probe} is not ignored"


def test_the_confirmation_defaults_to_the_kit_base():
    import ui.release_kit.confirm_dialog as dialog_mod
    source = Path(dialog_mod.__file__).read_text(encoding="utf-8")
    assert "kitplan.default_kit_base(user_data_base(), is_frozen())" in source
