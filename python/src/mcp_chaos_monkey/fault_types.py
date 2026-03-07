from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Union

FaultTarget = str


def is_fault_target(value: object) -> bool:
    """Validates that a value is a non-empty string suitable as a fault target."""
    return isinstance(value, str) and len(value) > 0


class FaultType(StrEnum):
    LATENCY = "latency"
    ERROR = "error"
    TIMEOUT = "timeout"
    MALFORMED = "malformed"
    CONNECTION_REFUSED = "connection-refused"
    CONNECTION_DROP = "connection-drop"
    RATE_LIMIT = "rate-limit"
    SCHEMA_MISMATCH = "schema-mismatch"


@dataclass
class LatencyFault:
    delay_ms: int
    probability: float | None = None
    type: str = field(default=FaultType.LATENCY, init=False)


@dataclass
class ErrorFault:
    status_code: int
    message: str | None = None
    probability: float | None = None
    type: str = field(default=FaultType.ERROR, init=False)


@dataclass
class TimeoutFault:
    hang_ms: int
    probability: float | None = None
    type: str = field(default=FaultType.TIMEOUT, init=False)


@dataclass
class MalformedFault:
    corrupt_response: bool = True
    probability: float | None = None
    type: str = field(default=FaultType.MALFORMED, init=False)


@dataclass
class ConnectionRefusedFault:
    probability: float | None = None
    type: str = field(default=FaultType.CONNECTION_REFUSED, init=False)


@dataclass
class ConnectionDropFault:
    after_bytes: int | None = None
    probability: float | None = None
    type: str = field(default=FaultType.CONNECTION_DROP, init=False)


@dataclass
class RateLimitFault:
    retry_after_seconds: int
    probability: float | None = None
    type: str = field(default=FaultType.RATE_LIMIT, init=False)


@dataclass
class SchemaMismatchFault:
    missing_fields: list[str] = field(default_factory=list)
    probability: float | None = None
    type: str = field(default=FaultType.SCHEMA_MISMATCH, init=False)


FaultConfig = Union[
    LatencyFault,
    ErrorFault,
    TimeoutFault,
    MalformedFault,
    ConnectionRefusedFault,
    ConnectionDropFault,
    RateLimitFault,
    SchemaMismatchFault,
]

# Maps JSON/dict keys (camelCase and snake_case) to dataclass field names
_FIELD_MAP: dict[str, str] = {
    "delayMs": "delay_ms",
    "delay_ms": "delay_ms",
    "statusCode": "status_code",
    "status_code": "status_code",
    "hangMs": "hang_ms",
    "hang_ms": "hang_ms",
    "corruptResponse": "corrupt_response",
    "corrupt_response": "corrupt_response",
    "afterBytes": "after_bytes",
    "after_bytes": "after_bytes",
    "retryAfterSeconds": "retry_after_seconds",
    "retry_after_seconds": "retry_after_seconds",
    "missingFields": "missing_fields",
    "missing_fields": "missing_fields",
    "message": "message",
}

_FAULT_BUILDERS: dict[str, type] = {
    "latency": LatencyFault,
    "error": ErrorFault,
    "timeout": TimeoutFault,
    "malformed": MalformedFault,
    "connection-refused": ConnectionRefusedFault,
    "connection-drop": ConnectionDropFault,
    "rate-limit": RateLimitFault,
    "schema-mismatch": SchemaMismatchFault,
}


def parse_fault_config(data: dict[str, Any]) -> FaultConfig:
    """Parse a dict (e.g. from JSON) into a FaultConfig dataclass."""
    fault_type = data.get("type", "")
    cls = _FAULT_BUILDERS.get(fault_type)
    if cls is None:
        raise ValueError(f"Unknown fault type: {fault_type}")

    kwargs: dict[str, Any] = {}
    unknown_keys: list[str] = []
    for key, value in data.items():
        if key in ("type", "probability"):
            continue
        mapped = _FIELD_MAP.get(key)
        if mapped is not None:
            kwargs[mapped] = value
        else:
            unknown_keys.append(key)
    if unknown_keys:
        raise ValueError(
            f"Unknown field(s) for fault type '{fault_type}': {', '.join(unknown_keys)}"
        )

    if "probability" in data and data["probability"] is not None:
        prob = float(data["probability"])
        if not (0.0 <= prob <= 1.0):
            raise ValueError(f"probability must be between 0 and 1, got {prob}")
        kwargs["probability"] = prob

    _validate_field_types(fault_type, kwargs)
    return cls(**kwargs)  # type: ignore[call-arg]


_NUMERIC_FIELDS = {"delay_ms", "status_code", "hang_ms", "retry_after_seconds", "after_bytes"}


def _validate_field_types(fault_type: str, kwargs: dict[str, Any]) -> None:
    """Validate that parsed fields have the correct types."""
    for key, value in kwargs.items():
        if key == "probability":
            continue
        if key in _NUMERIC_FIELDS:
            if value is not None and not isinstance(value, (int, float)):
                raise ValueError(
                    f"{key} must be a number for fault type '{fault_type}', got {type(value).__name__}"
                )
        elif key == "missing_fields":
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError(
                    f"missing_fields must be a list of strings for fault type '{fault_type}'"
                )
        elif key == "message":
            if value is not None and not isinstance(value, str):
                raise ValueError(
                    f"message must be a string for fault type '{fault_type}', got {type(value).__name__}"
                )
        elif key == "corrupt_response":
            if not isinstance(value, bool):
                raise ValueError(
                    f"corrupt_response must be a boolean for fault type '{fault_type}', got {type(value).__name__}"
                )
