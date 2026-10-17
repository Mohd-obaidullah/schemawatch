from __future__ import annotations

from unittest.mock import MagicMock

from schemawatch.diff import DriftEvent
from schemawatch.watchdog import Watchdog


def test_watchdog_learning_phase() -> None:
    watchdog = Watchdog(learning_threshold=3, sample_rate=1.0)
    vendor = "payco"
    endpoint = "/v1/charges"

    # Sample 1: {id, amount}
    changes = watchdog.observe(vendor, endpoint, {"id": 1, "amount": 10.0})
    assert changes == []
    assert watchdog.store.get_sample_count(vendor, endpoint) == 1

    # Sample 2: {id, currency} (amount omitted, currency added)
    changes = watchdog.observe(vendor, endpoint, {"id": 2, "currency": "USD"})
    assert changes == []
    assert watchdog.store.get_sample_count(vendor, endpoint) == 2

    # Sample 3: {id, amount, currency}
    changes = watchdog.observe(vendor, endpoint, {"id": 3, "amount": 20.0, "currency": "USD"})
    assert changes == []
    assert watchdog.store.get_sample_count(vendor, endpoint) == 3

    # Baseline should now have {id} required, {amount, currency} optional
    baseline = watchdog.store.get_baseline(vendor, endpoint)
    assert baseline is not None
    assert baseline.required == {"id"}
    assert "amount" in baseline.properties
    assert "currency" in baseline.properties


def test_watchdog_drift_detection_and_cooldown() -> None:
    alerts: list[DriftEvent] = []
    watchdog = Watchdog(
        learning_threshold=2,
        sample_rate=1.0,
        cooldown_seconds=60,
        on_alert=alerts.append,
    )
    vendor = "payco"
    endpoint = "/v1/charges"

    # Learning phase (2 samples)
    watchdog.observe(vendor, endpoint, {"id": 1, "status": "ok"})
    watchdog.observe(vendor, endpoint, {"id": 2, "status": "ok"})

    # Post-learning: normal payload
    normal_changes = watchdog.observe(vendor, endpoint, {"id": 3, "status": "ok"})
    assert normal_changes == []
    assert len(alerts) == 0

    # Post-learning: drift payload (status is integer instead of string)
    drift_changes = watchdog.observe(vendor, endpoint, {"id": 4, "status": 500})
    assert len(drift_changes) == 1
    assert drift_changes[0].path == "$.status"
    assert drift_changes[0].severity == "breaking"
    assert len(alerts) == 1
    assert alerts[0].vendor == "payco"
    assert alerts[0].endpoint == "/v1/charges"
    assert len(alerts[0].changes) == 1
    assert alerts[0].changes[0].path == "$.status"

    # Post-learning: immediate duplicate drift payload (should be suppressed by cooldown)
    dup_changes = watchdog.observe(vendor, endpoint, {"id": 5, "status": 500})
    assert dup_changes == []
    assert len(alerts) == 1  # No new alert triggered


def test_watchdog_sampling_rate() -> None:
    watchdog = Watchdog(learning_threshold=1, sample_rate=0.0)
    vendor = "payco"
    endpoint = "/test"

    # Learn
    watchdog.observe(vendor, endpoint, {"x": 1})

    # With sample_rate=0.0, never inspects
    drift_changes = watchdog.observe(vendor, endpoint, {"x": "str"})
    assert drift_changes == []


def test_watchdog_fail_open_on_exception() -> None:
    """Watchdog.observe() must never raise into the caller under any failure."""
    bad_store = MagicMock()
    # Store throws an exception
    bad_store.get_sample_count.side_effect = RuntimeError("Database connection exploded")

    watchdog = Watchdog(store=bad_store)

    # Must swallow exception and return empty list
    changes = watchdog.observe("vendor", "/fail", {"any": "data"})
    assert changes == []


def test_watchdog_fail_open_on_bad_payload() -> None:
    watchdog = Watchdog(learning_threshold=2)
    # Pass corrupted or oversized data
    changes = watchdog.observe("vendor", "/test", "{bad json")
    assert changes == []


def test_watchdog_on_alert_exception_swallowed() -> None:
    def exploding_alert_callback(event: DriftEvent) -> None:
        raise ValueError("Alert webhook failed to send!")

    watchdog = Watchdog(learning_threshold=1, on_alert=exploding_alert_callback)
    watchdog.observe("v", "/e", {"id": 1})
    # Next observation detects drift and calls callback, must swallow exception and return changes
    changes = watchdog.observe("v", "/e", {"id": "str"})
    assert len(changes) == 1


def test_watchdog_post_learning_none_baseline_fallback() -> None:
    watchdog = Watchdog(learning_threshold=0)
    # Count >= learning_threshold but baseline is None
    changes = watchdog.observe("v", "/empty", {"x": 10})
    assert changes == []
    assert watchdog.store.get_baseline("v", "/empty") is not None
