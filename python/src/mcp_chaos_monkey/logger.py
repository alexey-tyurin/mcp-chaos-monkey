from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ChaosLogger(Protocol):
    """Pluggable logger interface — stdlib logging.Logger satisfies this directly."""

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def error(self, msg: str, *args: Any, **kwargs: Any) -> None: ...


ChaosLoggerFactory = Callable[[str], ChaosLogger]


def create_default_logger(name: str) -> ChaosLogger:
    """Create a default logger using stdlib logging."""
    return logging.getLogger(f"mcp_chaos_monkey.{name}")


_logger_factory: ChaosLoggerFactory = create_default_logger


def configure_chaos_logger(factory: ChaosLoggerFactory) -> None:
    """Set the global logger factory. Call once at startup."""
    global _logger_factory
    _logger_factory = factory


class _LazyLogger:
    """Proxy that delegates to the current logger factory on each call.

    This ensures that calling ``configure_chaos_logger`` after modules have
    already been imported still takes effect.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    def _get(self) -> ChaosLogger:
        return _logger_factory(self._name)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._get().debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._get().info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._get().warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._get().error(msg, *args, **kwargs)


def get_logger(name: str) -> ChaosLogger:
    """Internal — used by all library modules.

    Returns a lazy proxy so that ``configure_chaos_logger`` takes effect
    even when called after module import.
    """
    return _LazyLogger(name)  # type: ignore[return-value]
