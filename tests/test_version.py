"""The version shown in the header, and the honesty of its staleness check.

Two things here are worth pinning rather than trusting.

The **format**, because it is user-facing and appears beside the wordmark: a
build number that stopped zero-padding, or a major that leaked a dotted suffix,
would look like a bug in the app rather than in a version string.

The **staleness verdict**, because the failure mode is silent. Claiming "up to
date" when there is nothing to compare against is worse than saying nothing —
it is the answer the user is relying on when they check whether the app they
just opened includes the change they asked for.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import version as app_version  # noqa: E402

VERSION_RE = re.compile(r"^v\d+\.\d{3,}$")


@pytest.fixture(autouse=True)
def _clear_cache():
    """`info()` is cached for the process; these tests change what it reads."""
    app_version.info.cache_clear()
    yield
    app_version.info.cache_clear()


class TestFormat:
    def test_version_reads_as_a_version(self):
        assert VERSION_RE.match(app_version.version_string()), (
            f"{app_version.version_string()!r} is not v<major>.<build>")

    @pytest.mark.parametrize("build,expected", [
        (7, "v2.007"), (42, "v2.042"), (112, "v2.112"), (1234, "v2.1234"),
    ])
    def test_build_is_zero_padded_to_three(self, monkeypatch, build, expected):
        """v2.7 reads as a draft; v2.007 reads as a build.

        Driven with small numbers on purpose. Asserting only against the
        current build tests nothing — 112 is already three digits, so removing
        the padding entirely still passes. The padding only shows below 100,
        which is exactly where a new project starts.
        """
        monkeypatch.setattr(app_version, "_read_major", lambda: "2")
        monkeypatch.setattr(app_version, "_git_build",
                            lambda *a, **k: {"build": build, "commit": "x",
                                             "date": "", "source": "git"})
        monkeypatch.setattr(app_version, "_baked", lambda: None)
        monkeypatch.setattr(app_version, "is_frozen", lambda: False)
        app_version.info.cache_clear()
        assert app_version.info()["version"] == expected

    def test_the_major_comes_from_the_VERSION_file(self):
        declared = (Path(__file__).resolve().parent.parent / "VERSION").read_text().strip()
        assert app_version.info()["major"] == declared.lstrip("vV").split(".")[0]

    def test_build_matches_the_repository(self):
        """The number is the commit count — not a number someone maintains."""
        count = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True, text=True).stdout.strip()
        if not count.isdigit():
            pytest.skip("no git metadata in this checkout")
        assert app_version.info()["build"] == int(count)


class TestStalenessIsHonest:
    def test_an_unstamped_build_does_not_claim_to_be_current(self, monkeypatch):
        """The whole point: 'I cannot tell' must not render as 'up to date'."""
        monkeypatch.setattr(app_version, "_git_build", lambda *a, **k: None)
        monkeypatch.setattr(app_version, "_baked", lambda: None)
        app_version.info.cache_clear()

        verdict = app_version.staleness()
        assert verdict["known"] is False
        assert verdict["current"] is False
        assert "cannot" in verdict["detail"] or "no version stamp" in verdict["detail"]

    def test_no_checkout_to_compare_against_is_reported_as_unknown(self, monkeypatch):
        """A packaged app on a machine with no source must say so."""
        monkeypatch.setattr(app_version, "_baked",
                            lambda: {"build": 40, "commit": "abc1234",
                                     "date": "", "source": "baked"})
        monkeypatch.setattr(app_version, "_git_build", lambda *a, **k: None)
        monkeypatch.setattr(app_version, "is_frozen", lambda: True)
        app_version.info.cache_clear()

        verdict = app_version.staleness()
        assert verdict["known"] is False
        assert verdict["current"] is False

    def test_a_build_behind_the_checkout_says_how_far(self, monkeypatch):
        monkeypatch.setattr(app_version, "_baked",
                            lambda: {"build": 100, "commit": "old1234",
                                     "date": "", "source": "baked"})
        monkeypatch.setattr(app_version, "is_frozen", lambda: True)
        monkeypatch.setattr(app_version, "_git_build",
                            lambda *a, **k: {"build": 112, "commit": "new5678",
                                             "date": "", "source": "git"})
        app_version.info.cache_clear()

        verdict = app_version.staleness()
        assert verdict["known"] is True
        assert verdict["current"] is False
        assert verdict["behind"] == 12
        assert "12 commits behind" in verdict["detail"]

    def test_singular_when_one_behind(self):
        """Reads as prose in a tooltip, so '1 commits' would show."""
        import services.version as v
        v.info.cache_clear()
        original_baked, original_git = v._baked, v._git_build
        v._baked = lambda: {"build": 111, "commit": "a", "date": "", "source": "baked"}
        v._git_build = lambda *a, **k: {"build": 112, "commit": "b", "date": "", "source": "git"}
        v.is_frozen, original_frozen = (lambda: True), v.is_frozen
        try:
            v.info.cache_clear()
            assert "1 commit behind" in v.staleness()["detail"]
        finally:
            v._baked, v._git_build, v.is_frozen = original_baked, original_git, original_frozen
            v.info.cache_clear()


class TestFrozenPrefersItsOwnStamp:
    def test_a_bundle_reports_the_build_it_was_made_from(self, monkeypatch):
        """A checkout sitting beside a bundle is not what the bundle runs."""
        monkeypatch.setattr(app_version, "is_frozen", lambda: True)
        monkeypatch.setattr(app_version, "_baked",
                            lambda: {"build": 99, "commit": "baked99",
                                     "date": "", "source": "baked"})
        monkeypatch.setattr(app_version, "_git_build",
                            lambda *a, **k: {"build": 112, "commit": "live112",
                                             "date": "", "source": "git"})
        app_version.info.cache_clear()
        assert app_version.info()["build"] == 99
        assert app_version.info()["source"] == "baked"


class TestTheStampScript:
    def test_it_writes_what_version_reads_back(self, tmp_path, monkeypatch):
        root = Path(__file__).resolve().parent.parent
        stamp = root / app_version.BUILD_INFO_NAME
        if not stamp.is_file():
            pytest.skip("no stamp present; scripts/stamp_version.py has not run")
        data = json.loads(stamp.read_text(encoding="utf-8"))
        assert isinstance(data.get("build"), int)
        assert data.get("major") == app_version.info()["major"]


class TestTheShellShowsIt:
    """The version moved from a header badge to the app mark's tooltip and
    Settings > General > About (spec manuscript-redesign D2, Design S2/S4;
    rewritten from TestTheHeaderShowsIt in slice 1)."""

    def test_the_mark_carries_the_version(self, app, window):
        tip = window.app_mark.toolTip()
        assert app_version.version_string() in tip
        # The hover is where "is this current?" gets answered.
        assert any(word in tip for word in ("Up to date", "behind", "cannot", "no version stamp"))
        assert window.app_mark.accessibleDescription() == tip

    def test_a_stale_build_shows_the_dot_and_says_so(self, app, window):
        stale = not app_version.staleness()["current"]
        assert window.app_mark.stale is stale
        if stale:
            assert "older than the code" in window.app_mark.toolTip()

    @pytest.mark.parametrize("current", [True, False])
    def test_both_build_states_reach_the_mark(self, app, window, monkeypatch,
                                              current):
        """QA F3: forced, not read from this checkout's real state."""
        real = dict(app_version.staleness())
        monkeypatch.setattr(app_version, "staleness",
                            lambda *a, **k: {**real, "current": current})
        try:
            window._show_version_on_mark()
            assert window.app_mark.stale is (not current)
            assert ("older than the code" in window.app_mark.toolTip()) is \
                (not current)
            assert window.app_mark.accessibleName().endswith(
                "(stale build)") is (not current)
        finally:
            monkeypatch.undo()
            window._show_version_on_mark()

    @pytest.mark.parametrize("current", [True, False])
    def test_both_build_states_reach_the_about_line(self, app, window,
                                                    monkeypatch, current):
        from PySide6.QtWidgets import QDialog, QLabel
        from ui import dialogs
        real = dict(app_version.staleness())
        monkeypatch.setattr(app_version, "staleness",
                            lambda *a, **k: {**real, "current": current})
        opened = []
        monkeypatch.setattr(QDialog, "exec", lambda self: opened.append(self) or 0)
        dialogs.show_settings(window)
        try:
            about = opened[0].findChild(QLabel, "SettingsAbout")
            assert ("older than the code" in about.text()) is (not current)
        finally:
            opened[0].reject()

    def test_the_about_line_matches_the_module(self, app, window, monkeypatch):
        from PySide6.QtWidgets import QDialog, QLabel
        from ui import dialogs
        opened = []
        monkeypatch.setattr(QDialog, "exec", lambda self: opened.append(self) or 0)
        dialogs.show_settings(window)
        about = opened[0].findChild(QLabel, "SettingsAbout")
        assert about is not None
        assert about.text().startswith(f"Imprint {app_version.version_string()}")
        assert ("older than the code" in about.text()) is \
            (not app_version.staleness()["current"])
        opened[0].reject()


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main

    saved = QMessageBox.warning
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        QMessageBox.warning = saved
