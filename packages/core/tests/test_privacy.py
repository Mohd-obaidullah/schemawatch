from __future__ import annotations

import json

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
