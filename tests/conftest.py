"""Test-wide setup that has to happen before anything imports Qt.

## Why this file exists

Seven test modules each called `os.environ.setdefault("QT_QPA_PLATFORM",
"offscreen")` — but inside a fixture, which runs long after pytest has imported
every test module. If any of those imports reached Qt first (importing `main`
does), Qt had already chosen its platform plugin, and `setdefault` then did
nothing at all.

Whether that mattered came down to import order, which is why it worked almost
every time. When it did not, the suite ran on the native **cocoa** platform: it
tried to build real windows on the display, and wedged. One run sat there for
57 minutes inside `QComboBox::addItems` -> `endInsertRows` -> `setCurrentIndex`,
having produced no output and burned 8 seconds of CPU — blocked on a lock, not
looping, so nothing looked wrong except that it never finished.

A conftest is imported before any test module, so setting it here makes the
offscreen platform unconditional rather than a race. The per-file calls can
stay; they are harmless no-ops now, and they document the requirement where a
reader of that file will see it.

## The other thing this guards

`QT_QPA_PLATFORM` is only honoured if it is set *before* the first Qt import.
Nothing here may import PySide6 at module level, and nothing may import `main`.
Keep this file Qt-free.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Every test module repeats this; doing it here means a new one does not have to
# remember, and an import of `main` resolves the same way from any directory.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# setdefault, not assignment: a caller who deliberately asked for another
# platform (debugging a layout on a real screen, say) keeps it.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Qt otherwise writes a "Populating font family aliases took N ms" warning on
# every run because the offscreen platform has no Sans Serif. Harmless, but it
# buries real output.
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false")

# ── Database isolation ────────────────────────────────────────────────────────
# services.database resolves DB_PATH at call time, and several modules build
# the real GodAI window without patching it — test_creator_v2 was INSERTing
# rows into the checkout's live data/imprint.db. Redirecting it here, before
# any test module imports main, makes isolation the default rather than a
# per-fixture convention. Modules that point DB_PATH at their own tmp_path
# still can; the path they restore afterwards is this temp one, not the dev
# database. (services.database imports nothing from Qt, so this keeps the
# rule above intact.)
import tempfile  # noqa: E402

from services import database as _database  # noqa: E402

_database.DB_PATH = Path(tempfile.mkdtemp(prefix="imprint-tests-")) / "imprint.db"

# The app runs init_db() at startup; tests that query without building the
# window were leaning on the dev database's schema being there already.
_database.init_db()

# ── The developer's .env must not reach the suite ────────────────────────────
# `main.py` calls load_dotenv() at import, and most modules here import main,
# so every value in a local .env became part of the test environment. That is
# not hypothetical: creating a .env from .env.example — whose only non-blank
# entries are two Higgsfield endpoint defaults — immediately failed two tests
# in test_higgsfield_client.py that assert the built-in default endpoint.
#
# The worse case is the one that has not happened yet. A suite that sees a live
# ANTHROPIC_API_KEY or HF_API_KEY_ID is a suite where one unmocked call spends
# real money, and the guard tests in test_request_guard.py exist precisely
# because that path is easy to get wrong.
#
# So: clear them here, before any test module imports anything. A test that
# wants a credential sets it with monkeypatch, which is already the convention
# in every module that needs one.
_CREDENTIAL_ENV = (
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "DEEPSEEK_API_KEY", "KIMI_API_KEY", "DASHSCOPE_API_KEY",
    "DASHSCOPE_BASE_URL", "DASHSCOPE_VIDEO_BASE_URL",
    "HF_API_KEY_ID", "HF_API_KEY_SECRET",
    "HIGGSFIELD_API_KEY_ID", "HIGGSFIELD_API_KEY_SECRET",
    "HIGGSFIELD_BASE_URL",
    "HIGGSFIELD_TEXT_VIDEO_ENDPOINT", "HIGGSFIELD_IMAGE_VIDEO_ENDPOINT",
    "ELEVENLABS_API_KEY", "HEYGEN_API_KEY", "SYNTHESIA_API_KEY",
    "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME",
    "REDDIT_PASSWORD", "PINTEREST_ACCESS_TOKEN",
)

for _name in _CREDENTIAL_ENV:
    os.environ.pop(_name, None)

# load_dotenv does not overwrite a variable that is already set, so claiming
# each name with a sentinel keeps main.py's import from putting the real value
# back. The clients all treat a missing key and an empty one the same way.
for _name in _CREDENTIAL_ENV:
    os.environ[_name] = ""

# ── Public model ratings: the shipped snapshot, and no network ────────────────
# The window loads services/recommendations/ratings at startup and refreshes it
# from Hugging Face beside the Model updates check — a minute of paced GETs.
# The suite must neither fetch nor read a developer's cached copy (which would
# make rankings depend on the day the tests run), so the cache points at an
# empty temp folder, staleness reads as fresh, and the fetcher refuses. Every
# test therefore ranks on config/lmarena_snapshot.json. A test of the refresh
# itself undoes these with monkeypatch.
from services import benchmarks as _benchmarks  # noqa: E402
from services.recommendations import ratings as _ratings  # noqa: E402

_ratings.CACHE_FILE = Path(tempfile.mkdtemp(prefix="imprint-ratings-")) / "lmarena_ratings.json"


def _no_ratings_network(url):
    raise RuntimeError(f"tests may not fetch model ratings: {url}")


_benchmarks._get_json = _no_ratings_network
_benchmarks.is_stale = lambda *args, **kwargs: False
