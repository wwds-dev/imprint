# Tooling baseline (Imprint)

Date: 2026-10-12. Measured report-only; no application source, tests or existing config were touched.

## Added files
`ruff.toml`, `.gitleaks.toml`, `.githooks/pre-commit` (executable, not activated), `.github/dependabot.yml`
(pip `/`, `/vidforge`, `/cloud`, github-actions), `.github/workflows/quality.yml`, `.github/workflows/security.yml`,
`docs/company/tooling/` (incl. `baseline.json`, which must be committed with the rest), this file.

## Measurements
| Check | Command | Result |
|---|---|---|
| Lint | `uvx ruff check --no-cache --quiet --output-format=concise --exit-zero .` | **189** findings (98 in `main.py`); recorded in `baseline.json` as `ruff: 189`. Rules: E4, E7, E9, F, B. `vidforge/` and `cloud/` are first-party tracked code, so they are not excluded. |
| Secrets, history | `gitleaks detect --redact -c .gitleaks.toml` (gitleaks 8.30.1) | 220 commits, **2 findings**, rule `generic-api-key`, in `services/database.py` and `tests/test_settings_pricing.py` (commit 83343104). Same false-positive family as the pinned `.gitleaksignore` entries (quoted settings keys), but the existing fingerprints do not match this commit. Owner to confirm they are not real, then re-pin or rewrite; do not allowlist in `.gitleaks.toml` without approval. |
| Secrets, working tree | scratch config (outside the repo) excluding `_to_delete/`, `build/`, `dist/`, `.venv`, caches, `.env` | 3 findings, rule `generic-api-key`: `services/database.py` (2 lines), `tests/test_settings_pricing.py`. Likely the same false positives. |
| Secrets, `.env` | gitleaks on the single file | no leaks found (gitignored file). |
| Dependency audit | `uvx pip-audit -r requirements.txt` | **Cannot run as is**: `requirements.txt` has unpinned lines (`anthropic`, `python-pptx`, `PySide6`, `google-genai`, `psutil`, `python-docx`, `reportlab`, `PyYAML`, `google-api-python-client`, `google-auth-oauthlib`) and pip-audit refuses them. Pinned subset only (30 lines, `--no-deps --disable-pip`): **93 advisories in 7 packages**: pypdf 6.10.0 (49), pillow 12.2.0 (25), urllib3 2.6.3 (7), soupsieve 2.8.3 (6), anyio 4.13.0 (2), idna 3.11 (2), lxml 6.0.4 (2). Transitive and unpinned packages are not covered. |
| Tests | `.venv/bin/python -m coverage run ... -m pytest -q` capped at 120 s | Did not finish in 120 s under coverage (about 35% done, no failures seen up to that point). |
| Coverage | | **UNVERIFIED**. Floor: none, so `quality.yml` has no coverage-floor step. It still writes coverage data. |

## UNVERIFIED
- Coverage and the full-suite result with coverage (needs a longer cap, about 3 to 5 minutes).
- Whether the CI install succeeds on `macos-latest` (nothing was run on GitHub); PySide6 is unpinned.
- The README's `~90 s` suite time is not reproduced under coverage.

## Contradictions with `app-context.md`
- It says no `.github` exists; it now does (added by this run, nothing earlier).
- `.venv` has no `coverage` installed (CI installs it; I used a temp `--target` dir, since removed).
- No `client_secret*.json` exists anywhere in the working tree (only openai SDK files under ignored `dist/` match the name), so there is no OAuth secret file to report.

## Notes
- The repo's default branch is `main`; workflows trigger on all pushes and PRs, so no mismatch.
- `quality.yml` runs on macOS for the tests (PySide6) and ubuntu for the lint ratchet.
- `security.yml` blocks on any gitleaks finding, so the 2 history findings above will turn it red until resolved.
