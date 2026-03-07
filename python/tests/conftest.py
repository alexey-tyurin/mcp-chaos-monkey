from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def chaos_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up environment for chaos tests and reset singleton between tests."""
    monkeypatch.setenv("CHAOS_ENABLED", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("NODE_ENV", raising=False)
    # Reset singleton before each test
    from mcp_chaos_monkey.controller import ChaosController

    ChaosController._instance = None
