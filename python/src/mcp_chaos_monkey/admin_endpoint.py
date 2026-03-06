from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .controller import ChaosController
from .fault_types import FaultConfig, parse_fault_config
from .guard import assert_chaos_allowed
from .logger import get_logger

logger = get_logger("chaos-admin")


def handle_status() -> dict[str, Any]:
    """GET /chaos/status — returns active faults."""
    controller = ChaosController.get_instance()
    faults = controller.get_active_faults()
    return {"faults": [asdict(f) for f in faults]}


def handle_inject(body: dict[str, Any]) -> dict[str, Any]:
    """POST /chaos/inject — inject a fault."""
    controller = ChaosController.get_instance()
    config: FaultConfig = parse_fault_config(body["config"])
    fault_id = controller.inject(body["target"], config, body.get("duration_ms"))
    return {"fault_id": fault_id}


def handle_clear(body: dict[str, Any]) -> dict[str, Any]:
    """POST /chaos/clear — clear a specific fault."""
    controller = ChaosController.get_instance()
    fault_id = body["fault_id"]
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

    async def status_route(request: Request) -> JSONResponse:
        try:
            return JSONResponse(handle_status())
        except Exception as exc:
            logger.error("Chaos status failed: %s", exc)
            return JSONResponse({"error": "Failed to get chaos status"}, status_code=500)

    async def inject_route(request: Request) -> JSONResponse:
        try:
            body = await request.json()
            return JSONResponse(handle_inject(body))
        except Exception as exc:
            logger.error("Chaos inject failed: %s", exc)
            return JSONResponse({"error": "Failed to inject fault"}, status_code=500)

    async def clear_route(request: Request) -> JSONResponse:
        try:
            body = await request.json()
            return JSONResponse(handle_clear(body))
        except Exception as exc:
            logger.error("Chaos clear failed: %s", exc)
            return JSONResponse({"error": "Failed to clear fault"}, status_code=500)

    async def clear_all_route(request: Request) -> JSONResponse:
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
