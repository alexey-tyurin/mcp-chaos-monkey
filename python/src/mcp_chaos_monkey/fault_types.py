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
    for key, value in data.items():
        if key in ("type", "probability"):
            continue
        mapped = _FIELD_MAP.get(key)
        if mapped is not None:
            kwargs[mapped] = value

    if "probability" in data and data["probability"] is not None:
        kwargs["probability"] = float(data["probability"])

    return cls(**kwargs)  # type: ignore[call-arg]
