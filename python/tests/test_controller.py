from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from mcp_chaos_monkey.controller import ChaosController
from mcp_chaos_monkey.fault_types import ErrorFault, LatencyFault


def test_singleton() -> None:
    c1 = ChaosController.get_instance()
    c2 = ChaosController.get_instance()
    assert c1 is c2


def test_inject_and_get_fault() -> None:
    controller = ChaosController.get_instance()
    fault = ErrorFault(status_code=503)
    fault_id = controller.inject("weather-api", fault)

    assert fault_id.startswith("weather-api-")
    result = controller.get_fault("weather-api")
    assert result is not None
    assert result.type == "error"
    assert result.status_code == 503  # type: ignore[union-attr]


def test_get_fault_returns_none_for_unknown_target() -> None:
    controller = ChaosController.get_instance()
    assert controller.get_fault("nonexistent") is None


def test_clear_fault() -> None:
    controller = ChaosController.get_instance()
    fault_id = controller.inject("redis", LatencyFault(delay_ms=100))
    controller.clear(fault_id)
    assert controller.get_fault("redis") is None


def test_clear_all() -> None:
    controller = ChaosController.get_instance()
    controller.inject("a", ErrorFault(status_code=500))
    controller.inject("b", LatencyFault(delay_ms=50))
    controller.clear_all()
    assert controller.get_fault("a") is None
    assert controller.get_fault("b") is None
    assert controller.get_active_faults() == []


def test_get_active_faults() -> None:
    controller = ChaosController.get_instance()
    controller.inject("target1", ErrorFault(status_code=503))
    controller.inject("target2", LatencyFault(delay_ms=100))
    faults = controller.get_active_faults()
    assert len(faults) == 2
    targets = {f.target for f in faults}
    assert targets == {"target1", "target2"}


def test_fault_expiry() -> None:
    controller = ChaosController.get_instance()
    controller.inject("expiring", LatencyFault(delay_ms=10), duration_ms=1)
    time.sleep(0.01)
    assert controller.get_fault("expiring") is None


def test_fault_probability() -> None:
    controller = ChaosController.get_instance()
    # Probability 0 = never triggers
    controller.inject("prob-test", ErrorFault(status_code=500, probability=0.0))
    with patch("mcp_chaos_monkey.controller.random.random", return_value=0.5):
        assert controller.get_fault("prob-test") is None

    controller.clear_all()
    # Probability 1.0 = always triggers
    controller.inject("prob-test", ErrorFault(status_code=500, probability=1.0))
    with patch("mcp_chaos_monkey.controller.random.random", return_value=0.5):
        assert controller.get_fault("prob-test") is not None


def test_request_count_increments() -> None:
    controller = ChaosController.get_instance()
    controller.inject("counter", ErrorFault(status_code=500))
    controller.get_fault("counter")
    controller.get_fault("counter")
    faults = controller.get_active_faults()
    assert faults[0].request_count == 2


def test_reset() -> None:
    _ = ChaosController.get_instance()
    ChaosController.reset()
    assert ChaosController._instance is None


def test_get_active_faults_filters_expired() -> None:
    """Fix #3: get_active_faults should not return expired faults."""
    controller = ChaosController.get_instance()
    controller.inject("active-target", ErrorFault(status_code=500))
    controller.inject("expired-target", LatencyFault(delay_ms=10), duration_ms=1)
    time.sleep(0.01)
    faults = controller.get_active_faults()
    targets = {f.target for f in faults}
    assert "active-target" in targets
    assert "expired-target" not in targets


def test_get_fault_cleans_expired_without_dict_mutation_error() -> None:
    """Fix #8: expired faults should be cleaned up safely (no dict mutation during iteration)."""
    controller = ChaosController.get_instance()
    # Inject an expired fault and an active fault for the same target
    controller.inject("target", LatencyFault(delay_ms=10), duration_ms=1)
    controller.inject("target", ErrorFault(status_code=503))
    time.sleep(0.01)
    # Should not raise RuntimeError from dict mutation during iteration
    result = controller.get_fault("target")
    assert result is not None
    assert result.type == "error"


def test_probability_out_of_range_rejected() -> None:
    """Fix #10: probability outside [0,1] should be rejected."""
    from mcp_chaos_monkey.fault_types import parse_fault_config

    with pytest.raises(ValueError, match="probability must be between 0 and 1"):
        parse_fault_config({"type": "error", "status_code": 500, "probability": 2.0})

    with pytest.raises(ValueError, match="probability must be between 0 and 1"):
        parse_fault_config({"type": "error", "status_code": 500, "probability": -0.5})


def test_clear_returns_true_for_existing_fault() -> None:
    controller = ChaosController.get_instance()
    fault_id = controller.inject("api", ErrorFault(status_code=503))
    assert controller.clear(fault_id) is True


def test_clear_returns_false_for_nonexistent_fault() -> None:
    controller = ChaosController.get_instance()
    assert controller.clear("nonexistent-id") is False


def test_inject_rejects_negative_duration_ms() -> None:
    controller = ChaosController.get_instance()
    with pytest.raises(ValueError, match="duration_ms must be a non-negative number"):
        controller.inject("api", ErrorFault(status_code=503), duration_ms=-100)


def test_inject_rejects_non_numeric_duration_ms() -> None:
    controller = ChaosController.get_instance()
    with pytest.raises(ValueError, match="duration_ms must be a non-negative number"):
        controller.inject("api", ErrorFault(status_code=503), duration_ms="abc")  # type: ignore[arg-type]


def test_inject_accepts_zero_duration_ms() -> None:
    controller = ChaosController.get_instance()
    fault_id = controller.inject("api", ErrorFault(status_code=503), duration_ms=0)
    assert fault_id.startswith("api-")


def test_max_faults_limit() -> None:
    """MEM-1: Controller should reject faults when exceeding MAX_FAULTS."""
    from mcp_chaos_monkey.controller import MAX_FAULTS

    controller = ChaosController.get_instance()
    for i in range(MAX_FAULTS):
        controller.inject(f"target-{i}", ErrorFault(status_code=500))
    with pytest.raises(ValueError, match="Maximum number of active faults"):
        controller.inject("one-too-many", ErrorFault(status_code=500))
