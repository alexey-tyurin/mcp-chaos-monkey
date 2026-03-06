"""Interceptors — lazy imports to avoid requiring optional dependencies at import time."""

from typing import Any

_LAZY_IMPORTS = {
    "create_chaos_aware_client": ".http_interceptor",
    "create_chaos_aware_client_sync": ".http_interceptor",
    "wrap_redis_with_chaos": ".redis_interceptor",
    "ChaosAuthMiddleware": ".auth_interceptor",
    "create_chaos_auth_middleware": ".auth_interceptor",
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    module_path = _LAZY_IMPORTS.get(name)
    if module_path is not None:
        import importlib

        module = importlib.import_module(module_path, __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
