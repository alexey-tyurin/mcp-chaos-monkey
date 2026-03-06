from __future__ import annotations

from dataclasses import dataclass, field

from .fault_types import FaultConfig, FaultTarget


@dataclass
class ScenarioFault:
    target: FaultTarget
    config: FaultConfig
    duration_ms: int | None = None


@dataclass
class ChaosScenario:
    name: str
    description: str
    faults: list[ScenarioFault]
    expected_behavior: str
    assertions: list[str] = field(default_factory=list)


def define_scenario(
    *,
    name: str,
    description: str,
    faults: list[ScenarioFault],
    expected_behavior: str,
    assertions: list[str] | None = None,
) -> ChaosScenario:
    """Build a ChaosScenario with validation."""
    if not name:
        raise ValueError("Scenario name is required")
    if not faults:
        raise ValueError("Scenario must have at least one fault")
    return ChaosScenario(
        name=name,
        description=description,
        faults=faults,
        expected_behavior=expected_behavior,
        assertions=assertions or [],
    )
