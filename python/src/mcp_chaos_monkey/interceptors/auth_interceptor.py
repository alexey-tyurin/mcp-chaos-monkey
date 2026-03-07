from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from ..controller import ChaosController
from ..fault_types import FaultTarget
from ..logger import get_logger

logger = get_logger("chaos-auth")

# ASGI type aliases
Scope = dict[str, Any]
Receive = Callable[..., Any]
Send = Callable[..., Any]
ASGIApp = Callable[..., Any]


class ChaosAuthMiddleware:
    """ASGI middleware that injects chaos faults into auth flows."""

    def __init__(self, app: ASGIApp, target: FaultTarget = "oauth-token") -> None:
        self.app = app
        self.target = target

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        controller = ChaosController.get_instance()
        fault = controller.get_fault(self.target)

        if fault is None:
            await self.app(scope, receive, send)
            return

        logger.debug("Chaos auth fault triggered: type=%s", fault.type)

        match fault.type:
            case "error":
                body = json.dumps({
                    "error": "token_invalid",
                    "message": fault.message or "Authentication failed (chaos)",  # type: ignore[union-attr]
                }).encode()
                await send({
                    "type": "http.response.start",
                    "status": fault.status_code,  # type: ignore[union-attr]
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"content-length", str(len(body)).encode()],
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": body,
                })
            case "latency":
                await asyncio.sleep(fault.delay_ms / 1000)  # type: ignore[union-attr]
                await self.app(scope, receive, send)
            case "timeout":
                # Hang for the specified duration then send 504 to avoid leaking connections
                await asyncio.sleep(fault.hang_ms / 1000)  # type: ignore[union-attr]
                timeout_body = json.dumps({"error": "Gateway Timeout (chaos)"}).encode()
                await send({
                    "type": "http.response.start",
                    "status": 504,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"content-length", str(len(timeout_body)).encode()],
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": timeout_body,
                })
            case _:
                await self.app(scope, receive, send)


def create_chaos_auth_middleware(
    target: FaultTarget = "oauth-token",
) -> Callable[[ASGIApp], ChaosAuthMiddleware]:
    """Factory that returns a middleware class constructor with a preset target."""

    def wrapper(app: ASGIApp) -> ChaosAuthMiddleware:
        return ChaosAuthMiddleware(app, target=target)

    return wrapper
