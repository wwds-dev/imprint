"""The app is shown as "Imprint Studio" and three agents as Kernel, Nova and
Vector, while every name that holds state stays "Imprint".

Spec ``docs/specs/rename-imprint-studio.md``, success measure 1. The window
title and header wordmark are checked on the shared window in
``test_panel_layout.py`` (building one costs about ten seconds).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ── (a) name surfaces ──────────────────────────────────────────────────────

@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_the_display_name_constant():
    from services.runtime_paths import APP_DISPLAY_NAME
    assert APP_DISPLAY_NAME == "Imprint Studio"


def test_tray_tooltip_and_actions_use_the_display_name(qapp):
    from ui.tray import Tray
    tray = Tray()
    assert tray.icon.toolTip() == "Imprint Studio"
    labels = [a.text() for a in tray._menu.actions() if a.text()]
    assert labels == ["Open Imprint Studio", "Quit Imprint Studio"]


def test_version_tooltip_starts_with_the_display_name():
    from services import version
    assert version.tooltip().startswith("Imprint Studio ")


# Calls whose string argument a user reads as the app's name.
_NAME_CALLS = {"setWindowTitle", "setAccessibleName", "setToolTip", "name_in_menu_bar"}
_NAME_SOURCES = ["main.py", *sorted(p.relative_to(ROOT).as_posix()
                                    for p in (ROOT / "ui").rglob("*.py"))]


def _literal_name_arguments(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name not in _NAME_CALLS:
            continue
        for arg in node.args:
            for const in ast.walk(arg):
                if isinstance(const, ast.Constant) and isinstance(const.value, str):
                    yield node.lineno, const.value


@pytest.mark.parametrize("rel", _NAME_SOURCES)
def test_no_window_title_or_tray_text_hard_codes_the_old_name(rel):
    """Sub-window titles, accessible names and the menu-bar name read
    ``APP_DISPLAY_NAME``; a literal "Imprint" there is the old name."""
    hits = [f"{rel}:{line} {text!r}" for line, text in _literal_name_arguments(ROOT / rel)
            if re.search(r"\bImprint\b(?! Studio)", text)]
    assert not hits, "\n".join(hits)


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _open_dialog(kind: str):
    from PySide6.QtWidgets import QWidget
    from services.runtime_paths import resource_base
    RESOURCE_DIR = resource_base()
    host = QWidget()
    if kind == "docs":
        from ui.docs_center import DocsCentreDialog
        return host, DocsCentreDialog(host, RESOURCE_DIR)
    if kind == "learn":
        from ui.learning_center_v2 import LearningCentreDialog
        return host, LearningCentreDialog(host, RESOURCE_DIR)
    from ui.income_worksheets import IncomeWorksheetsDialog
    return host, IncomeWorksheetsDialog(host)


@pytest.mark.parametrize("kind,title", [
    ("docs", "Documentation"), ("learn", "Learning Centre"),
    ("income", "Income Lab worksheets"),
])
def test_sub_window_titles_carry_the_display_name(qt_app, kind, title):
    """Review R-11: the static scan above only proves no old literal is
    left; a title that dropped the app name would pass it. Built offscreen."""
    from services.runtime_paths import APP_DISPLAY_NAME
    host, dialog = _open_dialog(kind)
    try:
        assert dialog.windowTitle() == f"{title} · {APP_DISPLAY_NAME}"
    finally:
        dialog.deleteLater()
        host.deleteLater()


def _non_docstring_strings(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                       ast.AsyncFunctionDef))
                  and node.body and isinstance(node.body[0], ast.Expr)
                  and isinstance(node.body[0].value, ast.Constant)}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings):
            yield node.lineno, node.value


@pytest.mark.parametrize("rel", _NAME_SOURCES)
def test_no_user_text_names_the_retired_client_gigs_workspace(rel):
    """The image-model tooltip said "Best image model for Client Gigs", a
    workspace name retired in September; it now reads Vector's label."""
    hits = [f"{rel}:{line} {text!r}"
            for line, text in _non_docstring_strings(ROOT / rel)
            if "Client Gigs" in text]
    assert not hits, "\n".join(hits)


def test_bundle_metadata_names_imprint_studio():
    spec = (ROOT / "Imprint.spec").read_text(encoding="utf-8")
    assert '"CFBundleName": "Imprint Studio"' in spec
    assert '"CFBundleDisplayName": "Imprint Studio"' in spec
    assert 'name="Imprint Studio.app"' in spec
    install = (ROOT / "scripts" / "install_app.sh").read_text(encoding="utf-8")
    assert 'APP_DISPLAY_NAME="Imprint Studio"' in install


# ── (b) state keeps the old name ───────────────────────────────────────────

def test_state_names_do_not_change():
    from services import runtime_paths
    from services import database
    assert runtime_paths.APP_NAME == "Imprint"
    assert database.DB_PATH.name == "imprint.db"
    main_src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'SINGLE_INSTANCE_KEY = "imprint.single-instance"' in main_src
    for rel in ("ui/docs_center.py", "ui/learning_center_v2.py"):
        assert 'QSettings("Imprint", "Imprint")' in (ROOT / rel).read_text(encoding="utf-8")


def test_bundle_id_is_unchanged():
    """An open owner decision (TODO.md), not part of this rename."""
    assert "com.netrunner3000.imprint" in (ROOT / "Imprint.spec").read_text(encoding="utf-8")
    assert "com.netrunner3000.imprint" in (
        ROOT / "scripts" / "install_app.sh").read_text(encoding="utf-8")


# ── (c) every copy of a label equals the catalog ───────────────────────────

def _specs():
    from agents.catalog import AGENT_SPECS
    return [s for s in AGENT_SPECS if s.workspace is not None]


def test_the_three_new_codenames():
    from agents.catalog import AGENTS_BY_KEY
    assert (AGENTS_BY_KEY["chat"].label, AGENTS_BY_KEY["creator"].label,
            AGENTS_BY_KEY["fiverr"].label) == ("Kernel", "Nova", "Vector")


def test_recommendation_profiles_carry_the_catalog_label():
    import importlib
    for spec in _specs():
        if not spec.recommendation_profile:
            continue
        profile = importlib.import_module(spec.recommendation_profile).RECOMMENDATION_PROFILE
        assert profile.label == spec.label, spec.key


def _seeded_labels() -> dict[str, str]:
    tree = ast.parse((ROOT / "services" / "database.py").read_text(encoding="utf-8"))
    func = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_seed_default_agents")
    labels = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            if "name" in keys and "label" in keys:
                values = dict(zip(keys, node.values, strict=False))
                labels[values["name"].value] = values["label"].value
    return labels


def test_the_database_seed_carries_the_catalog_label():
    seeded = _seeded_labels()
    for spec in _specs():
        if spec.key in seeded:
            assert seeded[spec.key] == spec.label, spec.key


def test_registry_and_manifests_carry_the_catalog_label():
    labels = {s.key: s.label for s in _specs()}
    registry = json.loads((ROOT / "config" / "registry.json").read_text(encoding="utf-8"))
    rows = registry if isinstance(registry, list) else next(
        v for v in registry.values() if isinstance(v, list))
    for row in rows:
        if row.get("type") == "agent" and row.get("name") in labels:
            assert row["label"] == labels[row["name"]], row["name"]
    sheets = json.loads((ROOT / "docs" / "agents" / "manifest.json").read_text(encoding="utf-8"))
    for page in sheets["pages"]:
        if page.get("agent") in labels:
            assert page["title"] == labels[page["agent"]], page["id"]
    lessons = json.loads((ROOT / "docs" / "learn" / "manifest.json").read_text(encoding="utf-8"))
    for module in lessons["modules"]:
        if module["section"] == "agents" and module.get("agent") in labels:
            assert module["title"] == labels[module["agent"]], module["id"]


def test_an_existing_database_with_the_old_labels_is_relabelled():
    """A user's database seeded before 2026-11-22 holds Chat, Muse and Stamp;
    the next launch (``init_db``) shows Kernel, Nova and Vector."""
    from services import database
    old = {"chat": "Chat", "creator": "Muse", "fiverr": "Stamp"}
    conn = database.get_connection()
    try:
        for key, label in old.items():
            conn.execute("UPDATE agents SET label = ? WHERE name = ?", (label, key))
        conn.commit()
    finally:
        conn.close()
    database.init_db()
    conn = database.get_connection()
    try:
        rows = dict(conn.execute(
            "SELECT name, label FROM agents WHERE name IN ('chat','creator','fiverr')"))
    finally:
        conn.close()
    assert rows == {"chat": "Kernel", "creator": "Nova", "fiverr": "Vector"}


# ── (d) no old name where a user reads it ──────────────────────────────────

def _string_literals(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    getattr(body[0], "value", None), ast.Constant):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings):
            yield node.lineno, node.value


def _code_sources() -> list[Path]:
    files = [ROOT / "main.py", *sorted((ROOT / "ui").rglob("*.py"))]
    files += sorted((ROOT / "agents").glob("*/panel.py"))
    files += sorted((ROOT / "agents").glob("*/agent.py"))
    files += [ROOT / "services" / "api_keys.py"]
    return files


def _doc_sources() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "agents" / "README.md"]
    files += sorted((ROOT / "agents").glob("*/README.md"))
    files += sorted((ROOT / "docs" / "agents").glob("*.md"))
    files += sorted((ROOT / "docs" / "learn").rglob("*.md"))
    return [p for p in files if p.exists()]


# "Muse" is also Meta's "Muse Glimmer"; "Stamp" is also a verb.
_OLD_MUSE = re.compile(r"\bMuse\b(?! Glimmer)")
_OLD_STAMP = re.compile(r"\bStamp\b")
# A sentence that records the rename itself names the old labels on purpose.
_RENAME_NOTE = re.compile(r"(?i)\b(?:formerly|renamed|was called|until 2026-11-22)\b")


def _old_name_hits(text: str, where: str) -> list[str]:
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        if _RENAME_NOTE.search(line):
            continue
        if _OLD_MUSE.search(line) or _OLD_STAMP.search(line):
            hits.append(f"{where}:{number} {line.strip()[:100]}")
    return hits


@pytest.mark.parametrize("path", _code_sources(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_old_codename_in_user_visible_strings(path):
    hits = []
    for line, text in _string_literals(path):
        hits += [f"{path.relative_to(ROOT)}:{line} {h.split(' ', 1)[1]}"
                 for h in _old_name_hits(text, "x")]
    assert not hits, "\n".join(hits)


@pytest.mark.parametrize("path", _doc_sources(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_old_codename_in_user_docs(path):
    hits = _old_name_hits(path.read_text(encoding="utf-8"),
                          path.relative_to(ROOT).as_posix())
    assert not hits, "\n".join(hits)


def test_no_agent_is_titled_chat():
    """"Chat" stays a word and a job type; it is no longer an agent's name."""
    hits = []
    for path in _doc_sources():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^#{1,4}\s+(?:7\.1\s+)?Chat\b", line):
                hits.append(f"{path.relative_to(ROOT)}:{number} {line}")
    assert not hits, "\n".join(hits)


# ── D1-B: the old bundle is removed, and only it ───────────────────────────

def test_old_bundle_removal_is_one_fixed_path():
    """Both install scripts remove /Applications/Imprint.app after the rename.
    The removal is the only ``rm`` in the helper, names the path in full (no
    glob, no variable), and is guarded by the bundle id."""
    helper = (ROOT / "scripts" / "retire_old_bundle.sh").read_text(encoding="utf-8")
    code = "\n".join(line for line in helper.splitlines()
                     if not line.lstrip().startswith("#"))
    removals = re.findall(r"\brm\b[^\n]*", code)
    assert removals == ['rm -rf -- "/Applications/Imprint.app"']
    assert "com.netrunner3000.imprint" in code
    assert '[ -L "$old" ]' in code          # a symlink is never followed
    assert "*" not in "".join(removals)
    for script in ("install_app.sh", "build_app.sh"):
        text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert 'source "${PROJECT_ROOT}/scripts/retire_old_bundle.sh"' in text, script
        assert "\nretire_old_bundle\n" in text, script

    # Review R-8: a copy that will not quit makes retire_old_bundle return 1,
    # and set -e then stops build_app.sh, so it must come after the build-copy
    # cleanup rather than before it.
    build = (ROOT / "scripts" / "build_app.sh").read_text(encoding="utf-8")
    assert build.index('rm -rf "$DIST_APP"') < build.index("\nretire_old_bundle\n")
