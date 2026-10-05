"""Structured export and pre-export validation for the Site Builder.

The panel used to hand over one HTML blob. `split_project` turns it into
the files a real handoff expects — index.html referencing an extracted
stylesheet and script — and `validate` runs the static HTML/accessibility
checks a client would fail the delivery on. Both are heuristics over text,
not a browser: they catch the common failures (missing alt text, unlabeled
inputs, no doctype, duplicate ids), and the panel says "checks", never
"compliance". Qt-free on purpose.
"""

import re
from dataclasses import dataclass

_INLINE_STYLE = re.compile(r"[ \t]*<style[^>]*>(.*?)</style>\s*",
                           re.DOTALL | re.IGNORECASE)
# Only inline scripts move to script.js — a <script src=…> already IS a file
# reference and must stay where it is.
_INLINE_SCRIPT = re.compile(r"[ \t]*<script(?![^>]*\bsrc\s*=)[^>]*>(.*?)"
                            r"</script>\s*", re.DOTALL | re.IGNORECASE)


def split_project(full_html: str) -> dict[str, str]:
    """One blob -> {filename: content}; css/js files only when non-empty."""
    styles = [m.strip() for m in _INLINE_STYLE.findall(full_html) if m.strip()]
    scripts = [m.strip() for m in _INLINE_SCRIPT.findall(full_html)
               if m.strip()]
    html = _INLINE_STYLE.sub("", full_html)
    html = _INLINE_SCRIPT.sub("", html)

    files: dict[str, str] = {}
    if styles:
        files["styles.css"] = "\n\n".join(styles) + "\n"
        link = '    <link rel="stylesheet" href="styles.css">\n'
        if re.search(r"</head>", html, re.IGNORECASE):
            html = re.sub(r"</head>", link + "</head>", html, count=1,
                          flags=re.IGNORECASE)
        else:
            html = link + html
    if scripts:
        files["script.js"] = "\n\n".join(scripts) + "\n"
        tag = '    <script src="script.js" defer></script>\n'
        if re.search(r"</body>", html, re.IGNORECASE):
            html = re.sub(r"</body>", tag + "</body>", html, count=1,
                          flags=re.IGNORECASE)
        else:
            html = html + "\n" + tag
    files["index.html"] = html
    return files


@dataclass(frozen=True)
class Finding:
    level: str      # "error" | "warning"
    message: str


def validate(html: str) -> list[Finding]:
    """Static HTML and accessibility checks on the generated page."""
    findings: list[Finding] = []
    lowered = html.lower()

    def error(message):
        findings.append(Finding("error", message))

    def warn(message):
        findings.append(Finding("warning", message))

    if not lowered.lstrip().startswith("<!doctype"):
        error("Missing <!DOCTYPE html> — browsers fall back to quirks mode.")
    html_tag = re.search(r"<html\b[^>]*>", html, re.IGNORECASE)
    if html_tag and not re.search(r"\blang\s*=", html_tag.group(0),
                                  re.IGNORECASE):
        error("<html> has no lang attribute — screen readers guess the "
              "language.")
    title = re.search(r"<title[^>]*>(.*?)</title>", html,
                      re.DOTALL | re.IGNORECASE)
    if not title or not title.group(1).strip():
        error("Missing or empty <title>.")
    if "viewport" not in lowered:
        warn("No viewport meta tag — the page will not scale on phones.")

    for img in re.finditer(r"<img\b[^>]*>", html, re.IGNORECASE):
        if not re.search(r"\balt\s*=", img.group(0), re.IGNORECASE):
            error(f"<img> without alt text: {img.group(0)[:60]}…")

    labelled_ids = set(re.findall(r"<label[^>]*\bfor\s*=\s*[\"']([^\"']+)",
                                  html, re.IGNORECASE))
    for tag in re.finditer(r"<(input|select|textarea)\b[^>]*>", html,
                           re.IGNORECASE):
        text = tag.group(0)
        if re.search(r"\btype\s*=\s*[\"'](hidden|submit|button)", text,
                     re.IGNORECASE):
            continue
        has_aria = re.search(r"\baria-label(ledby)?\s*=", text, re.IGNORECASE)
        id_match = re.search(r"\bid\s*=\s*[\"']([^\"']+)", text,
                             re.IGNORECASE)
        has_label = id_match and id_match.group(1) in labelled_ids
        if not has_aria and not has_label:
            error(f"Form control without a label or aria-label: "
                  f"{text[:60]}…")

    for anchor in re.finditer(r"<a\b[^>]*>(.*?)</a>", html,
                              re.DOTALL | re.IGNORECASE):
        inner = re.sub(r"<[^>]+>", "", anchor.group(1)).strip()
        if not inner and not re.search(r"\baria-label\s*=",
                                       anchor.group(0), re.IGNORECASE):
            warn("Link with no text and no aria-label.")

    ids = re.findall(r"\bid\s*=\s*[\"']([^\"']+)", html, re.IGNORECASE)
    for duplicate in sorted({i for i in ids if ids.count(i) > 1}):
        error(f'Duplicate id "{duplicate}".')

    headings = [int(m) for m in re.findall(r"<h([1-6])\b", html,
                                           re.IGNORECASE)]
    if headings:
        if 1 not in headings:
            warn("No <h1> on the page.")
        for previous, current in zip(headings, headings[1:]):
            if current > previous + 1:
                warn(f"Heading level jumps from h{previous} to h{current}.")
                break
    return findings
