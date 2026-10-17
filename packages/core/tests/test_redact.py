from __future__ import annotations

import json
from typing import Any

import pytest
from schemawatch.redact import (
    InvalidPayloadError,
    PayloadTooLargeError,
    redact,
)


def test_redact_primitives() -> None:
    assert redact("secret_password") == ""
    assert redact(12345) == 0
    assert redact(99.95) == 0.0
    assert redact(True) is False
    assert redact(False) is False
    assert redact(None) is None


def test_redact_bool_not_treated_as_int() -> None:
    # In Python, isinstance(True, int) is True, so we must verify bool gets False and remains bool
    redacted = redact(True)
    assert isinstance(redacted, bool)
    assert not isinstance(redacted, float)


def test_redact_nested_dict() -> None:
    payload = {
        "user_id": 9876,
        "email": "user@example.com",
        "is_active": True,
        "score": 4.5,
        "address": {
            "street": "123 Main St",
            "zip": "94105",
        },
    }
    redacted = redact(payload)
    assert redacted == {
        "user_id": 0,
        "email": "",
        "is_active": False,
        "score": 0.0,
        "address": {
            "street": "",
            "zip": "",
        },
    }


def test_redact_array_truncation() -> None:
    long_list = list(range(100))
    redacted = redact(long_list, max_array_length=5)
    assert len(redacted) == 5
    assert redacted == [0, 0, 0, 0, 0]


def test_redact_json_string_and_bytes() -> None:
    payload_dict = {"foo": "bar", "num": 42}
    raw_str = json.dumps(payload_dict)
    assert redact(raw_str) == {"foo": "", "num": 0}

    raw_bytes = raw_str.encode("utf-8")
    assert redact(raw_bytes) == {"foo": "", "num": 0}


def test_redact_payload_size_limit() -> None:
    huge_str = "a" * 1000
    with pytest.raises(PayloadTooLargeError):
        redact(huge_str, max_payload_bytes=500)

    huge_bytes = b"a" * 1000
    with pytest.raises(PayloadTooLargeError):
        redact(huge_bytes, max_payload_bytes=500)

    huge_dict = {"data": "x" * 1000}
    with pytest.raises(PayloadTooLargeError):
        redact(huge_dict, max_payload_bytes=500)


def test_redact_invalid_json() -> None:
    with pytest.raises(InvalidPayloadError):
        redact("{not valid json")

    with pytest.raises(InvalidPayloadError):
        redact(b"{not valid json bytes")

    class Unserializable:
        pass

    with pytest.raises(InvalidPayloadError):
        redact(Unserializable())


def test_redact_bytes_edge_cases() -> None:
    # Non-UTF-8 bytes raises InvalidPayloadError
    with pytest.raises(InvalidPayloadError):
        redact(b"\x80\x81invalid_utf8")

    # Plain text bytes
    assert redact(b"plain_string_bytes") == ""

    # Unknown object in _redact_value
    from schemawatch.redact import _redact_value

    assert _redact_value(object(), max_array_length=5) is None


def test_redact_nesting_depth_limit() -> None:
    # Build payload with 35 levels of nesting (exceeds default limit 32)
    nested: dict[str, Any] = {"value": 1}
    for _ in range(35):
        nested = {"level": nested}

    with pytest.raises(PayloadTooLargeError) as exc_info:
        redact(nested)

    assert "nesting depth" in str(exc_info.value)
