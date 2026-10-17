from __future__ import annotations

import json
import threading
import time
from typing import Any

from schemawatch.infer import SchemaNode
from schemawatch.store import compute_alert_hash
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from schemawatch_api.models import Baseline, Endpoint, utc_now


class SqlStore:
    """SQLAlchemy-backed implementation of the schemawatch Store protocol.

    Persists endpoints and versioned baselines into relational storage.
    Supports in-memory or Redis-backed cooldown deduplication.
    Keeps packages/core completely decoupled from database dependencies.
    """

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        redis_client: Any = None,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis_client
        self._lock = threading.Lock()
        self._in_memory_cooldowns: dict[str, float] = {}

    def get_baseline(self, vendor: str, endpoint: str) -> SchemaNode | None:
        """Retrieve the current active baseline SchemaNode for a vendor endpoint."""
        with self._session_factory() as session:
            stmt = select(Endpoint).where(
                Endpoint.vendor == vendor,
                Endpoint.endpoint == endpoint,
            )
            ep = session.scalars(stmt).first()
            if ep is None or ep.current_baseline_version is None:
                return None

            base_stmt = select(Baseline).where(
                Baseline.endpoint_id == ep.id,
                Baseline.version == ep.current_baseline_version,
            )
            baseline_row = session.scalars(base_stmt).first()
            if baseline_row is None:
                return None

            data = json.loads(baseline_row.schema_json)
            return SchemaNode.from_dict(data)

    def set_baseline(self, vendor: str, endpoint: str, schema: SchemaNode) -> None:
        """Persist a new version of the baseline SchemaNode."""
        with self._session_factory() as session:
            stmt = select(Endpoint).where(
                Endpoint.vendor == vendor,
                Endpoint.endpoint == endpoint,
            )
            ep = session.scalars(stmt).first()
            if ep is None:
                ep = Endpoint(
                    vendor=vendor,
                    endpoint=endpoint,
                    sample_count=0,
                    current_baseline_version=1,
                )
                session.add(ep)
                session.flush()

            target_version = ep.current_baseline_version or 1
            ep.current_baseline_version = target_version
            ep.updated_at = utc_now()

            schema_dict = schema.to_dict()
            existing_baseline = session.scalars(
                select(Baseline).where(
                    Baseline.endpoint_id == ep.id,
                    Baseline.version == target_version,
                )
            ).first()
            if existing_baseline is not None:
                existing_baseline.schema_json = json.dumps(schema_dict)
            else:
                baseline_row = Baseline(
                    endpoint_id=ep.id,
                    version=target_version,
                    schema_json=json.dumps(schema_dict),
                    created_at=utc_now(),
                )
                session.add(baseline_row)
            session.commit()

    def get_sample_count(self, vendor: str, endpoint: str) -> int:
        """Get the current number of learned samples for a vendor endpoint."""
        with self._session_factory() as session:
            stmt = select(Endpoint.sample_count).where(
                Endpoint.vendor == vendor,
                Endpoint.endpoint == endpoint,
            )
            count = session.scalars(stmt).first()
            return int(count) if count is not None else 0

    def increment_sample_count(self, vendor: str, endpoint: str) -> int:
        """Increment and return the sample count for a vendor endpoint."""
        with self._session_factory() as session:
            stmt = select(Endpoint).where(
                Endpoint.vendor == vendor,
                Endpoint.endpoint == endpoint,
            )
            ep = session.scalars(stmt).first()
            if ep is None:
                ep = Endpoint(
                    vendor=vendor,
                    endpoint=endpoint,
                    sample_count=1,
                )
                session.add(ep)
                new_count = 1
            else:
                ep.sample_count += 1
                ep.updated_at = utc_now()
                new_count = ep.sample_count

            session.commit()
            return new_count

    def check_and_set_cooldown(
        self,
        vendor: str,
        endpoint: str,
        path: str,
        kind: str,
        cooldown_seconds: int,
    ) -> bool:
        """Check if an alert is on cooldown. If not, record the cooldown and return True."""
        alert_hash = compute_alert_hash(vendor, endpoint, path, kind)

        if self._redis is not None:
            key = f"schemawatch:cooldown:{alert_hash}"
            try:
                # SET key 1 NX EX cooldown_seconds returns True if key was set (is new)
                return bool(self._redis.set(key, "1", nx=True, ex=cooldown_seconds))
            except Exception:
                # Fail open to in-memory fallback if Redis has an issue
                pass

        now = time.time()
        with self._lock:
            # Clean up expired cooldowns periodically
            expired = [k for k, exp in self._in_memory_cooldowns.items() if exp <= now]
            for k in expired:
                del self._in_memory_cooldowns[k]

            current_expiry = self._in_memory_cooldowns.get(alert_hash)
            if current_expiry is not None and current_expiry > now:
                return False

            self._in_memory_cooldowns[alert_hash] = now + cooldown_seconds
            return True

    def reset(self, vendor: str, endpoint: str) -> None:
        """Reset sample counts and baselines for an endpoint."""
        with self._session_factory() as session:
            stmt = select(Endpoint).where(
                Endpoint.vendor == vendor,
                Endpoint.endpoint == endpoint,
            )
            ep = session.scalars(stmt).first()
            if ep is not None:
                ep.sample_count = 0
                ep.current_baseline_version = None
                ep.updated_at = utc_now()
                session.commit()
