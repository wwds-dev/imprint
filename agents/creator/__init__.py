"""Public interface for the Muse agent."""

from .agent import KINDS, PROMO_CHANNELS, CreatorAgent

__all__ = ["KINDS", "PROMO_CHANNELS", "CreatorAgent", "CreatorPanel"]


def __getattr__(name):
    # Lazy panel import keeps this package Qt-free at import time for
    # consumers that only want the agent (tests, CLI tools).
    if name == "CreatorPanel":
        from .panel import CreatorPanel
        return CreatorPanel
    raise AttributeError(name)
