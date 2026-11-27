"""The Manuscript shell: icon rail, top bar, chips, popovers and the History
drawer (spec manuscript-redesign, slice 1; ADR 0006).

These modules import Qt, ``ui.style``, ``ui.theme`` and ``ui.motion`` only
(decision 10). ``main.py`` builds every existing control with its handler, as
it always has, and places it in these containers; nothing here fetches, spends
or starts a thread.
"""
