# Radar check: define, manuscript-redesign (2026-11-25)

Scope: Imprint UI shell redesign in PySide6 (light theme, icon rail, top-bar stepper, focus
mode, small animations; layout checks on a native macOS render). Three searches, no fetches.
Pinned: `PySide6==6.11.2` (`requirements.txt:35`). The app uses no Qt animation class today
(`git grep QPropertyAnimation|QVariantAnimation|QTimeLine` is empty) and no `colorScheme` call;
from QtNetwork it uses only `QLocalServer` / `QLocalSocket` (`main.py:49`).

| Finding | Source | Impact | Recommendation | Approval |
|---|---|---|---|---|
| Qt exposes no API to read the platform's "Reduce motion" setting; an open request asks for one. Any moving gimmick (Booth bars, ring fill, spine fill, preview reshape) must read macOS's setting another way (e.g. `NSWorkspace.accessibilityDisplayShouldReduceMotion` through PyObjC, or an in-app switch) or not move at all. | [QTBUG-133042](https://bugreports.qt.io/browse/QTBUG-133042); Apple, [Change Motion settings](https://support.apple.com/guide/mac-help/mchla3c4f1da/mac) | P2 | adopt as a spec requirement (motion off when the user asks for less); the mechanism is Architect's | owner, at the Define gate (question on the 2026-10-06 calm rule) |
| Light theme: Qt 6.8+ lets an app set its own colour scheme (`QStyleHints.setColorScheme`), so native dialogs and the cocoa style can follow a light palette instead of the system's dark mode. Not re-verified this run (from known Qt 6.8 docs). | [What's New in Qt 6.11](https://doc.qt.io/QT-6/whatsnew611.html) (no scheme change in 6.11) | P3 | watch; Architect confirms on 6.11.2 with a native render | none now |
| PySide6 6.11.x: 6.11.1 and 6.11.2 are bug-fix releases; nothing in them on styling. | [PySide6 6.11 release notes](https://doc.qt.io/qtforpython-6.11/release_notes/pyside6_release_notes.html) | none | skip | none |
| Qt 2026 advisories fixed in Qt 6.11.3 / 6.12.1 are in Qt Network HTTP, QWebSocket, NTLM and Qt XML. Imprint uses none of those from Qt (only local sockets). Outside this redesign's scope; belongs to the next `upgrade` radar. | [Qt known vulnerabilities](https://wiki.qt.io/List_of_known_vulnerabilities_in_Qt_products); [Qt security blog](https://qt.io/blog/tag/security) | P3 | watch (next dependency upgrade) | owner, at that upgrade |
| A Fedora advisory lists python-pyside6 6.11.2 under a CVE whose text cites a libxml2 bug; the tag and package do not clearly match. Distro packaging, not the PyPI wheel. | [Fedora advisory via linuxsecurity.com](https://linuxsecurity.com/advisories/fedora/python-pyside6-fedora-2026-91259c13b9) | P3 | watch; not verified | none |

## Checked, nothing new
- No better-fitting toolkit or library for this scope: the redesign is restyling and re-parenting
  existing PySide6 widgets; Qt Labs StyleKit (new in 6.11) is for Qt Quick, not Widgets, so it does
  not apply to this app.
- No change to the request guard's surface: the redesign adds no paid path.
