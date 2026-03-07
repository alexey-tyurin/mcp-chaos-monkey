from __future__ import annotations

from unittest.mock import MagicMock

from mcp_chaos_monkey.logger import configure_chaos_logger, get_logger


def test_lazy_logger_uses_current_factory(monkeypatch: object) -> None:
    """Fix #9: get_logger returns a lazy proxy that delegates to the current factory.

    Calling configure_chaos_logger after get_logger should still take effect.
    """
    # get_logger is called at import time in real modules — simulate that
    logger = get_logger("test-module")

    # Now configure a custom factory *after* the logger was created
    custom_logger = MagicMock()
    custom_factory = MagicMock(return_value=custom_logger)
    configure_chaos_logger(custom_factory)

    # The lazy proxy should delegate to the new factory
    logger.info("hello %s", "world")
    custom_factory.assert_called_with("test-module")
    custom_logger.info.assert_called_once_with("hello %s", "world")

    # Restore default to avoid polluting other tests
    from mcp_chaos_monkey.logger import create_default_logger
    configure_chaos_logger(create_default_logger)


def test_lazy_logger_switches_factory_dynamically() -> None:
    """Switching factory multiple times should always use the latest one."""
    logger = get_logger("dynamic-test")

    factory_a = MagicMock(return_value=MagicMock())
    factory_b = MagicMock(return_value=MagicMock())

    configure_chaos_logger(factory_a)
    logger.warning("msg1")
    factory_a.assert_called_with("dynamic-test")
    factory_a.return_value.warning.assert_called_once_with("msg1")

    configure_chaos_logger(factory_b)
    logger.error("msg2")
    factory_b.assert_called_with("dynamic-test")
    factory_b.return_value.error.assert_called_once_with("msg2")

    # Restore default
    from mcp_chaos_monkey.logger import create_default_logger
    configure_chaos_logger(create_default_logger)
