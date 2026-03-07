from __future__ import annotations

import hmac
import os
from dataclasses import asdict
from typing import Any

from .controller import ChaosController
from .fault_types import FaultConfig, parse_fault_config
from .guard import assert_chaos_allowed
from .logger import get_logger

logger = get_logger("chaos-admin")

_VALID_FAULT_TYPES = {
    "latency", "error", "timeout", "malformed",
    "connection-refused", "connection-drop", "rate-limit", "schema-mismatch",
}


def _check_admin_auth(headers: dict[str, str] | None = None) -> str | None:
    """Return an error message if auth fails, or None if OK."""
    required_token = os.environ.get("CHAOS_ADMIN_TOKEN")
    if required_token is None:
        return "CHAOS_ADMIN_TOKEN is not set — admin access denied. Set CHAOS_ADMIN_TOKEN to enable admin endpoints."
    if required_token == "":
        return "CHAOS_ADMIN_TOKEN is set but empty — refusing access"
    if headers is None:
        return "Invalid or missing CHAOS_ADMIN_TOKEN"
    provided = headers.get("authorization", "").removeprefix("Bearer ")
    if not hmac.compare_digest(provided, required_token):
        return "Invalid or missing CHAOS_ADMIN_TOKEN"
    return None


def handle_status() -> dict[str, Any]:
    """GET /chaos/status — returns active faults."""
    controller = ChaosController.get_instance()
    faults = controller.get_active_faults()
    return {"faults": [asdict(f) for f in faults]}


def handle_inject(body: dict[str, Any]) -> dict[str, Any]:
    """POST /chaos/inject — inject a fault."""
    target = body.get("target")
    if not target or not isinstance(target, str):
        raise ValueError("Missing required field: target (non-empty string)")
    config_data = body.get("config")
    if not isinstance(config_data, dict) or config_data.get("type") not in _VALID_FAULT_TYPES:
        raise ValueError(
            f"Missing or invalid field: config.type "
            f"(must be one of: {', '.join(sorted(_VALID_FAULT_TYPES))})"
        )
    duration_ms = body.get("duration_ms")
    if duration_ms is not None:
        if not isinstance(duration_ms, (int, float)) or duration_ms < 0:
            raise ValueError("duration_ms must be a non-negative number")
    controller = ChaosController.get_instance()
    config: FaultConfig = parse_fault_config(config_data)
    fault_id = controller.inject(target, config, duration_ms)
    return {"fault_id": fault_id}


def handle_clear(body: dict[str, Any]) -> dict[str, Any]:
    """POST /chaos/clear — clear a specific fault."""
    fault_id = body.get("fault_id")
    if not fault_id or not isinstance(fault_id, str):
        raise ValueError("Missing required field: fault_id")
    controller = ChaosController.get_instance()
    controller.clear(fault_id)
    return {"cleared": fault_id}


def handle_clear_all() -> dict[str, Any]:
    """POST /chaos/clear-all — clear all faults."""
    controller = ChaosController.get_instance()
    controller.clear_all()
    return {"cleared": "all"}


def create_starlette_routes() -> list[Any]:
    """Create Starlette Route objects for chaos admin endpoints.

    Requires: pip install mcp-chaos-monkey[starlette]
    """
    try:
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route
    except ImportError as e:
        raise ImportError(
            "starlette is required for admin routes. "
            "Install with: pip install mcp-chaos-monkey[starlette]"
        ) from e

    assert_chaos_allowed()

    def _auth_check(request: Request) -> JSONResponse | None:
        headers = dict(request.headers)
        auth_error = _check_admin_auth(headers)
        if auth_error:
            return JSONResponse({"error": auth_error}, status_code=403)
        return None

    async def status_route(request: Request) -> JSONResponse:
        denied = _auth_check(request)
        if denied:
            return denied
        try:
            return JSONResponse(handle_status())
        except Exception as exc:
            logger.error("Chaos status failed: %s", exc)
            return JSONResponse({"error": "Failed to get chaos status"}, status_code=500)

    async def inject_route(request: Request) -> JSONResponse:
        denied = _auth_check(request)
        if denied:
            return denied
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        try:
            return JSONResponse(handle_inject(body))
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            logger.error("Chaos inject failed: %s", exc)
            return JSONResponse({"error": "Failed to inject fault"}, status_code=500)

    async def clear_route(request: Request) -> JSONResponse:
        denied = _auth_check(request)
        if denied:
            return denied
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        try:
            return JSONResponse(handle_clear(body))
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            logger.error("Chaos clear failed: %s", exc)
            return JSONResponse({"error": "Failed to clear fault"}, status_code=500)

    async def clear_all_route(request: Request) -> JSONResponse:
        denied = _auth_check(request)
        if denied:
            return denied
        try:
            return JSONResponse(handle_clear_all())
        except Exception as exc:
            logger.error("Chaos clear-all failed: %s", exc)
            return JSONResponse({"error": "Failed to clear all faults"}, status_code=500)

    logger.info("Chaos admin endpoints registered at /chaos/*")

    return [
        Route("/chaos/status", status_route, methods=["GET"]),
        Route("/chaos/inject", inject_route, methods=["POST"]),
        Route("/chaos/clear", clear_route, methods=["POST"]),
        Route("/chaos/clear-all", clear_all_route, methods=["POST"]),
    ]
