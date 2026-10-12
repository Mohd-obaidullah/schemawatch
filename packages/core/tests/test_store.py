from __future__ import annotations

import time
from unittest.mock import MagicMock

from schemawatch.infer import SchemaNode
from schemawatch.store import MemoryStore, RedisStore, compute_alert_hash


def test_compute_alert_hash_deterministic() -> None:
    h1 = compute_alert_hash("payco", "/v1", "$.id", "type_changed")
    h2 = compute_alert_hash("payco", "/v1", "$.id", "type_changed")
    h3 = compute_alert_hash("payco", "/v2", "$.id", "type_changed")
    assert h1 == h2
    assert h1 != h3


def test_memory_store_baseline_and_counts() -> None:
    store = MemoryStore()
    assert store.get_baseline("vendor", "/test") is None
    assert store.get_sample_count("vendor", "/test") == 0

    node = SchemaNode(types={"object"})
    store.set_baseline("vendor", "/test", node)
    assert store.get_baseline("vendor", "/test") == node

    assert store.increment_sample_count("vendor", "/test") == 1
    assert store.increment_sample_count("vendor", "/test") == 2
    assert store.get_sample_count("vendor", "/test") == 2

    store.reset("vendor", "/test")
    assert store.get_baseline("vendor", "/test") is None
    assert store.get_sample_count("vendor", "/test") == 0


def test_memory_store_cooldown() -> None:
    store = MemoryStore()
    vendor = "stripe"
    endpoint = "/charges"
    path = "$.amount"
    kind = "type_changed"

    # First occurrence: allowed
    assert store.check_and_set_cooldown(vendor, endpoint, path, kind, cooldown_seconds=1) is True

    # Immediate second occurrence: suppressed by cooldown
    assert store.check_and_set_cooldown(vendor, endpoint, path, kind, cooldown_seconds=1) is False

    # After cooldown expires: allowed again
    time.sleep(1.05)
    assert store.check_and_set_cooldown(vendor, endpoint, path, kind, cooldown_seconds=1) is True


def test_redis_store_mocked() -> None:
    mock_redis = MagicMock()
    store = RedisStore(mock_redis)

    # get_baseline
    mock_redis.get.return_value = None
    assert store.get_baseline("v", "/e") is None

    node = SchemaNode(types={"integer"})
    mock_redis.get.return_value = '{"types": ["integer"]}'
    retrieved = store.get_baseline("v", "/e")
    assert retrieved is not None
    assert retrieved.types == {"integer"}

    # set_baseline
    store.set_baseline("v", "/e", node)
    mock_redis.set.assert_called()

    # increment_sample_count
    mock_redis.incr.return_value = 5
    assert store.increment_sample_count("v", "/e") == 5

    # check_and_set_cooldown
    mock_redis.set.return_value = True
    assert store.check_and_set_cooldown("v", "/e", "$.x", "kind", 60) is True

    # reset
    store.reset("v", "/e")
    mock_redis.delete.assert_called()
