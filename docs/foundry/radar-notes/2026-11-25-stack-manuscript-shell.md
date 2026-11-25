# Radar check: stack, manuscript-redesign slice 1 (shell) (2026-11-25)

Scope: before Architect for slice 1 of `manuscript-redesign`: `Qt.Popup` frames vs `QMenu` on
macOS 27, reading macOS Reduce Motion, a sliding drawer (`QPropertyAnimation`), a light palette
beside dark ones. Three searches, no fetches. Builds on today's Define note
(`2026-11-25-define-manuscript-redesign.md`), which is not repeated here. Pinned:
`PySide6==6.11.2` (`requirements.txt:35`). PyObjC is not installed (`import AppKit` fails in
`.venv`); `ui/appkit_guard.py` already reaches AppKit through `ctypes` and `libobjc`.

| Finding | Source | Impact | Recommendation | Approval |
|---|---|---|---|---|
| `NSWorkspace.sharedWorkspace.accessibilityDisplayShouldReduceMotion` (macOS 10.12+) is the setting; change notice `NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification` goes to NSWorkspace's own notification center. Browsers check `respondsToSelector:` first and default to "motion allowed" when absent. Mozilla notes the value can be stale without a native event loop, so re-read it rather than cache it. | [Chromium `animation_mac.mm`](https://chromium.googlesource.com/chromium/src/+/923016306b416e430bf8eb25a6a36c703e836e0b/ui/gfx/animation/animation_mac.mm); [Mozilla bug 1702602](https://bugzilla.mozilla.org/show_bug.cgi?id=1702602); [gist (2021)](https://gist.github.com/dagronf/8c3e1dcc0f8175365f3055bacd9c99fa) | P2 | adopt: read it through `ctypes` (same pattern as `appkit_guard`, no new dependency), re-read on app activation instead of observing the notification (a block observer through `ctypes` is fragile) | none (no dependency); the mechanism is in the Architect gate |
| `Qt.Popup` widgets on macOS: all mouse and key input goes to the open popup; a `QLineEdit` inside a popup gets no right-click context menu (QTBUG-133560, open for 6.7/6.8); clicks on another window's title bar may not close it (QTBUG-30312, old). | [QTBUG-133560](https://bugreports.qt.io/browse/QTBUG-133560); [QTBUG-96449](https://bugreports.qt.io/browse/QTBUG-96449); [QTBUG-30312](https://bugreports-test.qt.io/browse/QTBUG-30312) | P3 | adopt with care: the spend popover's limit fields lose their context menu (no copy/paste menu; ⌘C/⌘V still work). Close on window deactivation explicitly. Verify on a native render | none |
| `QStyleHints.setColorScheme` (Qt 6.8+) overrides the system scheme, best effort per platform; explicit app palette entries are kept. Lets native dialogs (file pickers, message boxes) follow Light while macOS is in Dark mode. | [QStyleHints (Qt 6.11)](https://doc.qt.io/qt-6.11/qstylehints.html); [QTBUG-124490](https://bugreports.qt.io/browse/QTBUG-124490) | P3 | adopt as optional in Build: call it on a Look change; confirm on a native render | none |

## Checked, nothing new
- No new advisory on PySide6 6.11.2 since today's Define note.
- No library worth adding for popovers, drawers or motion: `QFrame` with `Qt.Popup`, `QMenu` and
  `QVariantAnimation` cover the scope.
