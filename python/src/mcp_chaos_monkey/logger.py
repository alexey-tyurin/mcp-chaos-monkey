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


def get_logger(name: str) -> ChaosLogger:
    """Internal — used by all library modules."""
    return _logger_factory(name)
