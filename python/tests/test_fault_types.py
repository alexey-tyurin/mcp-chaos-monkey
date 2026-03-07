from __future__ import annotations

import pytest

from mcp_chaos_monkey.fault_types import parse_fault_config


def test_parse_latency_fault() -> None:
    config = parse_fault_config({"type": "latency", "delay_ms": 500})
    assert config.type == "latency"
    assert config.delay_ms == 500  # type: ignore[union-attr]


def test_parse_camel_case_keys() -> None:
    config = parse_fault_config({"type": "latency", "delayMs": 200})
    assert config.delay_ms == 200  # type: ignore[union-attr]


def test_parse_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="Unknown fault type"):
        parse_fault_config({"type": "bogus"})


def test_parse_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="Unknown field"):
        parse_fault_config({"type": "latency", "delayMs": 100, "badField": True})


def test_parse_rejects_non_numeric_delay_ms() -> None:
    with pytest.raises(ValueError, match="delay_ms must be a number"):
        parse_fault_config({"type": "latency", "delayMs": "not_a_number"})


def test_parse_rejects_non_numeric_status_code() -> None:
    with pytest.raises(ValueError, match="status_code must be a number"):
        parse_fault_config({"type": "error", "statusCode": "abc"})


def test_parse_rejects_non_numeric_hang_ms() -> None:
    with pytest.raises(ValueError, match="hang_ms must be a number"):
        parse_fault_config({"type": "timeout", "hangMs": []})


def test_parse_rejects_non_list_missing_fields() -> None:
    with pytest.raises(ValueError, match="missing_fields must be a list of strings"):
        parse_fault_config({"type": "schema-mismatch", "missingFields": 42})


def test_parse_rejects_non_string_items_in_missing_fields() -> None:
    with pytest.raises(ValueError, match="missing_fields must be a list of strings"):
        parse_fault_config({"type": "schema-mismatch", "missingFields": [1, 2, 3]})


def test_parse_rejects_non_string_message() -> None:
    with pytest.raises(ValueError, match="message must be a string"):
        parse_fault_config({"type": "error", "statusCode": 500, "message": 123})


def test_parse_rejects_non_bool_corrupt_response() -> None:
    with pytest.raises(ValueError, match="corrupt_response must be a boolean"):
        parse_fault_config({"type": "malformed", "corruptResponse": "yes"})


def test_parse_accepts_valid_schema_mismatch() -> None:
    config = parse_fault_config({
        "type": "schema-mismatch",
        "missingFields": ["field1", "field2"],
    })
    assert config.type == "schema-mismatch"
    assert config.missing_fields == ["field1", "field2"]  # type: ignore[union-attr]


def test_parse_rejects_negative_delay_ms() -> None:
    """Fix: Negative numeric fields should be rejected."""
    with pytest.raises(ValueError, match="non-negative"):
        parse_fault_config({"type": "latency", "delayMs": -500})


def test_parse_rejects_negative_status_code() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        parse_fault_config({"type": "error", "statusCode": -1})


def test_parse_rejects_negative_hang_ms() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        parse_fault_config({"type": "timeout", "hangMs": -100})


def test_parse_rejects_negative_retry_after() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        parse_fault_config({"type": "rate-limit", "retryAfterSeconds": -10})


def test_parse_accepts_valid_error_with_message() -> None:
    config = parse_fault_config({
        "type": "error",
        "statusCode": 503,
        "message": "service down",
    })
    assert config.type == "error"
    assert config.message == "service down"  # type: ignore[union-attr]
