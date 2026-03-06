from __future__ import annotations

import random
import string
import threading
import time
from dataclasses import dataclass

from .fault_types import FaultConfig, FaultTarget
from .guard import assert_chaos_allowed
from .logger import get_logger

logger = get_logger("chaos-controller")


@dataclass
class _ActiveFault:
    target: FaultTarget
    config: FaultConfig
    activated_at: float
    expires_at: float | None
    request_count: int


@dataclass
class ActiveFaultInfo:
    """Public read-only view of an active fault."""

    id: str
    target: str
    type: str
    request_count: int


class ChaosController:
    _instance: ChaosController | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        assert_chaos_allowed()
        self._faults: dict[str, _ActiveFault] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ChaosController:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def inject(
        self,
        target: FaultTarget,
        config: FaultConfig,
        duration_ms: int | None = None,
    ) -> str:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        now = time.time() * 1000
        fault_id = f"{target}-{int(now)}-{suffix}"
        with self._lock:
            self._faults[fault_id] = _ActiveFault(
                target=target,
                config=config,
                activated_at=now,
                expires_at=now + duration_ms if duration_ms is not None else None,
                request_count=0,
            )
        logger.warning(
            "Chaos fault injected: %s target=%s type=%s",
            fault_id,
            target,
            config.type,
        )
        return fault_id

    def clear(self, fault_id: str) -> None:
        with self._lock:
            self._faults.pop(fault_id, None)
        logger.info("Chaos fault cleared: %s", fault_id)

    def clear_all(self) -> None:
        with self._lock:
            self._faults.clear()
        logger.info("All chaos faults cleared")

    def get_fault(self, target: FaultTarget) -> FaultConfig | None:
        now = time.time() * 1000
        with self._lock:
            expired: list[str] = []
            matched_config: FaultConfig | None = None
            for fault_id, fault in self._faults.items():
                if fault.target != target:
                    continue
                if fault.expires_at is not None and now > fault.expires_at:
                    expired.append(fault_id)
                    continue
                if matched_config is None:
                    if (
                        fault.config.probability is not None
                        and random.random() > fault.config.probability
                    ):
                        continue
                    fault.request_count += 1
                    matched_config = fault.config
            for eid in expired:
                self._faults.pop(eid, None)
        return matched_config

    def get_active_faults(self) -> list[ActiveFaultInfo]:
        with self._lock:
            return [
                ActiveFaultInfo(
                    id=fault_id,
                    target=fault.target,
                    type=fault.config.type,
                    request_count=fault.request_count,
                )
                for fault_id, fault in self._faults.items()
            ]

    @classmethod
    def reset(cls) -> None:
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.clear_all()
            cls._instance = None
