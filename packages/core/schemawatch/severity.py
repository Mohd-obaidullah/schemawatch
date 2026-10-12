from __future__ import annotations

from typing import Final

# Severity levels (AGENTS.md section 6)
SEVERITY_BREAKING: Final[str] = "breaking"
SEVERITY_WARNING: Final[str] = "warning"
SEVERITY_INFO: Final[str] = "info"

# Change kinds (AGENTS.md section 6)
KIND_TYPE_CHANGED: Final[str] = "type_changed"
KIND_FIELD_MISSING: Final[str] = "field_missing"
KIND_FIELD_ADDED: Final[str] = "field_added"
KIND_BECAME_NULLABLE: Final[str] = "became_nullable"
KIND_ENUM_CHANGED: Final[str] = "enum_changed"

VALID_SEVERITIES: Final[frozenset[str]] = frozenset(
    {
        SEVERITY_BREAKING,
        SEVERITY_WARNING,
        SEVERITY_INFO,
    }
)

VALID_KINDS: Final[frozenset[str]] = frozenset(
    {
        KIND_TYPE_CHANGED,
        KIND_FIELD_MISSING,
        KIND_FIELD_ADDED,
        KIND_BECAME_NULLABLE,
        KIND_ENUM_CHANGED,
    }
)


def calculate_severity(kind: str, *, is_required: bool = True) -> str:
    """Calculate the severity level for a detected schema change.

    Rules according to PRD / System Design:
    - type_changed: breaking
    - became_nullable: breaking
    - required field_missing: breaking
    - optional field_missing: info
    - field_added: info
    - enum_changed: warning

    Args:
        kind: The kind of change (type_changed, field_missing, etc.).
        is_required: Whether the missing field is required (relevant for field_missing).

    Returns:
        One of 'breaking', 'warning', or 'info'.
    """
    if kind == KIND_TYPE_CHANGED:
        return SEVERITY_BREAKING
    if kind == KIND_BECAME_NULLABLE:
        return SEVERITY_BREAKING
    if kind == KIND_FIELD_MISSING:
        return SEVERITY_BREAKING if is_required else SEVERITY_INFO
    if kind == KIND_FIELD_ADDED:
        return SEVERITY_INFO
    if kind == KIND_ENUM_CHANGED:
        return SEVERITY_WARNING
    return SEVERITY_INFO
