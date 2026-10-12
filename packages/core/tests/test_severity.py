from __future__ import annotations

import pytest
from schemawatch.severity import (
    KIND_BECAME_NULLABLE,
    KIND_ENUM_CHANGED,
    KIND_FIELD_ADDED,
    KIND_FIELD_MISSING,
    KIND_TYPE_CHANGED,
    SEVERITY_BREAKING,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    VALID_KINDS,
    VALID_SEVERITIES,
    calculate_severity,
)


@pytest.mark.parametrize(
    ("kind", "is_required", "expected_severity"),
    [
        (KIND_TYPE_CHANGED, True, SEVERITY_BREAKING),
        (KIND_TYPE_CHANGED, False, SEVERITY_BREAKING),
        (KIND_BECAME_NULLABLE, True, SEVERITY_BREAKING),
        (KIND_BECAME_NULLABLE, False, SEVERITY_BREAKING),
        (KIND_FIELD_MISSING, True, SEVERITY_BREAKING),
        (KIND_FIELD_MISSING, False, SEVERITY_INFO),
        (KIND_FIELD_ADDED, True, SEVERITY_INFO),
        (KIND_FIELD_ADDED, False, SEVERITY_INFO),
        (KIND_ENUM_CHANGED, True, SEVERITY_WARNING),
        (KIND_ENUM_CHANGED, False, SEVERITY_WARNING),
    ],
)
def test_calculate_severity_rules(kind: str, is_required: bool, expected_severity: str) -> None:
    result = calculate_severity(kind, is_required=is_required)
    assert result == expected_severity
    assert result in VALID_SEVERITIES


def test_calculate_severity_unknown_kind() -> None:
    assert calculate_severity("unknown_arbitrary_kind") == SEVERITY_INFO


def test_valid_kinds_and_severities() -> None:
    assert "breaking" in VALID_SEVERITIES
    assert "warning" in VALID_SEVERITIES
    assert "info" in VALID_SEVERITIES
    assert "type_changed" in VALID_KINDS
    assert "field_missing" in VALID_KINDS
    assert "field_added" in VALID_KINDS
    assert "became_nullable" in VALID_KINDS
