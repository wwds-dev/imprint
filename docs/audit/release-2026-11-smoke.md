# Release smoke test: November release train (v2.509, 2026-11-24)

Released specs: audit-p1-billing, dashscope-workspace-id, deps-security-upgrade-2026-10,
quill-draft-safety, docs-learning-centre-readiness, local-model-routing, rename-imprint-studio,
ai-act-safeguards (owner's Release gate: "Yes, release"). Not released: model-updates (reason in
TODO). Code identical to `7cd1aa4` (full suite 2994 passed, 0 failed); main at `9fe1e62`.

Checklist (app-context `## Commands`, "Release smoke checklist"):
- Legal gate: clear; owner sign-off 2026-11-24 18:13, pack `b0ae06bd71ca` (foundry `82cfa98`);
  `release_check.py .`: "clear: Release may start".
- Install: `./scripts/install_app.sh` (live launcher into the main checkout); stamped v2.508 at
  `672f4ad`, re-stamped v2.509 at `9fe1e62` after the release-log commit.
- Self-test: `main.py --selftest` 16/16 PASS (data dir, registry, vidforge, resources, ratings
  snapshot, AppKit guard). The launcher's `--selftest` printed nothing (exit 0): its output is not
  forwarded; noted, not investigated.
- Launch: process named "Imprint Studio"; window shows "IMPRINT STUDIO" and the version badge.
- One agent action (free, no paid request): Audio + Music workspace, Booth opened with its
  Convert form.
- Quit from the app menu: exited cleanly within 15 s. Relaunch: window back, badge v2.509.
- DB and projects intact: `data/imprint.db` opened by both launches; the projects table held 0
  rows before and the UI shows "All projects" with saved chats listed after relaunch.
- CI on `9fe1e62`, `672f4ad`, `ee4fff8`: quality and security green (reported by the parent
  session).

Not verified: a paid agent request (needs the owner's yes), a frozen `.app` build (not shipped;
`licences.md` §3 bundle steps first), `tests/manual_test_cases.md` UAT.
