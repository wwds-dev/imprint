"""Both branches of the creator_earnings retirement."""
import sqlite3


def _legacy(path):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE creator_earnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL,
        ingested_at TEXT NOT NULL, source_file TEXT NOT NULL DEFAULT '',
        gross_usd REAL NOT NULL DEFAULT 0.0)""")
    conn.commit()
    return conn


def _tables(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def test_an_empty_legacy_table_is_dropped(tmp_path):
    from services.database import _drop_empty_creator_earnings
    conn = _legacy(tmp_path / "a.db")
    _drop_empty_creator_earnings(conn)
    assert "creator_earnings" not in _tables(conn)


def test_a_table_with_imported_rows_is_left_alone(tmp_path, capsys):
    """Deleting a user's records is the user's decision, not a migration's."""
    from services.database import _drop_empty_creator_earnings
    conn = _legacy(tmp_path / "b.db")
    conn.execute("INSERT INTO creator_earnings (account_id, ingested_at, gross_usd)"
                 " VALUES (1, 'now', 42.0)")
    conn.commit()
    _drop_empty_creator_earnings(conn)
    assert "creator_earnings" in _tables(conn)
    assert conn.execute("SELECT COUNT(*) FROM creator_earnings").fetchone()[0] == 1
    assert "Backstage" in capsys.readouterr().out


def test_running_twice_on_a_modern_database_is_a_no_op(tmp_path):
    from services.database import _drop_empty_creator_earnings
    conn = sqlite3.connect(tmp_path / "c.db")
    _drop_empty_creator_earnings(conn)
    _drop_empty_creator_earnings(conn)
