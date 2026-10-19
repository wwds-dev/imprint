# Security review: deps-security-upgrade-2026-10 (security-engineer, 2026-10-14)

Playbook `docs/playbooks/security-engineer.md` is `status: baseline` (unverified); owner told to run Secure anyway. Result: no P0-P2, one P3.

1. Advisories: `uvx pip-audit -r requirements.txt` -> "No known vulnerabilities found". Venv matches pins. New transitive deps: truststore 0.10.5 and the httpx2 stack (anthropic -> httpx2 -> httpcore2, truststore). Not verified: pip-audit against the installed venv (only the requirements file).
2. Supply chain: all pins are genuine PyPI releases with plausible dates (httpx2/httpcore2 2.12.0, 2026-08-18, pydantic org repo `pydantic/httpx2`; pypdf 6.19.0 2026-09-16; urllib3 2.8.0 2026-09-15; pillow 12.3.0 2026-07-01; anyio 4.14.2 2026-07-12; soupsieve 2.9.0 2026-07-19; idna 3.18 2026-06-02; lxml 6.1.0 2026-04-18). Not typosquats. Not verified: hashes/attestations (no `--hash` pins).
3. Untrusted input: only new behaviour is anthropic via httpx2 loading the OS trust store through truststore; TLS verification stays on. Parser behaviour changes in pypdf/lxml/soupsieve/pillow not verified here (suite decides).
4. P3 residual: anthropic, python-pptx, PySide6, google-genai and others are unpinned (installed: anthropic 1.13.0, PySide6 6.12.0, google-genai 2.30.1); future resolves can change the transitive set. Suggest pinning these and `uv pip compile --generate-hashes` (owner decision, out of scope). Two HTTP stacks (httpx 0.28.1 + httpx2) widen the patch surface.
