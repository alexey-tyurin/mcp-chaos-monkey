from __future__ import annotations

import os


class ChaosNotAllowedError(Exception):
    """Raised when chaos injection is attempted in an unsafe environment."""


def assert_chaos_allowed() -> None:
    """Guard that prevents chaos from running in production or without explicit opt-in."""
    env = os.environ.get("ENVIRONMENT", "").lower()
    node_env = os.environ.get("NODE_ENV", "").lower()
    if env == "production" or node_env == "production":
        raise ChaosNotAllowedError(
            "FATAL: Chaos framework must never run in production"
        )
    if os.environ.get("CHAOS_ENABLED", "").lower() != "true":
        raise ChaosNotAllowedError(
            "Chaos framework not enabled. Set CHAOS_ENABLED=true"
        )
