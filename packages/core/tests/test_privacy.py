from __future__ import annotations

import json

import pytest
from schemawatch.infer import infer_schema
from schemawatch.redact import is_dynamic_map, redact
from schemawatch.watchdog import Watchdog


def test_privacy_no_raw_values_leak_into_baseline_or_alerts() -> None:
    """Privacy test: Proves no raw string, number, or boolean value from a payload
    appears in any stored baseline or emitted alert.
    """
    secret_string_1 = "SUPER_SECRET_SSN_987-65-4321"
    secret_string_2 = "sk_live_very_secret_api_key_xyz123"
    secret_int = 987654321
    secret_float = 1337.4242

    payload_sample = {
        "user_ssn": secret_string_1,
        "api_key": secret_string_2,
        "account_balance": secret_int,
        "interest_rate": secret_float,
        "is_verified": True,
        "metadata": {
            "internal_notes": "PRIVATE_PATIENT_HEALTH_DATA_DIAGNOSIS_42",
        },
    }

    watchdog = Watchdog(learning_threshold=1, sample_rate=1.0)
    vendor = "fintech_vendor"
    endpoint = "/v1/sensitive"

    # Step 1: Learn baseline
    watchdog.observe(vendor, endpoint, payload_sample)

    # Inspect baseline stored
    baseline = watchdog.store.get_baseline(vendor, endpoint)
    assert baseline is not None

    baseline_json = json.dumps(baseline.to_dict())

    # Assert no sensitive values exist in baseline representation
    assert secret_string_1 not in baseline_json
    assert secret_string_2 not in baseline_json
    assert str(secret_int) not in baseline_json
    assert str(secret_float) not in baseline_json
    assert "PRIVATE_PATIENT_HEALTH_DATA_DIAGNOSIS_42" not in baseline_json

    # Step 2: Trigger drift with a new secret
    secret_drift_str = "LEAKY_CARD_NUMBER_4111_2222_3333_4444"
    drift_payload = {
        "user_ssn": 12345,  # type changed string -> integer
        "api_key": secret_string_2,
        "account_balance": secret_drift_str,  # type changed integer -> string
        "interest_rate": secret_float,
        "is_verified": True,
        "metadata": {
            "internal_notes": "NEW_SENSITIVE_NOTE_9999",
        },
    }

    changes = watchdog.observe(vendor, endpoint, drift_payload)
    assert len(changes) > 0

    for change in changes:
        change_json = json.dumps(change.to_dict())
        assert secret_string_1 not in change_json
        assert secret_string_2 not in change_json
        assert secret_drift_str not in change_json
        assert "NEW_SENSITIVE_NOTE_9999" not in change_json
        assert str(secret_int) not in change_json
        assert str(secret_float) not in change_json


def test_privacy_five_email_keyed_users_never_leak_emails(caplog: pytest.LogCaptureFixture) -> None:
    """Privacy test: 5 email-keyed users never leak an email into baseline, alerts or logs."""
    emails = [
        "alice.smith@confidential-bank.com",
        "bob.jones@private-investments.org",
        "carol.williams@secret-agency.gov",
        "david.miller@stealth-corp.io",
        "eva.brown@internal-audit.net",
    ]
    learning_payload = {
        email: {"account_id": 1000 + i, "tier": "gold"} for i, email in enumerate(emails)
    }

    watchdog = Watchdog(learning_threshold=1, sample_rate=1.0)
    vendor = "user_service"
    endpoint = "/v1/users"

    # Step 1: Learn baseline
    watchdog.observe(vendor, endpoint, learning_payload)

    # Assert baseline has NO email addresses and has wildcard '*'
    baseline = watchdog.store.get_baseline(vendor, endpoint)
    assert baseline is not None
    baseline_str = json.dumps(baseline.to_dict())
    for email in emails:
        assert email not in baseline_str
    assert "*" in baseline.properties

    # Step 2: Trigger drift with 5 new email keys and type drift
    new_emails = [f"new_victim_{i}@classified.org" for i in range(5)]
    drift_payload = {
        email: {"account_id": f"acc_{i}", "tier": "gold"} for i, email in enumerate(new_emails)
    }

    changes = watchdog.observe(vendor, endpoint, drift_payload)
    assert len(changes) > 0

    all_emails = emails + new_emails
    for change in changes:
        change_json = json.dumps(change.to_dict())
        for email in all_emails:
            assert email not in change_json
            assert email not in (change.detail or "")
            assert email not in change.path
        assert ".*" in change.path

    # Step 3: Assert logs contain no email addresses
    logs = caplog.text
    for email in all_emails:
        assert email not in logs


def test_privacy_normal_eight_field_object_is_not_turned_into_a_map() -> None:
    """Privacy test: A normal 8-field object is NOT turned into a map."""
    normal_object = {
        "id": 12345,
        "name": "Standard Product",
        "price": 29.99,
        "currency": "USD",
        "in_stock": True,
        "created_at": "2026-01-01T00:00:00Z",
        "category": "electronics",
        "description": "High quality widget",
    }
    assert not is_dynamic_map(normal_object.keys())

    # Redacting does not replace keys with '*'
    redacted = redact(normal_object)
    assert "*" not in redacted
    assert len(redacted) == 8
    assert set(redacted.keys()) == set(normal_object.keys())

    # Inferred schema retains all 8 properties and required fields
    node = infer_schema(normal_object)
    assert "*" not in node.properties
    assert len(node.properties) == 8
    assert node.required == set(normal_object.keys())


def test_privacy_dynamic_map_detection_edge_cases() -> None:
    # 3 UUID keys -> Treated as map
    uuid_dict = {
        "123e4567-e89b-12d3-a456-426614174000": "data_1",
        "223e4567-e89b-12d3-a456-426614174001": "data_2",
        "323e4567-e89b-12d3-a456-426614174002": "data_3",
    }
    assert is_dynamic_map(uuid_dict.keys())

    # 3 long-digit keys -> Treated as map
    digit_dict = {
        "1234567890": "a",
        "9876543210": "b",
        "5555555555": "c",
    }
    assert is_dynamic_map(digit_dict.keys())

    # 3 long-hex keys -> Treated as map
    hex_dict = {
        "abcdef0123456789": "val1",
        "0123456789abcdef": "val2",
        "fedcba9876543210": "val3",
    }
    assert is_dynamic_map(hex_dict.keys())

    # 2 keys total (even if 1 is a UUID) -> NOT a map (min 3 keys required)
    two_key_dict = {
        "123e4567-e89b-12d3-a456-426614174000": "uuid_val",
        "status": "active",
    }
    assert not is_dynamic_map(two_key_dict.keys())
