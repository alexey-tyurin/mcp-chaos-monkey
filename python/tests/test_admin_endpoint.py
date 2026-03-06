from __future__ import annotations

import pytest

from mcp_chaos_monkey.admin_endpoint import (
    _check_admin_auth,
    handle_clear,
    handle_clear_all,
    handle_inject,
    handle_status,
)
from mcp_chaos_monkey.controller import ChaosController


def test_handle_status_empty() -> None:
    result = handle_status()
    assert result == {"faults": []}


def test_handle_inject() -> None:
    result = handle_inject({
        "target": "weather-api",
        "config": {"type": "error", "status_code": 503},
    })
    assert "fault_id" in result
    assert result["fault_id"].startswith("weather-api-")


def test_handle_inject_with_duration() -> None:
    result = handle_inject({
        "target": "redis",
        "config": {"type": "latency", "delay_ms": 100},
        "duration_ms": 5000,
    })
    assert "fault_id" in result


def test_handle_status_with_faults() -> None:
    handle_inject({
        "target": "api",
        "config": {"type": "error", "status_code": 500},
    })
    result = handle_status()
    assert len(result["faults"]) >= 1
    fault = result["faults"][-1]
    assert fault["target"] == "api"
    assert fault["type"] == "error"


def test_handle_clear() -> None:
    inject_result = handle_inject({
        "target": "to-clear",
        "config": {"type": "timeout", "hang_ms": 1000},
    })
    fault_id = inject_result["fault_id"]

    clear_result = handle_clear({"fault_id": fault_id})
    assert clear_result == {"cleared": fault_id}


def test_handle_clear_all() -> None:
    handle_inject({
        "target": "a",
        "config": {"type": "error", "status_code": 500},
    })
    result = handle_clear_all()
    assert result == {"cleared": "all"}

    status = handle_status()
    assert status["faults"] == []


def test_inject_camel_case_keys() -> None:
    """Ensure camelCase keys from JSON work (cross-language compat)."""
    result = handle_inject({
        "target": "api",
        "config": {"type": "latency", "delayMs": 200},
    })
    assert "fault_id" in result


def test_handle_inject_missing_target() -> None:
    """Fix #7: Missing target should raise ValueError, not KeyError."""
    with pytest.raises(ValueError, match="target"):
        handle_inject({"config": {"type": "error", "status_code": 500}})


def test_handle_inject_missing_config() -> None:
    """Fix #7: Missing config should raise ValueError."""
    with pytest.raises(ValueError, match="config.type"):
        handle_inject({"target": "api"})


def test_handle_inject_invalid_fault_type() -> None:
    """Fix #7: Invalid fault type in config should raise ValueError."""
    with pytest.raises(ValueError, match="config.type"):
        handle_inject({"target": "api", "config": {"type": "bogus"}})


def test_handle_clear_missing_fault_id() -> None:
    """Fix #7: Missing fault_id should raise ValueError."""
    with pytest.raises(ValueError, match="fault_id"):
        handle_clear({})


def test_admin_auth_no_token_required() -> None:
    """Fix #4: When CHAOS_ADMIN_TOKEN is not set, auth always passes."""
    assert _check_admin_auth() is None
    assert _check_admin_auth({"authorization": "Bearer whatever"}) is None


def test_admin_auth_token_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix #4: When CHAOS_ADMIN_TOKEN is set, auth is enforced."""
    monkeypatch.setenv("CHAOS_ADMIN_TOKEN", "secret123")
    assert _check_admin_auth() is not None
    assert _check_admin_auth({"authorization": "Bearer wrong"}) is not None
    assert _check_admin_auth({"authorization": "Bearer secret123"}) is None
