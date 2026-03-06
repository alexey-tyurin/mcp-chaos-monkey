from __future__ import annotations

import pytest

from mcp_chaos_monkey.guard import ChaosNotAllowedError, assert_chaos_allowed


def test_allowed_when_chaos_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAOS_ENABLED", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("NODE_ENV", raising=False)
    assert_chaos_allowed()  # should not raise


def test_blocked_in_production_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAOS_ENABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ChaosNotAllowedError, match="production"):
        assert_chaos_allowed()


def test_blocked_in_production_node_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAOS_ENABLED", "true")
    monkeypatch.setenv("NODE_ENV", "production")
    with pytest.raises(ChaosNotAllowedError, match="production"):
        assert_chaos_allowed()


def test_blocked_when_chaos_not_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHAOS_ENABLED", raising=False)
    with pytest.raises(ChaosNotAllowedError, match="CHAOS_ENABLED"):
        assert_chaos_allowed()


def test_blocked_when_chaos_enabled_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAOS_ENABLED", "false")
    with pytest.raises(ChaosNotAllowedError, match="CHAOS_ENABLED"):
        assert_chaos_allowed()


def test_case_insensitive_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAOS_ENABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", "Production")
    with pytest.raises(ChaosNotAllowedError, match="production"):
        assert_chaos_allowed()
