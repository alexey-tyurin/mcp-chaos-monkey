from __future__ import annotations

import pytest

from mcp_chaos_monkey.cli import run_cli
from mcp_chaos_monkey.controller import ChaosController


def test_inject_and_status(capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(["inject", "weather-api", "error", "--status", "503"])
    captured = capsys.readouterr()
    assert "Injected fault:" in captured.out
    assert "weather-api" in captured.out

    run_cli(["status"])
    captured = capsys.readouterr()
    assert "Active faults (1):" in captured.out
    assert "weather-api" in captured.out
    assert "[error]" in captured.out


def test_inject_latency(capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(["inject", "redis", "latency", "--delay", "500"])
    captured = capsys.readouterr()
    assert "Injected fault:" in captured.out


def test_clear(capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(["inject", "target", "timeout", "--delay", "2000"])
    captured = capsys.readouterr()
    fault_id = captured.out.strip().split(": ")[1]

    run_cli(["clear", fault_id])
    captured = capsys.readouterr()
    assert f"Cleared fault: {fault_id}" in captured.out


def test_clear_all(capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(["inject", "a", "error", "--status", "500"])
    run_cli(["inject", "b", "latency"])
    run_cli(["clear-all"])
    captured = capsys.readouterr()
    assert "All faults cleared" in captured.out

    run_cli(["status"])
    captured = capsys.readouterr()
    assert "No active faults" in captured.out


def test_status_no_faults(capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(["status"])
    captured = capsys.readouterr()
    assert "No active faults" in captured.out


def test_inject_with_duration(capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(["inject", "api", "error", "--status", "503", "--duration", "10"])
    captured = capsys.readouterr()
    assert "Injected fault:" in captured.out


def test_no_command_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    run_cli([])
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower() or "mcp-chaos" in captured.out.lower()
