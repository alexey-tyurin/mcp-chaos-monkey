from __future__ import annotations

import json
from typing import Any, Callable

import pytest

from mcp_chaos_monkey.controller import ChaosController
from mcp_chaos_monkey.fault_types import ErrorFault, LatencyFault, TimeoutFault
from mcp_chaos_monkey.interceptors.auth_interceptor import (
    ChaosAuthMiddleware,
    create_chaos_auth_middleware,
)


async def _dummy_app(scope: dict, receive: Callable, send: Callable) -> None:
    """Minimal ASGI app that returns 200 OK."""
    body = json.dumps({"status": "ok"}).encode()
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({"type": "http.response.body", "body": body})


async def _call_middleware(
    middleware: ChaosAuthMiddleware,
    path: str = "/test",
) -> tuple[int, dict[str, Any]]:
    """Call the middleware and capture the response status + body."""
    status_code = 0
    body = b""

    async def receive() -> dict:
        return {"type": "http.request", "body": b""}

    async def send(message: dict) -> None:
        nonlocal status_code, body
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            body = message.get("body", b"")

    scope = {"type": "http", "path": path, "method": "GET"}
    await middleware(scope, receive, send)
    return status_code, json.loads(body) if body else {}


@pytest.mark.asyncio
async def test_no_fault_passes_through() -> None:
    middleware = ChaosAuthMiddleware(_dummy_app)
    status, data = await _call_middleware(middleware)
    assert status == 200
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_error_fault() -> None:
    controller = ChaosController.get_instance()
    controller.inject("oauth-token", ErrorFault(status_code=401, message="bad token"))
    middleware = ChaosAuthMiddleware(_dummy_app)
    status, data = await _call_middleware(middleware)
    assert status == 401
    assert data["error"] == "token_invalid"
    assert "bad token" in data["message"]


@pytest.mark.asyncio
async def test_latency_fault() -> None:
    controller = ChaosController.get_instance()
    controller.inject("oauth-token", LatencyFault(delay_ms=10))
    middleware = ChaosAuthMiddleware(_dummy_app)
    status, data = await _call_middleware(middleware)
    assert status == 200
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_custom_target() -> None:
    controller = ChaosController.get_instance()
    controller.inject("api-key", ErrorFault(status_code=403))
    middleware = ChaosAuthMiddleware(_dummy_app, target="api-key")
    status, data = await _call_middleware(middleware)
    assert status == 403


@pytest.mark.asyncio
async def test_create_chaos_auth_middleware_factory() -> None:
    controller = ChaosController.get_instance()
    controller.inject("custom-auth", ErrorFault(status_code=401))
    factory = create_chaos_auth_middleware("custom-auth")
    middleware = factory(_dummy_app)
    status, _ = await _call_middleware(middleware)
    assert status == 401


@pytest.mark.asyncio
async def test_timeout_fault_sends_504() -> None:
    """Fix #12: timeout fault should eventually send a 504 response, not hang forever."""
    controller = ChaosController.get_instance()
    controller.inject("oauth-token", TimeoutFault(hang_ms=10))
    middleware = ChaosAuthMiddleware(_dummy_app)
    status, data = await _call_middleware(middleware)
    assert status == 504
    assert "Gateway Timeout" in data["error"]


@pytest.mark.asyncio
async def test_non_http_scope_passes_through() -> None:
    """Non-HTTP scopes (websocket, lifespan) should be forwarded directly."""
    called = False

    async def ws_app(scope: dict, receive: Callable, send: Callable) -> None:
        nonlocal called
        called = True

    controller = ChaosController.get_instance()
    controller.inject("oauth-token", ErrorFault(status_code=401))
    middleware = ChaosAuthMiddleware(ws_app)

    scope = {"type": "websocket", "path": "/ws"}
    await middleware(scope, lambda: {}, lambda _: None)  # type: ignore
    assert called
