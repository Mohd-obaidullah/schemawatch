from __future__ import annotations

import json
from typing import Any

DEFAULT_MAX_PAYLOAD_BYTES: int = 1_000_000  # 1 MB
DEFAULT_MAX_ARRAY_LENGTH: int = 10


class PayloadTooLargeError(ValueError):
    """Raised when a payload exceeds the maximum allowed size."""


class InvalidPayloadError(ValueError):
    """Raised when a payload is not valid JSON or a JSON-serializable structure."""


def redact(
    payload: Any,
    *,
    max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
    max_array_length: int = DEFAULT_MAX_ARRAY_LENGTH,
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

    return _redact_value(payload, max_array_length=max_array_length)


def _redact_value(value: Any, *, max_array_length: int) -> Any:
    """Recursively replace values with type-preserving zero/empty representations."""
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
        return {
            str(k): _redact_value(v, max_array_length=max_array_length) for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        truncated = value[:max_array_length]
        return [_redact_value(item, max_array_length=max_array_length) for item in truncated]

    return None
