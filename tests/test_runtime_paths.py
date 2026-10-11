"""adopt_previous_app_dir and the .env seed in services/runtime_paths.

The rename of the app strands the old Application Support directory (and the
API keys in its .env) unless it is carried forward, so each branch is pinned.
"""
import stat

import pytest

from services import runtime_paths


@pytest.fixture
def support(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_paths.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(runtime_paths, "is_frozen", lambda: True)
    d = tmp_path / "Library" / "Application Support"
    d.mkdir(parents=True)
    return d


def _old(support):
    old = support / runtime_paths.PREVIOUS_APP_NAMES[0]
    old.mkdir()
    (old / ".env").write_text("K=1", encoding="utf-8")
    return old


def test_not_frozen_does_nothing(support, monkeypatch):
    old = _old(support)
    monkeypatch.setattr(runtime_paths, "is_frozen", lambda: False)
    assert runtime_paths.adopt_previous_app_dir() is None
    assert old.exists()


def test_old_dir_only_is_renamed(support):
    _old(support)
    target = support / runtime_paths.APP_NAME
    assert runtime_paths.adopt_previous_app_dir() == target
    assert (target / ".env").read_text(encoding="utf-8") == "K=1"
    assert not (support / runtime_paths.PREVIOUS_APP_NAMES[0]).exists()


def test_empty_new_dir_is_replaced(support):
    _old(support)
    target = support / runtime_paths.APP_NAME
    target.mkdir()
    assert runtime_paths.adopt_previous_app_dir() == target
    assert (target / ".env").exists()


def test_populated_new_dir_is_left_alone(support):
    old = _old(support)
    target = support / runtime_paths.APP_NAME
    target.mkdir()
    (target / "new.txt").write_text("new", encoding="utf-8")
    assert runtime_paths.adopt_previous_app_dir() is None
    assert (old / ".env").exists()
    assert [p.name for p in target.iterdir()] == ["new.txt"]


def test_both_populated_nothing_is_merged(support):
    # Pinned current behaviour; see docs/specs/audit-tier1-fixes.md for the
    # deferred decision (merge or notice).
    old = _old(support)
    target = support / runtime_paths.APP_NAME
    target.mkdir()
    (target / "config.json").write_text("{}", encoding="utf-8")
    assert runtime_paths.adopt_previous_app_dir() is None
    assert (old / ".env").read_text(encoding="utf-8") == "K=1"
    assert not (target / ".env").exists()


def test_no_old_dir_returns_none(support):
    assert runtime_paths.adopt_previous_app_dir() is None


def test_rename_failure_does_not_stop_startup(support, monkeypatch, capsys):
    old = _old(support)

    def boom(self, target):
        raise PermissionError("denied")

    monkeypatch.setattr(runtime_paths.Path, "rename", boom)
    assert runtime_paths.adopt_previous_app_dir() is None
    assert (old / ".env").exists()
    assert "denied" in capsys.readouterr().out
    # and the caller still gets a usable directory
    assert runtime_paths.user_data_base().is_dir()


def test_seeded_env_is_owner_only(support, monkeypatch, tmp_path):
    res = tmp_path / "res"
    res.mkdir()
    (res / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")
    monkeypatch.setattr(runtime_paths, "resource_base", lambda: res)
    runtime_paths.ensure_seeded()
    env = support / runtime_paths.APP_NAME / ".env"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600


def test_seeded_fallback_env_is_owner_only(support, monkeypatch, tmp_path):
    res = tmp_path / "res"
    res.mkdir()                                # no .env.example -> write_text path
    monkeypatch.setattr(runtime_paths, "resource_base", lambda: res)
    runtime_paths.ensure_seeded()
    env = support / runtime_paths.APP_NAME / ".env"
    assert "OPENAI_API_KEY=" in env.read_text(encoding="utf-8")
    assert stat.S_IMODE(env.stat().st_mode) == 0o600


def test_existing_env_is_not_touched(support, monkeypatch, tmp_path):
    res = tmp_path / "res"
    res.mkdir()
    monkeypatch.setattr(runtime_paths, "resource_base", lambda: res)
    d = support / runtime_paths.APP_NAME
    d.mkdir()
    env = d / ".env"
    env.write_text("KEEP=1", encoding="utf-8")
    runtime_paths.ensure_seeded()
    assert env.read_text(encoding="utf-8") == "KEEP=1"
