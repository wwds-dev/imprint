"""Release kit: an approved manuscript version to a release kit in one job.

Spec: docs/specs/one-click-release.md (Design D1–D7, Architecture A0–A10);
ADR 0005. Everything in this package is Qt-free; widgets and the driver that
runs the job on the GUI thread live in ui/release_kit/.

Slice 1 is the free path only: every step runs on this Mac.
"""
