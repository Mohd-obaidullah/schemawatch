from __future__ import annotations

import logging
import random
from collections.abc import Callable
from typing import Any

from schemawatch.diff import Change, DriftEvent, diff
from schemawatch.infer import infer_schema, merge
from schemawatch.redact import (
    DEFAULT_MAX_ARRAY_LENGTH,
    DEFAULT_MAX_OBJECT_KEYS,
    DEFAULT_MAX_PAYLOAD_BYTES,
    InvalidPayloadError,
    PayloadTooLargeError,
    redact,
)
from schemawatch.store import MemoryStore, Store

logger = logging.getLogger(__name__)


class Watchdog:
    """Core monitor for observing API response shapes, maintaining baselines, and flagging drift."""

    def __init__(
        self,
        store: Store | None = None,
        learning_threshold: int = 10,
        sample_rate: float = 1.0,
        cooldown_seconds: int = 3600,
        max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
        max_array_length: int = DEFAULT_MAX_ARRAY_LENGTH,
        max_object_keys: int = DEFAULT_MAX_OBJECT_KEYS,
        on_alert: Callable[[DriftEvent], None] | None = None,
    ) -> None:
        self.store: Store = store if store is not None else MemoryStore()
        self.learning_threshold = learning_threshold
        self.sample_rate = sample_rate
        self.cooldown_seconds = cooldown_seconds
        self.max_payload_bytes = max_payload_bytes
        self.max_array_length = max_array_length
        self.max_object_keys = max_object_keys
        self.on_alert = on_alert

    def observe(self, vendor: str, endpoint: str, payload: Any) -> list[Change]:
        """Observe an API response payload.

        Guaranteed to FAIL OPEN: never raises exceptions into host application code.
        Any unexpected errors are caught, logged, and an empty change list is returned.

        Args:
            vendor: Name or identifier of the third-party vendor (e.g. 'payco').
            endpoint: Identifier or path of the endpoint (e.g. '/v1/payments').
            payload: JSON payload (dict, list, or JSON string/bytes).

        Returns:
            List of detected changes that are not currently under cooldown.
        """
        try:
            return self._observe_internal(vendor, endpoint, payload)
        except Exception as exc:
            logger.exception(
                "schemawatch: error observing payload for %s %s: %s",
                vendor,
                endpoint,
                exc,
            )
            return []

    def _observe_internal(self, vendor: str, endpoint: str, payload: Any) -> list[Change]:
        # Step 1: Redact values (PII protection, size limits, array truncation)
        try:
            clean_payload = redact(
                payload,
                max_payload_bytes=self.max_payload_bytes,
                max_array_length=self.max_array_length,
                max_object_keys=self.max_object_keys,
            )
        except (PayloadTooLargeError, InvalidPayloadError) as exc:
            logger.warning(
                "schemawatch: dropped payload for %s %s: %s",
                vendor,
                endpoint,
                exc,
            )
            return []

        # Step 2: Learning phase check
        count = self.store.get_sample_count(vendor, endpoint)
        if count < self.learning_threshold:
            observed_schema = infer_schema(
                clean_payload,
                max_array_length=self.max_array_length,
                max_object_keys=self.max_object_keys,
            )
            baseline = self.store.get_baseline(vendor, endpoint)
            new_baseline = (
                merge(baseline, observed_schema) if baseline is not None else observed_schema
            )
            self.store.set_baseline(vendor, endpoint, new_baseline)
            self.store.increment_sample_count(vendor, endpoint)
            return []

        # Step 3: Sampling check
        if self.sample_rate < 1.0 and random.random() > self.sample_rate:
            return []

        # Step 4: Infer and diff against established baseline
        observed_schema = infer_schema(
            clean_payload,
            max_array_length=self.max_array_length,
            max_object_keys=self.max_object_keys,
        )
        baseline = self.store.get_baseline(vendor, endpoint)
        if baseline is None:
            self.store.set_baseline(vendor, endpoint, observed_schema)
            return []

        all_changes = diff(baseline, observed_schema)
        if not all_changes:
            return []

        # Step 5: Alert deduplication and cooldown
        active_changes: list[Change] = []
        for change in all_changes:
            is_new = self.store.check_and_set_cooldown(
                vendor,
                endpoint,
                change.path,
                change.kind,
                self.cooldown_seconds,
            )
            if is_new:
                active_changes.append(change)

        if active_changes and self.on_alert is not None:
            event = DriftEvent(
                vendor=vendor,
                endpoint=endpoint,
                changes=tuple(active_changes),
            )
            try:
                self.on_alert(event)
            except Exception as alert_exc:
                logger.exception("schemawatch: on_alert error: %s", alert_exc)

        return active_changes
