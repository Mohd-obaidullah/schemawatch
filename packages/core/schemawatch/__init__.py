from __future__ import annotations

from schemawatch.diff import Change, diff
from schemawatch.infer import SchemaNode, infer_schema, merge
from schemawatch.redact import redact
from schemawatch.severity import (
    KIND_BECAME_NULLABLE,
    KIND_ENUM_CHANGED,
    KIND_FIELD_ADDED,
    KIND_FIELD_MISSING,
    KIND_TYPE_CHANGED,
    SEVERITY_BREAKING,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    calculate_severity,
)
from schemawatch.store import MemoryStore, RedisStore, Store
from schemawatch.watchdog import Watchdog

__all__ = [
    "Change",
    "KIND_BECAME_NULLABLE",
    "KIND_ENUM_CHANGED",
    "KIND_FIELD_ADDED",
    "KIND_FIELD_MISSING",
    "KIND_TYPE_CHANGED",
    "MemoryStore",
    "RedisStore",
    "SEVERITY_BREAKING",
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    "SchemaNode",
    "Store",
    "Watchdog",
    "calculate_severity",
    "diff",
    "infer_schema",
    "merge",
    "redact",
]
