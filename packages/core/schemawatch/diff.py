from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from schemawatch.infer import SchemaNode
from schemawatch.severity import (
    KIND_BECAME_NULLABLE,
    KIND_FIELD_ADDED,
    KIND_FIELD_MISSING,
    KIND_TYPE_CHANGED,
    SEVERITY_BREAKING,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    calculate_severity,
)


@dataclass(frozen=True)
class Change:
    """Represents a single schema drift change detected between baseline and observed schemas."""

    path: str
    kind: str
    severity: str
    was: str | None = None
    now: str | None = None
    detail: str | None = None

    @property
    def field(self) -> str:
        """Alias for path for backwards compatibility / event reporting."""
        return self.path

    @property
    def message(self) -> str:
        """Alias for detail for user-facing formatting."""
        return self.detail or ""

    def to_dict(self) -> dict[str, Any]:
        """Convert Change to dictionary."""
        return {
            "field": self.path,
            "kind": self.kind,
            "severity": self.severity,
            "was": self.was,
            "now": self.now,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DriftEvent:
    """Represents an API contract drift observation event for a vendor endpoint."""

    vendor: str
    endpoint: str
    changes: tuple[Change, ...]
    detected_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not isinstance(self.changes, tuple):
            object.__setattr__(self, "changes", tuple(self.changes))

    @property
    def highest_severity(self) -> str:
        """Return the highest severity among all changes in the event."""
        for ch in self.changes:
            if ch.severity == SEVERITY_BREAKING:
                return SEVERITY_BREAKING
        for ch in self.changes:
            if ch.severity == SEVERITY_WARNING:
                return SEVERITY_WARNING
        return SEVERITY_INFO

    def to_dict(self) -> dict[str, Any]:
        """Convert DriftEvent to dictionary."""
        return {
            "vendor": self.vendor,
            "endpoint": self.endpoint,
            "highest_severity": self.highest_severity,
            "detected_at": self.detected_at,
            "changes": [c.to_dict() for c in self.changes],
        }


def _type_allowed(observed_type: str, baseline_types: set[str]) -> bool:
    """Check if an observed type is compatible with baseline types.

    Rule: integer is compatible with number (integer is allowed where number is expected).
    """
    if observed_type in baseline_types:
        return True
    if observed_type == "integer" and "number" in baseline_types:
        return True
    return False


def diff(baseline: SchemaNode, observed: SchemaNode, path: str = "$") -> list[Change]:
    """Compare an observed schema against a baseline schema and return all detected changes.

    Follows the system design rules:
    - became_nullable: breaking
    - type_changed: breaking (does not descend into children on mismatch)
    - field_missing: breaking if required, info if optional
    - field_added: info
    """
    changes: list[Change] = []

    # 1. Nullability check
    if "null" in observed.types and "null" not in baseline.types:
        was_types = ", ".join(sorted(baseline.types)) or "non-null"
        changes.append(
            Change(
                path=path,
                kind=KIND_BECAME_NULLABLE,
                severity=calculate_severity(KIND_BECAME_NULLABLE),
                was=was_types,
                now="null",
                detail="became nullable",
            )
        )

    # 2. Type mismatch check on non-null types
    obs_non_null = observed.types - {"null"}
    base_non_null = baseline.types - {"null"}

    if obs_non_null:
        # Check if all observed non-null types are allowed by baseline
        disallowed = [t for t in obs_non_null if not _type_allowed(t, base_non_null)]
        if disallowed:
            was_str = ", ".join(sorted(base_non_null)) or ", ".join(sorted(baseline.types))
            now_str = ", ".join(sorted(obs_non_null))
            changes.append(
                Change(
                    path=path,
                    kind=KIND_TYPE_CHANGED,
                    severity=calculate_severity(KIND_TYPE_CHANGED),
                    was=was_str,
                    now=now_str,
                    detail=f"{was_str} -> {now_str}",
                )
            )
            # Crucial rule from System Design:
            # "When a type mismatch is found at a node, comparison does not descend further,
            # which avoids noisy child changes."
            return changes

    # 3. Object property comparisons
    if "object" in baseline.types and "object" in observed.types:
        if "*" in baseline.properties:
            # Baseline is a wildcard map: match observed properties against wildcard schema
            for prop in observed.properties:
                child_path = f"{path}.*"
                changes.extend(
                    diff(
                        baseline.properties["*"],
                        observed.properties[prop],
                        path=child_path,
                    )
                )
        elif "*" in observed.properties:
            # Baseline was normal object, but observed became a wildcard map
            for prop in baseline.properties:
                prop_path = f"{path}.{prop}"
                is_req = prop in baseline.required
                changes.append(
                    Change(
                        path=prop_path,
                        kind=KIND_FIELD_MISSING,
                        severity=calculate_severity(KIND_FIELD_MISSING, is_required=is_req),
                        was="present",
                        now="missing",
                        detail=(
                            "required field is missing" if is_req else "optional field is missing"
                        ),
                    )
                )
            changes.append(
                Change(
                    path=f"{path}.*",
                    kind=KIND_FIELD_ADDED,
                    severity=calculate_severity(KIND_FIELD_ADDED),
                    was="absent",
                    now="present",
                    detail="new field added",
                )
            )
        else:
            # Normal object comparisons
            for prop in baseline.properties:
                if prop not in observed.properties:
                    prop_path = f"{path}.{prop}"
                    is_req = prop in baseline.required
                    severity = calculate_severity(KIND_FIELD_MISSING, is_required=is_req)
                    detail = "required field is missing" if is_req else "optional field is missing"
                    changes.append(
                        Change(
                            path=prop_path,
                            kind=KIND_FIELD_MISSING,
                            severity=severity,
                            was="present",
                            now="missing",
                            detail=detail,
                        )
                    )

            # Check for added properties
            for prop in observed.properties:
                if prop not in baseline.properties:
                    prop_path = f"{path}.{prop}"
                    changes.append(
                        Change(
                            path=prop_path,
                            kind=KIND_FIELD_ADDED,
                            severity=calculate_severity(KIND_FIELD_ADDED),
                            was="absent",
                            now="present",
                            detail="new field added",
                        )
                    )

            # Recurse for shared properties
            for prop in baseline.properties:
                if prop in observed.properties:
                    prop_path = f"{path}.{prop}"
                    changes.extend(
                        diff(
                            baseline.properties[prop],
                            observed.properties[prop],
                            path=prop_path,
                        )
                    )

    # 4. Array item comparisons
    if "array" in baseline.types and "array" in observed.types:
        if baseline.items is not None and observed.items is not None:
            changes.extend(
                diff(
                    baseline.items,
                    observed.items,
                    path=f"{path}[*]",
                )
            )

    return changes
