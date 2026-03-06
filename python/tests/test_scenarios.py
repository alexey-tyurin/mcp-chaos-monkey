from __future__ import annotations

import pytest

from mcp_chaos_monkey.fault_types import ErrorFault, LatencyFault
from mcp_chaos_monkey.scenarios import ChaosScenario, ScenarioFault, define_scenario


def test_define_scenario() -> None:
    scenario = define_scenario(
        name="api-timeout",
        description="API hangs for 10s",
        faults=[
            ScenarioFault(
                target="weather-api",
                config=LatencyFault(delay_ms=10000),
            ),
        ],
        expected_behavior="Circuit opens after retries exhaust",
        assertions=["Circuit transitions to OPEN"],
    )
    assert isinstance(scenario, ChaosScenario)
    assert scenario.name == "api-timeout"
    assert len(scenario.faults) == 1
    assert scenario.assertions == ["Circuit transitions to OPEN"]


def test_define_scenario_multiple_faults() -> None:
    scenario = define_scenario(
        name="multi-fault",
        description="Multiple faults",
        faults=[
            ScenarioFault(target="a", config=ErrorFault(status_code=500)),
            ScenarioFault(target="b", config=LatencyFault(delay_ms=100)),
        ],
        expected_behavior="System degrades gracefully",
    )
    assert len(scenario.faults) == 2
    assert scenario.assertions == []


def test_define_scenario_empty_name_raises() -> None:
    with pytest.raises(ValueError, match="name is required"):
        define_scenario(
            name="",
            description="test",
            faults=[ScenarioFault(target="a", config=ErrorFault(status_code=500))],
            expected_behavior="test",
        )


def test_define_scenario_no_faults_raises() -> None:
    with pytest.raises(ValueError, match="at least one fault"):
        define_scenario(
            name="empty",
            description="test",
            faults=[],
            expected_behavior="test",
        )


def test_scenario_fault_with_duration() -> None:
    sf = ScenarioFault(
        target="redis",
        config=LatencyFault(delay_ms=500),
        duration_ms=5000,
    )
    assert sf.duration_ms == 5000
