"""Docs integrity: the README, agent sheets, package READMEs, lessons and test
docs say only what the app can back up.

Spec: ``docs/specs/docs-learning-centre-readiness.md`` ("Checks that become
tests", T1 to T10). The lessons were already guarded by
``test_learning_center.py``; the README and the sheets were not, which is why
they drifted. Each check below names the audit finding it stops recurring
(``docs/audit/docs-learning-centre-readiness-tech-writer.md``).

A case still waiting for the name pass (package 5, with the rename in
``docs/specs/rename-imprint-studio.md``) is marked ``xfail(strict=True)``: it
fails today for a known reason, and the mark has to come off when that pass
lands, because a strict xfail that starts passing fails the suite.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
LEARN = ROOT / "docs" / "learn"
SHEETS = ROOT / "docs" / "agents"
CONTROLS_FILE = ROOT / "tests" / "docs_controls.txt"

PACKAGE_5 = "names change with the rename (spec package 5)"


def _package5(*values):
    return pytest.param(*values, marks=pytest.mark.xfail(strict=True, reason=PACKAGE_5))


# ── Which files are user docs ──────────────────────────────────────────────

def _user_docs() -> list[Path]:
    files = [README, ROOT / "SUPPORT.md", ROOT / "agents" / "README.md"]
    files += sorted((ROOT / "agents").glob("*/README.md"))
    files += sorted(SHEETS.glob("*.md"))
    files += sorted(LEARN.rglob("*.md"))
    files += sorted((ROOT / "tests").glob("*.md"))
    return [path for path in files if path.exists()]


USER_DOCS = _user_docs()


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


# ── Markdown helpers ───────────────────────────────────────────────────────

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.S | re.M)
_INLINE_CODE = re.compile(r"`[^`\n]*`")


def _visible(text: str) -> str:
    """Text a reader sees: no HTML comments, no fenced code, no inline code.
    Line breaks are kept so line numbers stay meaningful."""
    def blank(match: re.Match) -> str:
        return "\n" * match.group(0).count("\n")
    text = _COMMENT.sub(blank, text)
    text = _FENCE.sub(blank, text)
    return _INLINE_CODE.sub("``", text)


def _github_slug(heading: str) -> str:
    value = heading.strip().lower()
    value = re.sub(r"[*_`]", "", value)
    value = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"[^\w\- ]", "", value)
    return value.replace(" ", "-")


@lru_cache(maxsize=None)
def _anchors(path: Path) -> frozenset[str]:
    """Anchors a link may target in ``path``: GitHub slugs (with the -1, -2
    suffixes for repeated headings) and the Learning Centre's own anchors."""
    from ui.learning_center_v2 import _anchor

    text = _visible(path.read_text(encoding="utf-8"))
    seen: dict[str, int] = {}
    found: set[str] = set()
    for match in re.finditer(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, re.M):
        heading = match.group(1)
        slug = _github_slug(heading)
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        found.add(slug if count == 0 else f"{slug}-{count}")
        found.add(_anchor(heading))
    for match in re.finditer(r"<a\s+(?:name|id)=\"([^\"]+)\"", text):
        found.add(match.group(1))
    return frozenset(found)


_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _links(path: Path) -> list[tuple[int, str]]:
    text = _visible(path.read_text(encoding="utf-8"))
    out = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in _LINK.finditer(line):
            out.append((number, match.group(1)))
    return out


def _bold(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"\*\*([^*\n]+?)\*\*", text)]


def _section(text: str, heading_pattern: str) -> str:
    """Body of the first heading matching ``heading_pattern`` up to the next
    heading of the same or a higher level."""
    lines = text.splitlines()
    for start, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match and re.search(heading_pattern, match.group(2)):
            level = len(match.group(1))
            body = []
            for row in lines[start + 1:]:
                nxt = re.match(r"^(#{1,6})\s", row)
                if nxt and len(nxt.group(1)) <= level:
                    break
                body.append(row)
            return "\n".join(body)
    raise AssertionError(f"no heading matches {heading_pattern!r}")


# ── T1: links and anchors ──────────────────────────────────────────────────

@pytest.mark.parametrize("path", USER_DOCS, ids=_rel)
def test_t1_relative_links_and_anchors_resolve(path):
    """DL-6: a contents entry pointed at a chapter that existed only inside an
    HTML comment. Comments are stripped before anchors are collected."""
    broken = []
    for number, target in _links(path):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target):  # http:, mailto:, show:
            continue
        file_part, _, anchor = target.partition("#")
        dest = (path.parent / file_part).resolve() if file_part else path
        if not dest.exists():
            broken.append(f"{_rel(path)}:{number} -> {target} (no such file)")
            continue
        if anchor and dest.suffix == ".md" and anchor not in _anchors(dest):
            broken.append(f"{_rel(path)}:{number} -> {target} (no such heading)")
    assert not broken, "\n".join(broken)


# ── T2: section references ─────────────────────────────────────────────────

def _readme_numbers() -> set[str]:
    text = _visible(README.read_text(encoding="utf-8"))
    return {m.group(1).rstrip(".")
            for m in re.finditer(r"^#{2,6}\s+(\d+(?:\.\d+)*)\.?\s", text, re.M)}


@pytest.mark.parametrize("path", USER_DOCS, ids=_rel)
def test_t2_section_references_name_real_readme_sections(path):
    """DL-22: "Section 12.4" and "§5.6" named sections that do not exist.
    Inside README.md every "§N" or "Section N" is a README section; elsewhere
    only "README §N" is (other files number their own sections)."""
    numbers = _readme_numbers()
    text = _visible(path.read_text(encoding="utf-8"))
    if path == README:
        pattern = r"(?:§\s?|\b[Ss]ection )(\d+(?:\.\d+)*)"
    else:
        pattern = r"README(?:'s)? (?:§\s?|[Ss]ection )(\d+(?:\.\d+)*)"
    wrong = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in re.finditer(pattern, line):
            ref = match.group(1).rstrip(".")
            if ref not in numbers:
                wrong.append(f"{_rel(path)}:{number} §{ref}")
    assert not wrong, "no such README section:\n" + "\n".join(wrong)


# ── T3: orphan lessons ─────────────────────────────────────────────────────

def test_t3_every_learn_page_on_disk_is_in_the_manifest():
    """DL-17: seven legacy pages sat beside the lessons, shipped in the bundle
    and never shown. The existing orphan test looked only in ``modules/``."""
    manifest = json.loads((LEARN / "manifest.json").read_text(encoding="utf-8"))
    listed = {entry["filename"] for entry in manifest["modules"]}
    on_disk = {p.relative_to(LEARN).as_posix() for p in LEARN.rglob("*.md")}
    assert on_disk == listed, (
        f"on disk, not in manifest: {sorted(on_disk - listed)}; "
        f"in manifest, not on disk: {sorted(listed - on_disk)}")


# ── T4: quoted controls ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _app_strings() -> tuple[str, ...]:
    """Every string literal in the app's Python and its config JSON, except
    docstrings: a phrase in a docstring is never on screen (review R-3, where
    "too big right now" passed on ``services/providers.py``'s docstring)."""
    skip = {".venv", "tests", "cloud", "build", "dist", ".claude", "_to_delete"}
    strings: list[str] = []
    scopes = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for path in ROOT.rglob("*.py"):
        if skip & set(path.relative_to(ROOT).parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, scopes) and node.body
                      and isinstance(node.body[0], ast.Expr)
                      and isinstance(node.body[0].value, ast.Constant)}
        strings += [node.value for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings]

    def walk(value):
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                strings.append(str(key))
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for path in (ROOT / "config").glob("*.json"):
        try:
            walk(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return tuple(strings)


def _normalise(text: str) -> str:
    return text.replace("…", "...").strip()


def _in_app(phrase: str) -> bool:
    wanted = _normalise(phrase)
    return any(wanted in _normalise(s) for s in _app_strings())


def _controls() -> tuple[list[str], set[str]]:
    """``tests/docs_controls.txt``: controls the docs quote, then, after the
    ``[not controls]`` line, bold phrases in a control atlas that are not
    labels (section names, states, emphasis)."""
    controls: list[str] = []
    allowed: set[str] = set()
    target = controls
    for line in CONTROLS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[not controls]":
            target = allowed
            continue
        if isinstance(target, list):
            target.append(line)
        else:
            target.add(line)
    return controls, allowed


def test_t4_every_listed_control_is_a_label_in_the_app():
    """DL-5: the README quoted "Save Budget Limits", "Reset Session Spend",
    "Clear All", "Format + Export Book" and "Scenes / Chapters"; none of them is
    on screen. Every phrase on the list must be a string literal in the app
    (case-sensitive; a label with an ellipsis or a count may contain it)."""
    controls, _ = _controls()
    assert len(controls) >= 100, "the control list looks truncated"
    missing = [phrase for phrase in controls if not _in_app(phrase)]
    assert not missing, "quoted in the docs, not in the app:\n" + "\n".join(missing)


def _lessons_with_atlas() -> list[Path]:
    return [p for p in sorted((LEARN / "modules").glob("*.md"))
            if re.search(r"^## Control atlas", p.read_text(encoding="utf-8"), re.M)]


@pytest.mark.parametrize("path", _lessons_with_atlas(), ids=_rel)
def test_t4_bold_phrases_in_a_control_atlas_are_listed(path):
    """A bold word in a lesson's control atlas is either a control (and so on
    the list, and so checked against the app) or explicitly not one."""
    controls, allowed = _controls()
    known = set(controls) | allowed
    atlas = _section(path.read_text(encoding="utf-8"), r"^Control atlas$")
    unknown = [p for p in _bold(_visible(atlas)) if p not in known]
    assert not unknown, (f"{_rel(path)}: add each to tests/docs_controls.txt "
                         f"(control or [not controls]): {unknown}")


# README sections whose bold phrases name controls (review R-3).
_T4_README_SECTIONS = ("3", "4", "5", "6", "7", "13")
_GLYPH = re.compile(r"^[^\w\[(\"'“]+\s*")
_LABEL_SEPARATORS = ("…", "...", ":", " —", " (", " –")

# Label-like bold phrases that are not, today, a label in the app: each is a
# doc naming a control differently from the panel, or naming one that is not
# there. Found while widening T4 (review R-3); fixed in the name pass or by
# hand, and then this list shrinks (strict: a fixed entry fails the suite).
_T4_SUSPECTED_DRIFT = frozenset({
    "BEST AVAILABLE",    # lessons 12 and 18; no such badge text in the code
    "Free-form",         # README 7.4, as a Quill task group; no such label
    "Last decision",     # README 5, a rail row; no such label
    "Publishing Todos",  # README 7.5; only inside a status sentence
})


def _t4_scopes() -> list[tuple[str, str]]:
    readme = _visible(README.read_text(encoding="utf-8"))
    scopes = [(f"README.md section {n}", _section(readme, rf"^{n}\.\s"))
              for n in _T4_README_SECTIONS]
    for path in sorted(SHEETS.glob("*.md")) + sorted((LEARN / "modules").glob("*.md")):
        scopes.append((_rel(path), _visible(path.read_text(encoding="utf-8"))))
    return scopes


def _label_like(phrase: str) -> bool:
    """A bold phrase that could be a control's label. Not checked, because no
    string test can tell them apart: run-in headings and sentences (ending in
    ``:``, ``.``, ``;`` or ``,``, or over five words), quoted messages (they
    are T4's list or Troubleshooting's job), and composed names: several
    controls in one (``/``, ``+``, ``→``) or a label with a placeholder
    (``<model>``, ``N``, ``…`` inside). Plain-text (unbolded) quotes of a label
    are not checked either: nothing marks them as a label."""
    if phrase.endswith((":", ".", ";", ",")) or len(phrase.split()) > 5:
        return False
    if any(mark in phrase for mark in ('"', "“", "/", "+", "→", "<")):
        return False
    if re.search(r"\bN\b", phrase) or "…" in phrase.rstrip("…"):
        return False
    return bool(re.search(r"[A-Za-z]", phrase))


@lru_cache(maxsize=1)
def _app_labels() -> frozenset[str]:
    # Qt shows "&&" in a label as "&" ("Songs && Albums").
    return frozenset(_normalise(s.replace("&&", "&")) for s in _app_strings())


def _is_app_label(phrase: str) -> bool:
    """Whole-literal match: the phrase is a literal, or a literal starts with
    it followed by an ellipsis, a colon or an explanation ("Not rated yet —
    ranked below rated models"). A phrase of three words or more may also sit
    inside a longer literal at word boundaries (a quoted status line)."""
    wanted = _normalise(_GLYPH.sub("", phrase))
    if wanted in _app_labels() or wanted.rstrip(".:").strip() in _app_labels():
        return True
    starts = tuple(wanted + sep for sep in _LABEL_SEPARATORS)
    if any(s.startswith(starts) for s in _app_labels()):
        return True
    if len(wanted.split()) >= 3:
        pattern = re.compile(r"(?<!\w)" + re.escape(wanted) + r"(?!\w)")
        return any(pattern.search(s) for s in _app_labels())
    return False


def _t4_unknown() -> dict[str, set[str]]:
    controls, allowed = _controls()
    known = set(controls) | allowed
    found: dict[str, set[str]] = {}
    for where, text in _t4_scopes():
        for phrase in _bold(text):
            if (_label_like(phrase) and phrase not in known
                    and not _is_app_label(phrase)):
                found.setdefault(phrase, set()).add(where)
    return found


def test_t4_label_like_bold_phrases_are_app_labels():
    """DL-5 again, outside the control atlas (review R-3): README sections 3
    to 7 and 13, every agent sheet and every lesson. A label-like bold phrase
    is a whole label in the app, on the control list, or listed under
    ``[not controls]``; "Save Budget Limits" for "Save Limits" fails here."""
    unknown = {p: w for p, w in _t4_unknown().items() if p not in _T4_SUSPECTED_DRIFT}
    assert not unknown, ("bold phrase is no label in the app; fix the doc, or add it "
                         "to tests/docs_controls.txt [not controls]:\n"
                         + "\n".join(f"{p!r} in {sorted(w)}" for p, w in sorted(unknown.items())))


@pytest.mark.xfail(strict=True, reason="docs name controls the app labels differently (R-3)")
def test_t4_suspected_label_drift_is_fixed():
    still = sorted(p for p in _T4_SUSPECTED_DRIFT if p in _t4_unknown())
    assert not still, f"still not app labels: {still}"


def test_t4_troubleshooting_quotes_text_the_app_shows():
    """Review R-4: each Troubleshooting entry starts with the message as the
    app shows it. Every piece of a quoted message between ellipses (the
    variable parts) must be in an app string that is not a docstring."""
    text = _visible((LEARN / "modules" / "17-troubleshooting.md").read_text(encoding="utf-8"))
    wrong = []
    for phrase in _bold(text):
        for quoted in re.findall(r'"([^"]+)"', phrase):
            for piece in re.split(r"…|\.\.\.", quoted):
                piece = piece.strip(" '.")
                if len(piece) > 3 and not _in_app(piece):
                    wrong.append(piece)
    assert not wrong, f"quoted in Troubleshooting, not shown by the app: {wrong}"


def test_t4_suspected_drift_list_has_no_stale_entries():
    """An entry that is fixed, or no longer in the docs, comes off the list."""
    stale = sorted(_T4_SUSPECTED_DRIFT - set(_t4_unknown()))
    assert not stale, f"remove from _T4_SUSPECTED_DRIFT: {stale}"


@pytest.mark.xfail(strict=True, reason=PACKAGE_5)
def test_t4_stamp_sheet_field_labels_match_the_panel():
    """DL-18: the Stamp sheet names four fields differently from the panel
    (``agents/fiverr/panel.py``). Fixed with the rename, in one pass over that
    sheet."""
    text = (SHEETS / "fiverr.md").read_text(encoding="utf-8")
    stale = [label for label in ("Business Name", "Primary Colors",
                                 "# Concepts", "Delivery Msg") if label in text]
    assert not stale, stale


# ── T5: retired names ──────────────────────────────────────────────────────

RETIRED_NAMES = ("Atelier", "Maestro", "Publisher Agent", "Narrator Agent",
                 "Left-panel button", "Client Gigs", "Site Builder")

# README sections whose agent changes its name in the rename (package 5):
# 7.1 Chat, 7.2 Stamp, 7.11 Muse. Their old headings stay until then.
_README_PACKAGE_5 = (r"^7\.1 ", r"^7\.2 ", r"^7\.11 ")


def _readme_without_package5() -> str:
    text = _visible(README.read_text(encoding="utf-8"))
    for pattern in _README_PACKAGE_5:
        body = _section(text, pattern)
        text = text.replace(body, "\n" * body.count("\n"))
    # Their headings, and the contents entries that link to them.
    return "\n".join(
        "" if re.search(r"\(#7(1|2|11)-", line)
        or re.match(r"^### 7\.(1|2|11) ", line) else line
        for line in text.splitlines())


def _retired_hits(text: str, label: str) -> list[str]:
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        for name in RETIRED_NAMES:
            if re.search(rf"\b{re.escape(name)}\b", line):
                hits.append(f"{label}:{number} {name!r}")
    return hits


def test_t5_no_retired_agent_names_in_the_readme():
    """DL-1: sections 6 and 7 described seven agents in a left panel, under
    names retired in September. Sections 7.1, 7.2 and 7.11 are checked by the
    next test, after the rename."""
    hits = _retired_hits(_readme_without_package5(), "README.md")
    assert not hits, "\n".join(hits)


@pytest.mark.xfail(strict=True, reason=PACKAGE_5)
def test_t5_no_retired_agent_names_in_readme_sections_7_1_7_2_7_11():
    text = _visible(README.read_text(encoding="utf-8"))
    hits = []
    for pattern in _README_PACKAGE_5:
        heading = next(line for line in text.splitlines()
                       if re.match(r"^### " + pattern[1:], line))
        hits += _retired_hits(heading + "\n" + _section(text, pattern),
                              f"README {pattern}")
    assert not hits, "\n".join(hits)


_T5_PACKAGE_5_FILES = {"agents/fiverr/README.md", "docs/agents/fiverr.md",
                       "docs/learn/modules/02-choose-path.md",
                       "docs/learn/modules/14-costs-limits.md",
                       "docs/learn/modules/26-site-builder.md",
                       "docs/learn/modules/27-client-gigs.md"}


def _t5_params():
    for path in USER_DOCS:
        if path == README:
            continue
        yield (_package5(path) if _rel(path) in _T5_PACKAGE_5_FILES
               else pytest.param(path))


@pytest.mark.parametrize("path", list(_t5_params()), ids=_rel)
def test_t5_no_retired_agent_names_in_user_docs(path):
    """DL-9: lessons still call Sitebuilder "Site Builder" and Stamp "Client
    Gigs". Extends ``test_retired_names.py`` (a retired venture) to the retired
    agent names."""
    hits = _retired_hits(_visible(path.read_text(encoding="utf-8")), _rel(path))
    assert not hits, "\n".join(hits)


# ── T6: titles equal the catalog labels ────────────────────────────────────

def _labels() -> dict[str, str]:
    from agents.catalog import AGENT_SPECS
    return {spec.key: spec.label for spec in AGENT_SPECS}


def _first_heading(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def test_t6_manifest_titles_equal_the_catalog_labels():
    labels = _labels()
    wrong = []
    lessons = json.loads((LEARN / "manifest.json").read_text(encoding="utf-8"))
    for entry in lessons["modules"]:
        if entry["section"] == "agents" and entry["title"] != labels[entry["agent"]]:
            wrong.append(f"lesson {entry['id']}: {entry['title']!r}")
    sheets = json.loads((SHEETS / "manifest.json").read_text(encoding="utf-8"))
    for entry in sheets["pages"]:
        if entry.get("agent") and entry["title"] != labels[entry["agent"]]:
            wrong.append(f"sheet {entry['id']}: {entry['title']!r}")
    assert not wrong, "\n".join(wrong)


def _titled_files() -> list:
    lessons = json.loads((LEARN / "manifest.json").read_text(encoding="utf-8"))
    sheets = json.loads((SHEETS / "manifest.json").read_text(encoding="utf-8"))
    labels = _labels()
    rows = [(LEARN / e["filename"], labels[e["agent"]])
            for e in lessons["modules"] if e["section"] == "agents"]
    rows += [(SHEETS / e["filename"], labels[e["agent"]])
             for e in sheets["pages"] if e.get("agent")]
    params = []
    for path, label in rows:
        ok = _first_heading(path).startswith(label)
        # Today's mismatches are the rename's (package 5); new ones are bugs.
        params.append(_package5(path, label) if not ok and _rel(path) in _T6_KNOWN
                      else pytest.param(path, label))
    return params


_T6_KNOWN = {
    "docs/learn/modules/20-draft.md", "docs/learn/modules/21-publish.md",
    "docs/learn/modules/22-audiobooks.md", "docs/learn/modules/23-music.md",
    "docs/learn/modules/24-video.md", "docs/learn/modules/25-social.md",
    "docs/learn/modules/26-site-builder.md", "docs/learn/modules/27-client-gigs.md",
    "docs/agents/author.md", "docs/agents/manuscript.md", "docs/agents/audiobook.md",
    "docs/agents/music.md", "docs/agents/video.md", "docs/agents/social.md",
    "docs/agents/webdesign.md", "docs/agents/fiverr.md", "docs/agents/chat.md",
    "docs/agents/creator.md", "docs/agents/router.md",
}


@pytest.mark.parametrize("path,label", _titled_files(),
                         ids=lambda v: _rel(v) if isinstance(v, Path) else "")
def test_t6_first_heading_starts_with_the_catalog_label(path, label):
    """DL-9, DL-18: the contents list said "Quill", the lesson "Draft", the
    sheet "BOOK AUTHOR"."""
    assert _first_heading(path).startswith(label), (
        f"{_rel(path)}: {_first_heading(path)!r} should start with {label!r}")


# ── T7: income wording ─────────────────────────────────────────────────────

def _tracked_docs() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z", "-co", "--exclude-standard", "*.md"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    # Audits and specs quote the findings they record; history is history.
    skip = ("docs/audit/", "docs/specs/", "docs/history/", "docs/legal/",
            "docs/playbooks/", "CHANGELOG.md")
    return [ROOT / name for name in out.split("\0")
            if name and not name.startswith(skip) and (ROOT / name).exists()]


_INCOME = (
    re.compile(r"passive income", re.I),
    re.compile(r"realistic (?:monthly )?earnings", re.I),
    re.compile(r"\btop sellers\b", re.I),
    # A money amount or range per month: "$400–$2,000/month", "$5k/mo".
    re.compile(r"\$\s?\d[\d,.]*k?(?:\s*(?:–|-|to)\s*\$?\s?\d[\d,.]*k?)?\s*"
               r"(?:/|per |a )\s*(?:month|mo)\b", re.I),
)


def test_t7_no_income_wording_in_any_tracked_doc():
    """DL-7, DL-8: a hidden README chapter stated earnings as fact, and Label's
    package README projected streaming payouts the prompt forbids. Comments
    count: the repo is public and the raw file shows them."""
    hits = []
    for path in _tracked_docs():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(p.search(line) for p in _INCOME):
                hits.append(f"{_rel(path)}:{number}: {line.strip()[:90]}")
    assert not hits, "income wording:\n" + "\n".join(hits)


def test_t7_label_readme_does_not_project_payouts():
    text = (ROOT / "agents" / "music" / "README.md").read_text(encoding="utf-8")
    assert not re.search(r"\$0\.00\d\s*[–-]\s*\$0\.00\d", text), (
        "agents/music/README.md quotes a per-stream payout range; the prompt "
        "forbids it (agents/music/agent.py)")


# ── T8: local paths ────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", USER_DOCS + [ROOT / "CHANGELOG.md"], ids=_rel)
def test_t8_no_local_user_path_in_a_doc(path):
    """DL-2: the README sent readers to a folder on the owner's Mac, and
    published that folder's name in a public repo. Scope is the user docs
    (``USER_DOCS``); ``TODO.md``, ``config/`` and older audits are not checked
    and still carry such paths (review R-8, TODO QM rows)."""
    hits = [f"{_rel(path)}:{n}" for n, line in
            enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if "/Users/" in line]
    assert not hits, "\n".join(hits)


# ── T9: limitation sections ────────────────────────────────────────────────

_T9_PACKAGE_5 = {"chat.md", "creator.md", "fiverr.md"}


@pytest.mark.parametrize(
    "path",
    [_package5(p) if p.name in _T9_PACKAGE_5 else pytest.param(p)
     for p in sorted(SHEETS.glob("*.md"))],
    ids=_rel)
def test_t9_every_sheet_has_a_deliberate_limitations_section(path):
    """DL-14 (audit QB-5): ``overview.md`` promises the section on every sheet."""
    text = path.read_text(encoding="utf-8")
    assert re.search(r"^#{2,3} Deliberate limitations\b", text, re.M), _rel(path)


# ── T10: Settings tabs and permission boxes ────────────────────────────────

def _settings_tabs() -> list[str]:
    tree = ast.parse((ROOT / "ui" / "dialogs.py").read_text(encoding="utf-8"))
    for func in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        names = []
        for call in (n for n in ast.walk(func) if isinstance(n, ast.Call)):
            f = call.func
            if (isinstance(f, ast.Attribute) and f.attr == "addTab"
                    and isinstance(f.value, ast.Name) and f.value.id == "tabs"
                    and len(call.args) == 2 and isinstance(call.args[1], ast.Constant)):
                names.append((call.lineno, call.args[1].value))
        if any(name == "API keys" for _, name in names):
            return [name for _, name in sorted(names)]
    raise AssertionError("Settings dialog not found in ui/dialogs.py")


def test_t10_readme_lists_the_settings_tabs_the_dialog_builds():
    """DL-3: the README said five tabs; the dialog builds eight."""
    section = _section(_visible(README.read_text(encoding="utf-8")), r"^13\.3 Settings")
    documented = [m.group(1) for m in
                  re.finditer(r"^#### (.+?) tab\s*$", section, re.M | re.I)]
    assert documented == _settings_tabs()


def _permission_chips() -> list[str]:
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    return re.findall(r"self\.allow_\w+_checkbox = toggle_chip\(\"([^\"]+)\"", text)


def test_t10_readme_lists_every_permission_box():
    """DL-4: the README listed three provider boxes; the app has eight."""
    chips = _permission_chips()
    assert len(chips) == 8, chips
    section = _section(_visible(README.read_text(encoding="utf-8")), r"^6\.3 ")
    missing = [chip for chip in chips if f"**{chip}**" not in section]
    assert not missing, f"README 6.3 does not list: {missing}"
