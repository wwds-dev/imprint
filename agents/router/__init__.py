"""Public interface for the internal intent router."""

from .agent import ROUTES, RouteDecision, RouterAgent

__all__ = ["ROUTES", "RouteDecision", "RouterAgent"]
