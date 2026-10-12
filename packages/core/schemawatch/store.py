from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any, Protocol

from schemawatch.infer import SchemaNode

logger = logging.getLogger(__name__)


def compute_alert_hash(vendor: str, endpoint: str, path: str, kind: str) -> str:
    """Compute a deterministic hash for deduplication and cooldown."""
    raw = f"{vendor}:{endpoint}:{path}:{kind}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


class Store(Protocol):
    """Protocol for baseline persistence and alert deduplication stores."""

    def get_baseline(self, vendor: str, endpoint: str) -> SchemaNode | None: ...

    def set_baseline(self, vendor: str, endpoint: str, schema: SchemaNode) -> None: ...

    def get_sample_count(self, vendor: str, endpoint: str) -> int: ...

    def increment_sample_count(self, vendor: str, endpoint: str) -> int: ...

    def check_and_set_cooldown(
        self,
        vendor: str,
        endpoint: str,
        path: str,
        kind: str,
        cooldown_seconds: int,
    ) -> bool: ...

    def reset(self, vendor: str, endpoint: str) -> None: ...


class MemoryStore:
    """In-memory thread-safe baseline store with alert cooldown support."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._baselines: dict[str, SchemaNode] = {}
        self._counts: dict[str, int] = {}
        self._cooldowns: dict[str, float] = {}

    def _key(self, vendor: str, endpoint: str) -> str:
        return f"{vendor}:{endpoint}"

    def get_baseline(self, vendor: str, endpoint: str) -> SchemaNode | None:
        with self._lock:
            return self._baselines.get(self._key(vendor, endpoint))

    def set_baseline(self, vendor: str, endpoint: str, schema: SchemaNode) -> None:
        with self._lock:
            self._baselines[self._key(vendor, endpoint)] = schema

    def get_sample_count(self, vendor: str, endpoint: str) -> int:
        with self._lock:
            return self._counts.get(self._key(vendor, endpoint), 0)

    def increment_sample_count(self, vendor: str, endpoint: str) -> int:
        with self._lock:
            k = self._key(vendor, endpoint)
            new_count = self._counts.get(k, 0) + 1
            self._counts[k] = new_count
            return new_count

    def check_and_set_cooldown(
        self,
        vendor: str,
        endpoint: str,
        path: str,
        kind: str,
        cooldown_seconds: int,
    ) -> bool:
        alert_hash = compute_alert_hash(vendor, endpoint, path, kind)
        now = time.time()
        with self._lock:
            expires_at = self._cooldowns.get(alert_hash, 0.0)
            if now < expires_at:
                return False  # Cooldown active; suppress alert
            self._cooldowns[alert_hash] = now + cooldown_seconds
            return True  # Alert allowed

    def reset(self, vendor: str, endpoint: str) -> None:
        with self._lock:
            k = self._key(vendor, endpoint)
            self._baselines.pop(k, None)
            self._counts.pop(k, None)


class RedisStore:
    """Redis-backed baseline and deduplication store."""

    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    def _base_key(self, vendor: str, endpoint: str) -> str:
        return f"sw:base:{vendor}:{endpoint}"

    def _count_key(self, vendor: str, endpoint: str) -> str:
        return f"sw:n:{vendor}:{endpoint}"

    def _alert_key(self, alert_hash: str) -> str:
        return f"sw:alert:{alert_hash}"

    def get_baseline(self, vendor: str, endpoint: str) -> SchemaNode | None:
        raw = self.redis.get(self._base_key(vendor, endpoint))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return SchemaNode.from_dict(data)

    def set_baseline(self, vendor: str, endpoint: str, schema: SchemaNode) -> None:
        raw = json.dumps(schema.to_dict())
        self.redis.set(self._base_key(vendor, endpoint), raw)

    def get_sample_count(self, vendor: str, endpoint: str) -> int:
        raw = self.redis.get(self._count_key(vendor, endpoint))
        return int(raw) if raw is not None else 0

    def increment_sample_count(self, vendor: str, endpoint: str) -> int:
        return int(self.redis.incr(self._count_key(vendor, endpoint)))

    def check_and_set_cooldown(
        self,
        vendor: str,
        endpoint: str,
        path: str,
        kind: str,
        cooldown_seconds: int,
    ) -> bool:
        alert_hash = compute_alert_hash(vendor, endpoint, path, kind)
        key = self._alert_key(alert_hash)
        # SET key 1 NX EX cooldown (atomic)
        result = self.redis.set(key, "1", nx=True, ex=cooldown_seconds)
        return bool(result)

    def reset(self, vendor: str, endpoint: str) -> None:
        self.redis.delete(
            self._base_key(vendor, endpoint),
            self._count_key(vendor, endpoint),
        )
