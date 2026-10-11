"""
Imprint — a failed ratings refresh waits a day, like a successful one
=====================================================================
Type: unit; the worker test needs QtCore only.

Ported from Sentinel (2026-10-09, "a failed try waits a day") with the
`services/benchmarks.py` change the drift guard flagged. Before it, an
offline Mac re-tried the LMArena fetch on every launch: `is_stale` read only
the `fetched` stamp, and a failure wrote nothing.

Run with:  pytest tests/test_ratings_attempts.py -v
"""

import json
from datetime import datetime, timedelta

from services import benchmarks as b
from services.recommendations import ratings


def test_a_failed_attempt_counts_as_a_daily_try(tmp_path):
    """note_attempt makes a failure wait a day like a success does, without
    losing any cached table."""
    cache = tmp_path / "ratings.json"
    cache.write_text(json.dumps({"fetched": "2000-01-01T00:00:00",
                                 "categories": {"coding": {"x": 1}}}))
    assert b._older_than_max_age(cache)
    tried = datetime(2026, 10, 9, 12, 0)
    b.note_attempt(cache, now=tried)
    assert not b._older_than_max_age(cache, now=tried + timedelta(hours=23))
    assert b._older_than_max_age(cache, now=tried + timedelta(hours=25))
    assert json.loads(cache.read_text())["categories"] == {"coding": {"x": 1}}


def test_note_attempt_on_a_missing_cache_creates_only_the_stamp(tmp_path):
    cache = tmp_path / "sub" / "ratings.json"
    b.note_attempt(cache, now=datetime(2026, 10, 9, 12, 0))
    data = json.loads(cache.read_text())
    assert set(data) == {"attempted"}
    # No tables: not a usable cache, so the shipped snapshot still serves.
    assert b.load(cache).origin == "snapshot"
    assert b._older_than_max_age(cache, now=datetime(2026, 10, 9, 13, 0)) is False


def test_the_ratings_worker_stamps_a_failed_refresh(monkeypatch):
    """The worker is the only caller of refresh(); it must record the try, or
    the stamp in benchmarks.py is dead code and the fetch repeats at launch."""
    from ui.workers import RatingsWorker

    def boom():
        raise RuntimeError("leaderboard is loading")
    monkeypatch.setattr(ratings, "refresh", boom)
    stamped = []
    monkeypatch.setattr(ratings, "note_attempt", lambda: stamped.append(True))
    worker = RatingsWorker()
    got = []
    worker.ratings_ready.connect(lambda table, error: got.append((table, error)))
    worker.run()
    assert stamped == [True]
    assert got == [(None, "leaderboard is loading")]


def test_ratings_note_attempt_stamps_the_apps_cache_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ratings, "CACHE_FILE", tmp_path / "lmarena_ratings.json")
    ratings.note_attempt()
    assert "attempted" in json.loads(ratings.cache_file().read_text())
