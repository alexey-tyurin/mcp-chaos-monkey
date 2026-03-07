"""mcp-chaos-monkey — Chaos/fault injection framework for MCP projects."""

# Core
# Admin (framework-agnostic handlers)
from .admin_endpoint import handle_clear, handle_clear_all, handle_inject, handle_status

# CLI
from .cli import run_cli
from .controller import ActiveFaultInfo, ChaosController
from .fault_types import (
    ConnectionDropFault,
    ConnectionRefusedFault,
    ErrorFault,
    FaultConfig,
    FaultTarget,
    FaultType,
    LatencyFault,
    MalformedFault,
    RateLimitFault,
    SchemaMismatchFault,
    TimeoutFault,
    is_fault_target,
    parse_fault_config,
)
from .guard import ChaosNotAllowedError, assert_chaos_allowed

# Logger
from .logger import ChaosLogger, configure_chaos_logger, create_default_logger

# Scenarios
from .scenarios import ChaosScenario, ScenarioFault, define_scenario

__all__ = [
    # Core
    "assert_chaos_allowed",
    "ChaosNotAllowedError",
    "ChaosController",
    "ActiveFaultInfo",
    "FaultConfig",
    "FaultTarget",
    "FaultType",
    "LatencyFault",
    "ErrorFault",
    "TimeoutFault",
    "MalformedFault",
    "ConnectionRefusedFault",
    "ConnectionDropFault",
    "RateLimitFault",
    "SchemaMismatchFault",
    "is_fault_target",
    "parse_fault_config",
    # Logger
    "ChaosLogger",
    "configure_chaos_logger",
    "create_default_logger",
    # Scenarios
    "ChaosScenario",
    "ScenarioFault",
    "define_scenario",
    # Admin
    "handle_status",
    "handle_inject",
    "handle_clear",
    "handle_clear_all",
    # CLI
    "run_cli",
]
