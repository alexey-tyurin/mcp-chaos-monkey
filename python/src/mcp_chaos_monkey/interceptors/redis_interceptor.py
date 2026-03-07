from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Callable
from typing import Any

from ..controller import ChaosController
from ..fault_types import FaultTarget
from ..logger import get_logger

logger = get_logger("chaos-redis")

COMMANDS_TO_WRAP = ("get", "set", "delete", "hget", "hset", "expire", "ttl", "keys", "mget")


def wrap_redis_with_chaos(
    client: Any,
    target: FaultTarget = "redis",
) -> Callable[[], None]:
    """Monkey-patch a redis-py client to inject chaos faults.

    Supports both sync ``redis.Redis`` and async ``redis.asyncio.Redis``.
    Returns an unwrap function that restores the original methods.
    """
    originals: dict[str, Any] = {}
    is_async = asyncio.iscoroutinefunction(getattr(client, "get", None))

    for cmd in COMMANDS_TO_WRAP:
        original = getattr(client, cmd, None)
        if original is None or not callable(original):
            continue
        originals[cmd] = original

        if is_async:
            @functools.wraps(original)
            async def async_wrapped(
                *args: Any, _orig: Any = original, _cmd: str = cmd, **kwargs: Any,
            ) -> Any:
                controller = ChaosController.get_instance()
                fault = controller.get_fault(target)

                if fault is None:
                    return await _orig(*args, **kwargs)

                logger.debug(
                    "Chaos Redis fault triggered: target=%s cmd=%s type=%s",
                    target, _cmd, fault.type,
                )

                match fault.type:
                    case "latency":
                        await asyncio.sleep(fault.delay_ms / 1000)  # type: ignore[union-attr]
                        return await _orig(*args, **kwargs)
                    case "error":
                        raise ConnectionError(
                            f"Chaos Redis error: {fault.message or 'connection lost'}"  # type: ignore[union-attr]
                        )
                    case "timeout":
                        await asyncio.sleep(fault.hang_ms / 1000)  # type: ignore[union-attr]
                        raise TimeoutError("Chaos Redis timeout")
                    case "connection-refused":
                        raise ConnectionError("Redis connection refused (chaos)")
                    case _:
                        return await _orig(*args, **kwargs)

            setattr(client, cmd, async_wrapped)
        else:
            @functools.wraps(original)
            def sync_wrapped(
                *args: Any, _orig: Any = original, _cmd: str = cmd, **kwargs: Any,
            ) -> Any:
                controller = ChaosController.get_instance()
                fault = controller.get_fault(target)

                if fault is None:
                    return _orig(*args, **kwargs)

                logger.debug(
                    "Chaos Redis fault triggered: target=%s cmd=%s type=%s",
                    target, _cmd, fault.type,
                )

                match fault.type:
                    case "latency":
                        time.sleep(fault.delay_ms / 1000)  # type: ignore[union-attr]
                        return _orig(*args, **kwargs)
                    case "error":
                        raise ConnectionError(
                            f"Chaos Redis error: {fault.message or 'connection lost'}"  # type: ignore[union-attr]
                        )
                    case "timeout":
                        time.sleep(fault.hang_ms / 1000)  # type: ignore[union-attr]
                        raise TimeoutError("Chaos Redis timeout")
                    case "connection-refused":
                        raise ConnectionError("Redis connection refused (chaos)")
                    case _:
                        return _orig(*args, **kwargs)

            setattr(client, cmd, sync_wrapped)

    def unwrap() -> None:
        for cmd_name, orig_fn in originals.items():
            setattr(client, cmd_name, orig_fn)
        originals.clear()

    return unwrap
