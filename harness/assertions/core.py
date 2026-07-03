from __future__ import annotations

from typing import Any


def assert_expected_subset(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, expected_value in expected.items():
        if key not in actual:
            errors.append(f"Missing key: {key}")
            continue
        actual_value = actual[key]
        if isinstance(expected_value, dict) and isinstance(actual_value, dict):
            child_errors = assert_expected_subset(actual_value, expected_value)
            errors.extend(f"{key}.{error}" for error in child_errors)
        elif actual_value != expected_value:
            errors.append(f"{key}: expected {expected_value!r}, got {actual_value!r}")
    return errors
