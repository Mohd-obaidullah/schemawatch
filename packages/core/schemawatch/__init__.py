from __future__ import annotations

from typing import TYPE_CHECKING, Any

from schemawatch.diff import Change, DriftEvent, diff
from schemawatch.infer import SchemaNode, infer_schema, merge
from schemawatch.redact import DYNAMIC_KEY_WILDCARD, DynamicKeyWildcard, redact
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

if TYPE_CHECKING:
    from schemawatch.alerts import SlackAlert, WebhookAlert, fan_out
    from schemawatch.integrations.httpx_hook import SchemawatchHTTPXHook, create_httpx_hook

__all__ = [
    "Change",
    "DYNAMIC_KEY_WILDCARD",
    "DriftEvent",
    "DynamicKeyWildcard",
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
    "SchemawatchHTTPXHook",
    "SlackAlert",
    "Store",
    "Watchdog",
    "WebhookAlert",
    "calculate_severity",
    "create_httpx_hook",
    "diff",
    "fan_out",
    "infer_schema",
    "merge",
    "redact",
]


def __getattr__(name: str) -> Any:
    """Lazy module exports so 'import schemawatch' works without httpx installed."""
    if name in ("SlackAlert", "WebhookAlert", "fan_out"):
        import schemawatch.alerts as alerts

        return getattr(alerts, name)
    if name in ("SchemawatchHTTPXHook", "create_httpx_hook"):
        import schemawatch.integrations.httpx_hook as httpx_hook

        return getattr(httpx_hook, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
