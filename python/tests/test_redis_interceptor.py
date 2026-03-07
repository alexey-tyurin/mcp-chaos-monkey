from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mcp_chaos_monkey.controller import ChaosController
from mcp_chaos_monkey.fault_types import ConnectionRefusedFault, ErrorFault, RateLimitFault
from mcp_chaos_monkey.interceptors.redis_interceptor import wrap_redis_with_chaos


def _make_mock_redis() -> MagicMock:
    """Create a mock sync Redis client."""
    client = MagicMock()
    client.get = MagicMock(return_value=b"value")
    client.set = MagicMock(return_value=True)
    client.delete = MagicMock(return_value=1)
    client.hget = MagicMock(return_value=b"hval")
    client.hset = MagicMock(return_value=1)
    client.expire = MagicMock(return_value=True)
    client.ttl = MagicMock(return_value=300)
    client.keys = MagicMock(return_value=[b"key1"])
    client.mget = MagicMock(return_value=[b"v1", b"v2"])
    return client


def test_no_fault_passes_through() -> None:
    client = _make_mock_redis()
    unwrap = wrap_redis_with_chaos(client, "redis")
    result = client.get("mykey")
    assert result == b"value"
    unwrap()


def test_error_fault() -> None:
    controller = ChaosController.get_instance()
    controller.inject("redis", ErrorFault(status_code=500, message="chaos"))
    client = _make_mock_redis()
    unwrap = wrap_redis_with_chaos(client, "redis")
    with pytest.raises(ConnectionError, match="chaos"):
        client.get("mykey")
    unwrap()


def test_connection_refused_fault() -> None:
    controller = ChaosController.get_instance()
    controller.inject("redis", ConnectionRefusedFault())
    client = _make_mock_redis()
    unwrap = wrap_redis_with_chaos(client, "redis")
    with pytest.raises(ConnectionError, match="refused"):
        client.set("key", "val")
    unwrap()


def test_unwrap_restores_original() -> None:
    controller = ChaosController.get_instance()
    controller.inject("redis", ErrorFault(status_code=500))
    client = _make_mock_redis()
    unwrap = wrap_redis_with_chaos(client, "redis")
    with pytest.raises(ConnectionError):
        client.get("key")
    unwrap()
    result = client.get("key")
    assert result == b"value"


def test_unknown_fault_type_passes_through() -> None:
    """Faults that don't apply to Redis (e.g. rate-limit) should pass through."""
    controller = ChaosController.get_instance()
    controller.inject("redis", RateLimitFault(retry_after_seconds=60))
    client = _make_mock_redis()
    unwrap = wrap_redis_with_chaos(client, "redis")
    result = client.get("key")
    assert result == b"value"
    unwrap()


def test_double_wrap_raises() -> None:
    """Fix #10: Double-wrapping the same client should raise RuntimeError."""
    client = _make_mock_redis()
    unwrap = wrap_redis_with_chaos(client, "redis")
    with pytest.raises(RuntimeError, match="already wrapped"):
        wrap_redis_with_chaos(client, "redis")
    unwrap()


def test_unwrap_allows_rewrap() -> None:
    """After unwrap, the client can be wrapped again."""
    client = _make_mock_redis()
    unwrap1 = wrap_redis_with_chaos(client, "redis")
    unwrap1()
    unwrap2 = wrap_redis_with_chaos(client, "redis")
    unwrap2()
