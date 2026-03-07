from __future__ import annotations

import asyncio
import json
from typing import Any

from ..controller import ChaosController
from ..fault_types import FaultConfig, FaultTarget
from ..logger import get_logger

logger = get_logger("chaos-http")

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]


def _require_httpx() -> None:
    if httpx is None:
        raise ImportError(
            "httpx is required for the HTTP interceptor. "
            "Install with: pip install mcp-chaos-monkey[httpx]"
        )


class _ChaosAsyncTransport(httpx.AsyncBaseTransport if httpx else object):  # type: ignore[misc]
    """Async transport that injects chaos faults before forwarding requests."""

    def __init__(self, target: FaultTarget, transport: Any) -> None:
        self._target = target
        self._transport = transport

    async def handle_async_request(self, request: Any) -> Any:
        controller = ChaosController.get_instance()
        fault = controller.get_fault(self._target)

        if fault is None:
            return await self._transport.handle_async_request(request)

        logger.debug("Chaos fault triggered: target=%s type=%s", self._target, fault.type)
        return await _apply_async_fault(fault, request, self._transport)


class _ChaosSyncTransport(httpx.BaseTransport if httpx else object):  # type: ignore[misc]
    """Sync transport that injects chaos faults before forwarding requests."""

    def __init__(self, target: FaultTarget, transport: Any) -> None:
        self._target = target
        self._transport = transport

    def handle_request(self, request: Any) -> Any:
        controller = ChaosController.get_instance()
        fault = controller.get_fault(self._target)

        if fault is None:
            return self._transport.handle_request(request)

        logger.debug("Chaos fault triggered: target=%s type=%s", self._target, fault.type)
        return _apply_sync_fault(fault, request, self._transport)


async def _apply_async_fault(fault: FaultConfig, request: Any, transport: Any) -> Any:
    match fault.type:
        case "latency":
            await asyncio.sleep(fault.delay_ms / 1000)  # type: ignore[union-attr]
            return await transport.handle_async_request(request)
        case "error":
            return httpx.Response(
                status_code=fault.status_code,  # type: ignore[union-attr]
                content=json.dumps({"error": fault.message or "Chaos injected error"}).encode(),  # type: ignore[union-attr]
                headers={"Content-Type": "application/json"},
                request=request,
            )
        case "timeout":
            await asyncio.sleep(fault.hang_ms / 1000)  # type: ignore[union-attr]
            raise httpx.ReadTimeout(
                "Chaos timeout", request=request
            )
        case "connection-refused":
            raise httpx.ConnectError(
                "Chaos: connection refused", request=request
            )
        case "rate-limit":
            return httpx.Response(
                status_code=429,
                content=json.dumps({"error": "Too Many Requests"}).encode(),
                headers={
                    "Retry-After": str(fault.retry_after_seconds),  # type: ignore[union-attr]
                    "Content-Type": "application/json",
                },
                request=request,
            )
        case "malformed":
            return httpx.Response(
                status_code=200,
                content=b"<<<CORRUPTED_RESPONSE>>>{{{{not json",
                headers={"Content-Type": "application/json"},
                request=request,
            )
        case "schema-mismatch":
            response = await transport.handle_async_request(request)
            try:
                body = json.loads(response.content)
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning(
                    "schema-mismatch: upstream response is not valid JSON, returning as-is"
                )
                return response
            if not isinstance(body, dict):
                logger.warning("schema-mismatch: upstream JSON is not an object, returning as-is")
                return response
            for field in fault.missing_fields:  # type: ignore[union-attr]
                body.pop(field, None)
            new_content = json.dumps(body).encode()
            new_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() != "content-length"
            }
            new_headers["content-length"] = str(len(new_content))
            return httpx.Response(
                status_code=response.status_code,
                content=new_content,
                headers=new_headers,
                request=request,
            )
        case "connection-drop":
            raise httpx.ReadError(
                "Chaos: connection dropped", request=request
            )
        case _:
            return await transport.handle_async_request(request)


def _apply_sync_fault(fault: FaultConfig, request: Any, transport: Any) -> Any:
    import time

    match fault.type:
        case "latency":
            time.sleep(fault.delay_ms / 1000)  # type: ignore[union-attr]
            return transport.handle_request(request)
        case "error":
            return httpx.Response(
                status_code=fault.status_code,  # type: ignore[union-attr]
                content=json.dumps({"error": fault.message or "Chaos injected error"}).encode(),  # type: ignore[union-attr]
                headers={"Content-Type": "application/json"},
                request=request,
            )
        case "timeout":
            time.sleep(fault.hang_ms / 1000)  # type: ignore[union-attr]
            raise httpx.ReadTimeout(
                "Chaos timeout", request=request
            )
        case "connection-refused":
            raise httpx.ConnectError(
                "Chaos: connection refused", request=request
            )
        case "rate-limit":
            return httpx.Response(
                status_code=429,
                content=json.dumps({"error": "Too Many Requests"}).encode(),
                headers={
                    "Retry-After": str(fault.retry_after_seconds),  # type: ignore[union-attr]
                    "Content-Type": "application/json",
                },
                request=request,
            )
        case "malformed":
            return httpx.Response(
                status_code=200,
                content=b"<<<CORRUPTED_RESPONSE>>>{{{{not json",
                headers={"Content-Type": "application/json"},
                request=request,
            )
        case "schema-mismatch":
            response = transport.handle_request(request)
            try:
                body = json.loads(response.content)
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning(
                    "schema-mismatch: upstream response is not valid JSON, returning as-is"
                )
                return response
            if not isinstance(body, dict):
                logger.warning("schema-mismatch: upstream JSON is not an object, returning as-is")
                return response
            for field in fault.missing_fields:  # type: ignore[union-attr]
                body.pop(field, None)
            new_content = json.dumps(body).encode()
            new_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() != "content-length"
            }
            new_headers["content-length"] = str(len(new_content))
            return httpx.Response(
                status_code=response.status_code,
                content=new_content,
                headers=new_headers,
                request=request,
            )
        case "connection-drop":
            raise httpx.ReadError(
                "Chaos: connection dropped", request=request
            )
        case _:
            return transport.handle_request(request)


def create_chaos_aware_client(
    target: FaultTarget,
    client: Any | None = None,
    **kwargs: Any,
) -> Any:
    """Wrap an httpx.AsyncClient with chaos-aware transport.

    If ``client`` is provided, its internal transport is replaced.
    Otherwise a new AsyncClient is created with the given ``kwargs``.
    """
    _require_httpx()

    if client is not None:
        original = client._transport  # noqa: SLF001
        client._transport = _ChaosAsyncTransport(target, original)  # noqa: SLF001
        return client

    transport = httpx.AsyncHTTPTransport()
    return httpx.AsyncClient(
        transport=_ChaosAsyncTransport(target, transport),
        **kwargs,
    )


def create_chaos_aware_client_sync(
    target: FaultTarget,
    client: Any | None = None,
    **kwargs: Any,
) -> Any:
    """Wrap an httpx.Client (sync) with chaos-aware transport."""
    _require_httpx()

    if client is not None:
        original = client._transport  # noqa: SLF001
        client._transport = _ChaosSyncTransport(target, original)  # noqa: SLF001
        return client

    transport = httpx.HTTPTransport()
    return httpx.Client(
        transport=_ChaosSyncTransport(target, transport),
        **kwargs,
    )
