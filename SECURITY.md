# Security

Imprint is free, open-source software maintained by one person. It handles API keys for several paid providers, imports untrusted documents (PDF, EPUB, DOCX) and renders model output,
so security reports are welcome.

## Report privately

Use GitHub's private report form: **Security > Report a vulnerability** on
<https://github.com/wwds-dev/imprint/security/advisories/new>. Please do not open a public issue for a vulnerability.

Include the version in the header bar, what you did, and what happened. Leave out real keys, tokens and personal data:
describe them instead.

## What to expect

- **Acknowledgement within 7 days.**
- **A first assessment within 14 days**, and a fix or a written reason within 90 days.
- No bounty, and no service-level promise beyond this: one person keeps this project, in
  their own time. If a deadline slips, the report gets a reply saying so.
- Credit in the CHANGELOG if you want it.

## Supported versions

Only the latest commit on `main` is supported. There are no binary releases; Imprint is
distributed as source.

## Scope

In scope: this repository, including the video pipeline (`vidforge/`) and the narrator converter.
Out of scope: vulnerabilities in Qt, PySide6, Python, Ollama or the model and posting providers themselves (report those upstream), problems that need an attacker who already controls your Mac, and model output you consider wrong (that is a bug or a feature request, not a vulnerability).
