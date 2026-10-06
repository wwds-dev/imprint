"""Migrations — the path every other test skips.

Every test module builds its database from `SCHEMA`, which already has every
column, so `_add_missing_columns` has never been exercised by the suite. That
is the half that runs on a real user's machine, and it was broken: the `wanted`
dict named `creator_video_jobs` twice, a duplicate key in a dict literal is not
an error, and the later entry replaced the earlier one. Four settlement columns
were therefore dead code.

The visible cost was a paid feature failing quietly. `resume_pending_teasers`
threw `no such column: spend_state` on every launch of this project's own
database; `_note_failure` caught it, so the app started normally and simply
never resumed an in-flight Higgsfield render — one that had already been
authorized and may already have been billed.

Run with:  pytest tests/test_database_migrations.py -v
"""

from __future__ import annotations

import ast
import re
import sqlite3
from pathlib import Path

import pytest

from services import database


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_SOURCE = PROJECT_ROOT / "services" / "database.py"


@pytest.fixture
def db(tmp_path, monkeypatch):
    """An isolated database path, initialised on demand by the test."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "m.db")
    return database.DB_PATH


def _columns(path: Path, table: str) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    finally:
        conn.close()


def _wanted() -> dict[str, list[tuple[str, str]]]:
    """The migration table, read out of the module rather than restated here."""
    source = ast.parse(DATABASE_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(source):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "_add_missing_columns"):
            for statement in ast.walk(node):
                if (isinstance(statement, ast.Assign)
                        and isinstance(statement.targets[0], ast.Name)
                        and statement.targets[0].id == "wanted"):
                    return ast.literal_eval(statement.value)
    raise AssertionError("could not find _add_missing_columns' wanted table")


# ── The defect itself ────────────────────────────────────────────────────────

def test_no_table_is_listed_twice_in_the_migration_table():
    """A duplicate key loses every column under the earlier entry, silently.

    Read the keys as written, not the dict Python built — by the time the
    literal is a dict the duplicate has already been collapsed and there is
    nothing left to detect.
    """
    source = ast.parse(DATABASE_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(source):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "_add_missing_columns"):
            for statement in ast.walk(node):
                if (isinstance(statement, ast.Assign)
                        and isinstance(statement.targets[0], ast.Name)
                        and statement.targets[0].id == "wanted"):
                    keys = [key.value for key in statement.value.keys]
                    duplicates = {k for k in keys if keys.count(k) > 1}
                    assert not duplicates, (
                        "listed twice in `wanted`; the later entry replaces the "
                        f"earlier and its columns never migrate: {duplicates}")
                    return
    raise AssertionError("could not find _add_missing_columns' wanted table")


def test_an_older_database_gains_every_migration_column(db):
    """The regression test for the real failure: a database that predates a
    column must come out of init_db with it."""
    database.init_db()
    wanted = _wanted()

    # Take the database back to its pre-migration shape. SQLite has supported
    # ALTER TABLE DROP COLUMN since 3.35; the venv ships far newer.
    conn = sqlite3.connect(db)
    dropped: dict[str, list[str]] = {}
    for table, columns in wanted.items():
        for name, _decl in columns:
            try:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {name}")
            except sqlite3.OperationalError:
                # Some columns cannot be dropped (indexed, or part of a
                # constraint). Those are not the ones at risk here.
                continue
            dropped.setdefault(table, []).append(name)
    conn.commit()
    conn.close()

    assert dropped, "nothing could be dropped; the test would prove nothing"
    for table, names in dropped.items():
        have = _columns(db, table)
        assert not (set(names) & set(have)), f"{table}: drop did not take"

    database.init_db()

    for table, names in dropped.items():
        have = _columns(db, table)
        missing = [name for name in names if name not in have]
        assert not missing, f"{table} did not regain: {', '.join(missing)}"


def test_the_creator_teaser_settlement_columns_survive_a_migration(db):
    """Named explicitly because these four were the dead entry, and because the
    feature they back spends money: without `spend_state` an authorized teaser
    render is stranded rather than resumed."""
    database.init_db()
    conn = sqlite3.connect(db)
    for name in ("spend_state", "flat_cost_eur", "output_path", "run_id"):
        conn.execute(f"ALTER TABLE creator_video_jobs DROP COLUMN {name}")
    conn.commit()
    conn.close()

    database.init_db()

    have = _columns(db, "creator_video_jobs")
    for name in ("spend_state", "flat_cost_eur", "output_path", "run_id"):
        assert name in have, f"creator_video_jobs lost {name}"


def test_the_resume_query_runs_against_a_migrated_database(db):
    """`resume_pending_teasers` is guarded by a broad `except`, so a missing
    column reads as "no pending teasers" rather than as a failure. Run the
    query the panel runs, so the suite sees what the panel swallows."""
    database.init_db()
    conn = sqlite3.connect(db)
    for name in ("spend_state", "flat_cost_eur", "output_path", "run_id"):
        conn.execute(f"ALTER TABLE creator_video_jobs DROP COLUMN {name}")
    conn.commit()
    conn.close()

    database.init_db()

    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM creator_video_jobs WHERE spend_state = 'reserved' "
            "ORDER BY created_at").fetchall()
    assert rows == []          # none pending, but the query resolved


def test_init_db_is_idempotent(db):
    """It runs on every launch; a second pass must not fail or alter anything."""
    database.init_db()
    before = {table: _columns(db, table) for table in _wanted()}
    database.init_db()
    database.init_db()
    assert {table: _columns(db, table) for table in _wanted()} == before


# ── SCHEMA and the migration table must agree, except where they must not ───

# Columns the Backstage split retired. SCHEMA no longer declares them, so a
# fresh install does not get them; `wanted` still carries them, so a database
# that already has them keeps them rather than being migrated destructively.
# `agents/creator/panel.py` states the same thing at its INSERT: the columns
# are left in place deliberately and never written.
RETIRED = {
    "creator_content": {"segment", "posted_at", "revenue_usd"},
}


def test_every_migrated_column_is_declared_in_schema_or_knowingly_retired():
    """SCHEMA is what a fresh install gets; `wanted` is what an old database is
    brought up to. A column in `wanted` and not SCHEMA is usually a mistake —
    someone adding a column to one and not the other — so the exceptions are
    named above rather than tolerated silently.
    """
    schema = database.SCHEMA
    for table, columns in _wanted().items():
        match = re.search(
            rf"CREATE TABLE IF NOT EXISTS {table}\s*\((.*?)\n\s*\);",
            schema, re.S)
        assert match, f"{table} is migrated but not declared in SCHEMA"
        body = match.group(1)
        retired = RETIRED.get(table, set())
        undeclared = {name for name, _decl in columns
                      if not re.search(rf"\b{name}\b", body)}
        unexpected = undeclared - retired
        assert not unexpected, (
            f"SCHEMA's {table} does not declare {sorted(unexpected)}. Add them "
            "there, or add them to RETIRED in this file with the reason.")
        stale = retired - undeclared
        assert not stale, (
            f"{table}: {sorted(stale)} is listed as retired but SCHEMA now "
            "declares it — drop it from RETIRED.")


def test_the_retired_creator_columns_are_never_written():
    """Keeping a column is not the same as using one. If an INSERT starts
    writing a retired column, the money side of this work has come back into
    Imprint and the Backstage boundary (tests/test_creator_agent.py) is the
    thing to settle first."""
    panel = (PROJECT_ROOT / "agents" / "creator" / "panel.py").read_text(
        encoding="utf-8")
    inserts = re.findall(r"INSERT INTO creator_content\s*\((.*?)\)",
                         panel, re.S)
    assert inserts, "no INSERT INTO creator_content found; update this test"
    written = {name.strip() for block in inserts
               for name in block.replace("\n", " ").split(",")}
    for name in RETIRED["creator_content"]:
        assert name not in written, (
            f"creator_content.{name} is retired but an INSERT writes it")
