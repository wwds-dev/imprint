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
# The second rule is for Qt Multimedia's FFmpeg backend, which prints
# avformat's "Input #0, mp3, from '…/test.mp3'" dump whenever the player tests
# open their real MP3 — noise that reads like a failure in a quiet run.
# Added 2026-10-09 after the readiness-gate walk; confirm it silences the
# banner on the next Mac run (TODO card), and drop it if it does not.
os.environ.setdefault("QT_LOGGING_RULES",
                      "qt.qpa.fonts=false;qt.multimedia.ffmpeg*=false")

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
    "DASHSCOPE_BASE_URL", "DASHSCOPE_VIDEO_BASE_URL", "DASHSCOPE_WORKSPACE_ID",
    "HF_API_KEY_ID", "HF_API_KEY_SECRET",
    "HIGGSFIELD_API_KEY_ID", "HIGGSFIELD_API_KEY_SECRET",
    "HIGGSFIELD_BASE_URL",
    "HIGGSFIELD_TEXT_VIDEO_ENDPOINT", "HIGGSFIELD_IMAGE_VIDEO_ENDPOINT",
    "ELEVENLABS_API_KEY", "HEYGEN_API_KEY", "SYNTHESIA_API_KEY",
    "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME",
    "REDDIT_PASSWORD", "PINTEREST_ACCESS_TOKEN",
    "PUBLISHDRIVE_API_KEY",
)

for _name in _CREDENTIAL_ENV:
    os.environ.pop(_name, None)

# load_dotenv does not overwrite a variable that is already set, so claiming
# each name with a sentinel keeps main.py's import from putting the real value
# back. The clients all treat a missing key and an empty one the same way.
for _name in _CREDENTIAL_ENV:
    os.environ[_name] = ""

# The sentinels only hold while the names exist. Settings' Save pops every
# blank field from os.environ, and vidforge.config.load_env() runs
# load_dotenv(override=False) the first time the pipeline asks for a path,
# searching upward from vidforge/ for any .env: in a checkout that is the
# developer's own, so a popped name could come back with a real key. Marking
# vidforge's loader done makes it a no-op for the session (the app still runs
# it), and `_credential_names_stay_blanked` below fails any test that drops a
# name. The path is appended, never inserted, as agents/video/studio.py does.
_VIDFORGE_ROOT = PROJECT_ROOT / "vidforge"
if _VIDFORGE_ROOT.is_dir() and str(_VIDFORGE_ROOT) not in sys.path:
    sys.path.append(str(_VIDFORGE_ROOT))
try:
    from vidforge import config as _vidforge_config  # noqa: E402
except Exception:                     # no vidforge here: nothing to load a .env either
    _vidforge_config = None
else:
    _vidforge_config._env_loaded = True

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _credential_names_stay_blanked():
    """Fail the test that removed a blanked name, then put it back so the
    leak does not spread. A test that changes one records it with
    monkeypatch.setenv first (test_settings_keys._restore_env_after_save)."""
    yield
    dropped = [name for name in _CREDENTIAL_ENV if name not in os.environ]
    for name in dropped:
        os.environ[name] = ""
    if dropped:
        pytest.fail(f"this test removed {', '.join(dropped)} from os.environ and did not "
                    "put it back; record it with monkeypatch.setenv before changing it",
                    pytrace=False)


@pytest.fixture(autouse=True, scope="module")
def _collect_the_last_modules_windows():
    """Free the previous module's widgets now, before this module builds any.

    Most modules build a module-scoped `main.GodAI` and never close it; with
    its signal-lambda cycles it becomes cyclic garbage when the module ends,
    and the collector frees it whenever it next runs. If that is inside a
    new window's `__init__` while it walks `app.allWidgets()`
    (`install_dropdown_system`, `install_text_fit`), the walk touches freed
    widgets and the process segfaults: reproduced 2026-10-14 by replaying
    the `--randomly-seed=28367` order (crash in ui/widgets.py building
    test_creator_calendar's window, 3 runs of 3), gone with this collection.
    """
    import gc
    gc.collect()
    yield


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


@pytest.fixture(autouse=True, scope="session")
def _local_inventory_is_seeded_not_discovered():
    """What is "on this Mac" must not depend on this Mac.

    Every `LocalInventory` starts pre-seeded with LM Studio off, Ollama empty
    and 24 GB of memory, and never reports itself stale, so no test reaches a
    socket or ~/.lmstudio and nothing runs discovery on the GUI thread. Session
    scope, because module-scoped window fixtures are built before any
    function-scoped patch would apply. Tests of discovery build their own.
    """
    from types import SimpleNamespace

    from services import local_models

    off = SimpleNamespace(server_up=lambda: False, model_details=lambda: [])
    empty = SimpleNamespace(model_details=lambda: {}, list_models=lambda: [],
                            loaded_models=lambda: [])
    real_init = local_models.LocalInventory.__init__
    real_discover = local_models.discover

    def stubbed(*args, **kwargs):
        return real_discover(off, empty, memory=lambda: (16e9, 24e9),
                             lms_binary=lambda: None)

    def seeded(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        self.store(stubbed())

    with pytest.MonkeyPatch.context() as patch:
        # A live event loop lets the startup discovery fire; it must not read
        # this Mac either.
        patch.setattr(local_models, "discover", stubbed)
        patch.setattr(local_models.LocalInventory, "__init__", seeded)
        patch.setattr(local_models.LocalInventory, "stale",
                      lambda self, now=None: False)
        yield
