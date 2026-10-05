"""Site Builder: multi-file export and the pre-export checks.

Contract: one blob splits into index.html + styles.css + script.js with
references injected (inline-only; a <script src=…> stays put, and empty
files are not written); the validator catches the common HTML/a11y
failures and passes a clean page; both export paths run the checks and
the user — not the tool — decides whether findings block the handoff.
"""

import os

import pytest

from agents.webdesign.export import split_project, validate

CLEAN = """<!DOCTYPE html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Acme</title>
<style>body { margin: 0; }</style>
</head>
<body>
<h1>Acme</h1>
<h2>About</h2>
<img src="a.png" alt="The Acme logo">
<label for="email">Email</label><input id="email" type="email">
<a href="/x">Read more</a>
<script src="https://cdn.example/lib.js"></script>
<script>console.log("hi");</script>
</body>
</html>"""


def test_split_extracts_inline_assets_and_injects_references():
    files = split_project(CLEAN)
    assert set(files) == {"index.html", "styles.css", "script.js"}
    assert "body { margin: 0; }" in files["styles.css"]
    assert 'console.log("hi");' in files["script.js"]
    html = files["index.html"]
    assert '<link rel="stylesheet" href="styles.css">' in html
    assert '<script src="script.js" defer></script>' in html
    assert "console.log" not in html            # inline moved out
    assert "cdn.example/lib.js" in html         # src-script stays put
    assert "<style" not in html.lower()


def test_split_omits_empty_asset_files():
    files = split_project("<!DOCTYPE html><html lang='en'><head>"
                          "<title>x</title></head><body><h1>x</h1>"
                          "</body></html>")
    assert set(files) == {"index.html"}


def test_validator_passes_a_clean_page():
    assert validate(CLEAN) == []


@pytest.mark.parametrize("mutation, expected", [
    (lambda h: h.replace("<!DOCTYPE html>\n", ""), "DOCTYPE"),
    (lambda h: h.replace(' lang="en"', ""), "lang"),
    (lambda h: h.replace("<title>Acme</title>", "<title></title>"), "title"),
    (lambda h: h.replace(' alt="The Acme logo"', ""), "alt"),
    (lambda h: h.replace('<label for="email">Email</label>', ""), "label"),
    (lambda h: h.replace('id="email"', 'id="dup"').replace(
        "<h1>Acme</h1>", '<h1 id="dup">Acme</h1>'), "Duplicate id"),
    (lambda h: h.replace(
        '<meta name="viewport" content="width=device-width, '
        'initial-scale=1">\n', ""), "viewport"),
    (lambda h: h.replace("<h2>About</h2>", "<h4>About</h4>"), "jumps"),
])
def test_validator_catches_each_failure(mutation, expected):
    findings = validate(mutation(CLEAN))
    assert any(expected.lower() in f.message.lower() for f in findings), \
        [f.message for f in findings]


# ── panel wiring ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_export_project_writes_the_files(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from tests.test_webdesign_panel import FakeHost
    from agents.webdesign import WebdesignPanel

    panel = WebdesignPanel(FakeHost())
    try:
        panel.last_response = f"```html\n{CLEAN}\n```"
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory",
            staticmethod(lambda *a, **k: str(tmp_path)))
        panel.export_project()
        (folder,) = list(tmp_path.iterdir())
        names = sorted(p.name for p in folder.iterdir())
        assert names == ["index.html", "script.js", "styles.css"]
        assert "Exported 3 file(s)" in panel.webdesign_status_label.text()
    finally:
        panel.deleteLater()


def test_findings_gate_export_on_the_users_choice(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from tests.test_webdesign_panel import FakeHost
    from agents.webdesign import WebdesignPanel

    broken = CLEAN.replace(' alt="The Acme logo"', "")
    panel = WebdesignPanel(FakeHost())
    try:
        panel.last_response = broken
        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(lambda *a, **k: QMessageBox.No))
        called = []
        monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                            staticmethod(lambda *a, **k: called.append(1)
                                         or str(tmp_path)))
        panel.export_project()
        assert called == []                      # declined: no dialog, no files
        assert "cancelled" in panel.webdesign_status_label.text()

        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(lambda *a, **k: QMessageBox.Yes))
        panel.export_project()
        assert called and list(tmp_path.iterdir())   # chose to export anyway
    finally:
        panel.deleteLater()
