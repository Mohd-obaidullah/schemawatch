from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

DEFAULT_MAX_PAYLOAD_BYTES: int = 1_000_000  # 1 MB
DEFAULT_MAX_ARRAY_LENGTH: int = 10
DEFAULT_MAX_OBJECT_KEYS: int = 50
DEFAULT_MAX_NESTING_DEPTH: int = 32

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_LONG_DIGIT_RE = re.compile(r"^\d{8,}$")
_LONG_HEX_RE = re.compile(r"^[0-9a-fA-F]{16,}$")


class DynamicKeyWildcard(str):
    """Sentinel representing a dynamic-key wildcard map (*).

    Distinct from any literal string key.
    """

    _instance: DynamicKeyWildcard | None = None

    def __new__(cls) -> DynamicKeyWildcard:
        if cls._instance is None:
            cls._instance = super().__new__(cls, "*")
        return cls._instance

    def __repr__(self) -> str:
        return "DYNAMIC_KEY_WILDCARD"

    def __eq__(self, other: object) -> bool:
        return other is self

    def __hash__(self) -> int:
        return hash("__dynamic_key_wildcard__")

    def __copy__(self) -> DynamicKeyWildcard:
        return self

    def __deepcopy__(self, memo: Any) -> DynamicKeyWildcard:
        return self

    def __reduce__(self) -> str | tuple[Any, ...]:
        return (DynamicKeyWildcard, ())


DYNAMIC_KEY_WILDCARD = DynamicKeyWildcard()


def is_dynamic_key(key: Any) -> bool:
    """Check if key looks like an email, UUID, long digit string, or long hex string."""
    k = str(key).strip()
    return bool(
        _EMAIL_RE.match(k) or _UUID_RE.match(k) or _LONG_DIGIT_RE.match(k) or _LONG_HEX_RE.match(k)
    )


def is_dynamic_map(keys: Iterable[Any], max_keys: int = DEFAULT_MAX_OBJECT_KEYS) -> bool:
    """Determine whether an object should be treated as a dynamic map (wildcard '*').

    Criteria according to AGENTS.md / PRD:
    - More than max_keys (default 50) distinct keys; OR
    - >= 50% of its keys (minimum 3 matching keys) look like emails, UUIDs,
      long digit strings, or long hex strings.
    """
    key_list = list(keys)
    if any(k is DYNAMIC_KEY_WILDCARD for k in key_list):
        return True
    key_str_list = [str(k) for k in key_list]
    total = len(key_str_list)
    if total > max_keys:
        return True
    if total < 3:
        return False
    dynamic_count = sum(1 for k in key_str_list if is_dynamic_key(k))
    return dynamic_count >= 3 and (dynamic_count / total) >= 0.5


class PayloadTooLargeError(ValueError):
    """Raised when a payload exceeds the maximum allowed size."""


class InvalidPayloadError(ValueError):
    """Raised when a payload is not valid JSON or a JSON-serializable structure."""


def redact(
    payload: Any,
    *,
    max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
    max_array_length: int = DEFAULT_MAX_ARRAY_LENGTH,
    max_object_keys: int = DEFAULT_MAX_OBJECT_KEYS,
    max_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> Any:
    """Sanitize a payload by replacing raw values with type-preserving placeholders.

    Enforces size limits and truncates arrays to prevent excessive memory and processing.
    Ensures that no raw sensitive data (strings, numbers, booleans) can leak into downstream
    inference, baselines, or alert diffs.

    Args:
        payload: A JSON-compatible data structure (dict, list, primitive) or JSON string/bytes.
        max_payload_bytes: Maximum allowed payload size in bytes.
        max_array_length: Maximum number of elements to retain per array.

    Returns:
        Redacted payload preserving structure and types, or None if payload is empty/None.

    Raises:
        PayloadTooLargeError: If payload exceeds max_payload_bytes.
        InvalidPayloadError: If string/bytes payload cannot be parsed as JSON.
    """
    if isinstance(payload, (bytes, bytearray)):
        if len(payload) > max_payload_bytes:
            raise PayloadTooLargeError(
                f"Payload size ({len(payload)} bytes) exceeds limit ({max_payload_bytes} bytes)"
            )
        try:
            decoded = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidPayloadError(f"Could not decode payload as UTF-8: {exc}") from exc
        stripped = decoded.strip()
        if stripped.startswith(("{", "[")):
            try:
                payload = json.loads(decoded)
            except Exception as exc:
                raise InvalidPayloadError(f"Could not parse payload as JSON: {exc}") from exc
        else:
            try:
                payload = json.loads(decoded)
            except Exception:
                payload = decoded
    elif isinstance(payload, str):
        payload_bytes_len = len(payload.encode("utf-8"))
        if payload_bytes_len > max_payload_bytes:
            raise PayloadTooLargeError(
                f"Payload size ({payload_bytes_len} bytes) "
                f"exceeds limit ({max_payload_bytes} bytes)"
            )
        stripped = payload.strip()
        if stripped.startswith(("{", "[")):
            try:
                payload = json.loads(payload)
            except Exception as exc:
                raise InvalidPayloadError(f"Could not parse payload as JSON: {exc}") from exc
        else:
            try:
                payload = json.loads(payload)
            except Exception:
                pass
    else:
        # For in-memory objects, check rough size via JSON serialization
        try:
            encoded_len = len(json.dumps(payload).encode("utf-8"))
            if encoded_len > max_payload_bytes:
                raise PayloadTooLargeError(
                    f"Payload size ({encoded_len} bytes) exceeds limit ({max_payload_bytes} bytes)"
                )
        except (TypeError, OverflowError) as exc:
            raise InvalidPayloadError(f"Payload is not JSON-serializable: {exc}") from exc

    return _redact_value(
        payload,
        max_array_length=max_array_length,
        max_object_keys=max_object_keys,
        current_depth=0,
        max_depth=max_depth,
    )


def _redact_value(
    value: Any,
    *,
    max_array_length: int,
    max_object_keys: int = DEFAULT_MAX_OBJECT_KEYS,
    current_depth: int = 0,
    max_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> Any:
    """Recursively replace values with type-preserving zero/empty representations."""
    if current_depth > max_depth:
        raise PayloadTooLargeError(
            f"Payload nesting depth ({current_depth}) exceeds maximum limit ({max_depth})"
        )

    if value is None:
        return None
    # Check bool before int, since bool is a subclass of int in Python
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0
    if isinstance(value, float):
        return 0.0
    if isinstance(value, str):
        return ""
    if isinstance(value, dict):
        if is_dynamic_map(value.keys(), max_keys=max_object_keys):
            # Privacy hardening: objects with dynamic keys or > max_object_keys are treated as maps
            # (keys replaced by "*")
            merged_val: Any = None
            for v in value.values():
                redacted_v = _redact_value(
                    v,
                    max_array_length=max_array_length,
                    max_object_keys=max_object_keys,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                )
                if merged_val is None:
                    merged_val = redacted_v
                elif isinstance(merged_val, dict) and isinstance(redacted_v, dict):
                    merged_val = {**merged_val, **redacted_v}
            return {DYNAMIC_KEY_WILDCARD: merged_val if merged_val is not None else {}}
        return {
            (k if k is DYNAMIC_KEY_WILDCARD else str(k)): _redact_value(
                v,
                max_array_length=max_array_length,
                max_object_keys=max_object_keys,
                current_depth=current_depth + 1,
                max_depth=max_depth,
            )
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        truncated = value[:max_array_length]
        return [
            _redact_value(
                item,
                max_array_length=max_array_length,
                max_object_keys=max_object_keys,
                current_depth=current_depth + 1,
                max_depth=max_depth,
            )
            for item in truncated
        ]

    return None
