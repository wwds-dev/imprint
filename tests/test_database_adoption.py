"""_adopt_previous_db with a real WAL database.

A renamed database whose -wal sidecar is left behind (or moved wrongly) loses
the most recent committed transactions without any error. The fixture builds a
crash-like state: a committed row that exists only in the -wal file.
"""

from __future__ import annotations

import shutil
import sqlite3

import pytest

from services import database


def _crashed_legacy_db(dest, name):
    """Copy a live WAL database (main, -wal, -shm) as a crash would leave it."""
    src = dest / "_src"
    src.mkdir()
    conn = sqlite3.connect(src / "x.db")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t VALUES ('checkpointed')")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("INSERT INTO t VALUES ('wal-only')")
    conn.commit()
    for suffix in ("", "-wal", "-shm"):
        shutil.copy(src / ("x.db" + suffix), dest / (name + suffix))
    conn.close()
    shutil.rmtree(src)
    assert (dest / (name + "-wal")).stat().st_size > 0   # the write really is uncheckpointed


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "imprint.db")
    return database.DB_PATH


def _rows(path):
    conn = sqlite3.connect(path)
    try:
        return sorted(r[0] for r in conn.execute("SELECT v FROM t"))
    finally:
        conn.close()


def test_uncheckpointed_write_survives_adoption(db):
    old = database.PREVIOUS_DB_NAMES[0]
    _crashed_legacy_db(db.parent, old)
    database._adopt_previous_db()
    assert not (db.parent / old).exists()
    assert not (db.parent / (old + "-wal")).exists()
    # No assertion on imprint.db-wal: _has_tables(old) opens and closes the
    # legacy file first, and sqlite checkpoints a WAL when its last connection
    # closes, so the -wal write is folded into the main file before the move.
    assert _rows(db) == ["checkpointed", "wal-only"]


def test_populated_current_db_is_not_replaced(db):
    old = database.PREVIOUS_DB_NAMES[0]
    _crashed_legacy_db(db.parent, old)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t VALUES ('current')")
    conn.commit()
    conn.close()
    database._adopt_previous_db()
    assert _rows(db) == ["current"]
    assert (db.parent / old).exists()


def test_empty_placeholder_is_replaced(db):
    old = database.PREVIOUS_DB_NAMES[0]
    _crashed_legacy_db(db.parent, old)
    sqlite3.connect(db).close()                      # 0-byte placeholder
    database._adopt_previous_db()
    assert _rows(db) == ["checkpointed", "wal-only"]
