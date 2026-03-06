from __future__ import annotations

import argparse
import sys

from .controller import ChaosController
from .fault_types import (
    ConnectionDropFault,
    ConnectionRefusedFault,
    ErrorFault,
    FaultConfig,
    FaultType,
    LatencyFault,
    MalformedFault,
    RateLimitFault,
    SchemaMismatchFault,
    TimeoutFault,
)
from .guard import assert_chaos_allowed

VALID_FAULT_TYPES = [t.value for t in FaultType]


def _build_fault_config(args: argparse.Namespace) -> FaultConfig:
    fault_type = args.fault_type
    match fault_type:
        case "latency":
            return LatencyFault(delay_ms=args.delay)
        case "error":
            return ErrorFault(status_code=args.status)
        case "timeout":
            return TimeoutFault(hang_ms=args.delay)
        case "malformed":
            return MalformedFault(corrupt_response=True)
        case "connection-refused":
            return ConnectionRefusedFault()
        case "connection-drop":
            return ConnectionDropFault()
        case "rate-limit":
            return RateLimitFault(retry_after_seconds=args.retry_after)
        case "schema-mismatch":
            fields = args.fields.split(",") if args.fields else []
            return SchemaMismatchFault(missing_fields=fields)
        case _:
            raise ValueError(f"Unknown fault type: {fault_type}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-chaos",
        description="Chaos/fault injection CLI for MCP projects",
    )
    sub = parser.add_subparsers(dest="command")

    inject_p = sub.add_parser("inject", help="Inject a fault")
    inject_p.add_argument("target", help="Target name (e.g. weather-api, redis)")
    inject_p.add_argument(
        "fault_type", choices=VALID_FAULT_TYPES, help="Fault type to inject"
    )
    inject_p.add_argument("--status", type=int, default=503, help="HTTP status code")
    inject_p.add_argument("--delay", type=int, default=1000, help="Delay in ms")
    inject_p.add_argument(
        "--retry-after", type=int, default=60, help="Retry-After seconds"
    )
    inject_p.add_argument("--fields", default="", help="Comma-separated field names")
    inject_p.add_argument(
        "--duration", type=int, default=None, help="Auto-expire after N seconds"
    )

    clear_p = sub.add_parser("clear", help="Clear a specific fault")
    clear_p.add_argument("fault_id", help="Fault ID to clear")

    sub.add_parser("clear-all", help="Clear all faults")
    sub.add_parser("status", help="Show active faults")

    return parser


def run_cli(argv: list[str] | None = None) -> None:
    """Run the chaos CLI with the given arguments."""
    assert_chaos_allowed()

    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return

    match args.command:
        case "inject":
            config = _build_fault_config(args)
            duration_ms = args.duration * 1000 if args.duration else None
            controller = ChaosController.get_instance()
            fault_id = controller.inject(args.target, config, duration_ms)
            print(f"Injected fault: {fault_id}")

        case "clear":
            controller = ChaosController.get_instance()
            controller.clear(args.fault_id)
            print(f"Cleared fault: {args.fault_id}")

        case "clear-all":
            controller = ChaosController.get_instance()
            controller.clear_all()
            print("All faults cleared")

        case "status":
            controller = ChaosController.get_instance()
            faults = controller.get_active_faults()
            if not faults:
                print("No active faults")
            else:
                print(f"Active faults ({len(faults)}):")
                for f in faults:
                    print(
                        f"  {f.id} → {f.target} [{f.type}] ({f.request_count} requests)"
                    )


def main() -> None:
    """Entry point for the mcp-chaos console script."""
    run_cli(sys.argv[1:])
