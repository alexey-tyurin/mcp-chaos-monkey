from __future__ import annotations

import json

import httpx
import pytest

from mcp_chaos_monkey.controller import ChaosController
from mcp_chaos_monkey.fault_types import (
    ConnectionRefusedFault,
    ErrorFault,
    LatencyFault,
    MalformedFault,
    RateLimitFault,
    SchemaMismatchFault,
    TimeoutFault,
)
from mcp_chaos_monkey.interceptors.http_interceptor import (
    _ChaosAsyncTransport,
    create_chaos_aware_client,
)


class _EchoTransport(httpx.AsyncBaseTransport):
    """Test transport that echoes the request URL as JSON body."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = json.dumps({"url": str(request.url), "echoed": True})
        return httpx.Response(
            status_code=200,
            content=body.encode(),
            headers={"Content-Type": "application/json"},
            request=request,
        )


def _make_client(target: str = "test-api") -> httpx.AsyncClient:
    echo = _EchoTransport()
    chaos = _ChaosAsyncTransport(target, echo)
    return httpx.AsyncClient(transport=chaos)


@pytest.mark.asyncio
async def test_no_fault_passes_through() -> None:
    client = _make_client()
    resp = await client.get("http://example.com/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["echoed"] is True


@pytest.mark.asyncio
async def test_error_fault() -> None:
    controller = ChaosController.get_instance()
    controller.inject("test-api", ErrorFault(status_code=503, message="down"))
    client = _make_client()
    resp = await client.get("http://example.com/test")
    assert resp.status_code == 503
    assert "down" in resp.json()["error"]


@pytest.mark.asyncio
async def test_latency_fault() -> None:
    controller = ChaosController.get_instance()
    controller.inject("test-api", LatencyFault(delay_ms=50))
    client = _make_client()
    resp = await client.get("http://example.com/test")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_timeout_fault() -> None:
    controller = ChaosController.get_instance()
    controller.inject("test-api", TimeoutFault(hang_ms=10))
    client = _make_client()
    with pytest.raises(httpx.ReadTimeout):
        await client.get("http://example.com/test")


@pytest.mark.asyncio
async def test_connection_refused_fault() -> None:
    controller = ChaosController.get_instance()
    controller.inject("test-api", ConnectionRefusedFault())
    client = _make_client()
    with pytest.raises(httpx.ConnectError):
        await client.get("http://example.com/test")


@pytest.mark.asyncio
async def test_rate_limit_fault() -> None:
    controller = ChaosController.get_instance()
    controller.inject("test-api", RateLimitFault(retry_after_seconds=30))
    client = _make_client()
    resp = await client.get("http://example.com/test")
    assert resp.status_code == 429
    assert resp.headers["retry-after"] == "30"


@pytest.mark.asyncio
async def test_malformed_fault() -> None:
    controller = ChaosController.get_instance()
    controller.inject("test-api", MalformedFault())
    client = _make_client()
    resp = await client.get("http://example.com/test")
    assert resp.status_code == 200
    assert b"CORRUPTED" in resp.content
    with pytest.raises(json.JSONDecodeError):
        resp.json()


@pytest.mark.asyncio
async def test_create_chaos_aware_client_wraps_existing() -> None:
    base_client = httpx.AsyncClient(transport=_EchoTransport())
    wrapped = create_chaos_aware_client("wrap-test", base_client)
    assert wrapped is base_client

    controller = ChaosController.get_instance()
    controller.inject("wrap-test", ErrorFault(status_code=418))
    resp = await wrapped.get("http://example.com/test")
    assert resp.status_code == 418


class _HtmlTransport(httpx.AsyncBaseTransport):
    """Test transport that returns non-JSON HTML."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=500,
            content=b"<html><body>Error</body></html>",
            headers={"Content-Type": "text/html"},
            request=request,
        )


@pytest.mark.asyncio
async def test_schema_mismatch_non_json_response() -> None:
    """Fix #6: schema-mismatch on non-JSON response should not crash with JSONDecodeError."""
    controller = ChaosController.get_instance()
    controller.inject("html-api", SchemaMismatchFault(missing_fields=["foo"]))
    html_transport = _HtmlTransport()
    chaos = _ChaosAsyncTransport("html-api", html_transport)
    client = httpx.AsyncClient(transport=chaos)
    resp = await client.get("http://example.com/test")
    # Should return the original response as-is instead of crashing
    assert resp.status_code == 500
    assert b"<html>" in resp.content
