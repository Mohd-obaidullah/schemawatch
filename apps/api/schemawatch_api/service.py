from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from schemawatch.alerts import SlackAlert, WebhookAlert
from schemawatch.diff import Change, DriftEvent
from schemawatch.infer import SchemaNode, infer_schema
from schemawatch.redact import redact
from schemawatch.severity import SEVERITY_BREAKING, SEVERITY_INFO, SEVERITY_WARNING
from schemawatch.watchdog import Watchdog
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from schemawatch_api.config import Settings
from schemawatch_api.models import AlertDelivery, Baseline, DriftEventModel, Endpoint, utc_now
from schemawatch_api.sse import SSEManager
from schemawatch_api.store import SqlStore

logger = logging.getLogger(__name__)

SEVERITY_LEVELS = {
    SEVERITY_INFO: 1,
    SEVERITY_WARNING: 2,
    SEVERITY_BREAKING: 3,
}


class SchemawatchService:
    """Core backend domain service managing storage, watchdog, alerts, and SSE events."""

    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        sse_manager: SSEManager,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.sse_manager = sse_manager
        self._loop = loop

        # Initialize persistence store
        self.sql_store = SqlStore(session_factory=session_factory)

        # Initialize alert dispatchers
        self.alert_channels: list[tuple[str, Callable[[DriftEvent], bool]]] = []
        if settings.slack_webhook_url:
            self.alert_channels.append(
                ("slack", SlackAlert(webhook_url=settings.slack_webhook_url).send)
            )
        if settings.alert_webhook_url:
            self.alert_channels.append(
                (
                    "webhook",
                    WebhookAlert(
                        url=settings.alert_webhook_url,
                        secret=settings.alert_webhook_secret,
                    ).send,
                )
            )

        # Initialize Watchdog core monitor with SqlStore
        self.watchdog = Watchdog(
            store=self.sql_store,
            learning_threshold=settings.learn_samples,
            sample_rate=settings.sample_rate,
            cooldown_seconds=settings.cooldown_seconds,
            on_alert=self._on_watchdog_alert,
        )

        # Store latest observed clean schema per (vendor, endpoint) in memory for accept flow
        self._latest_observed_schemas: dict[str, SchemaNode] = {}

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Assign or update the asyncio event loop for thread-safe SSE dispatch."""
        self._loop = loop

    def _should_dispatch_alert(self, severity: str) -> bool:
        min_threshold = SEVERITY_LEVELS.get(self.settings.min_alert_severity, 1)
        event_level = SEVERITY_LEVELS.get(severity, 1)
        return event_level >= min_threshold

    def _on_watchdog_alert(self, event: DriftEvent) -> None:
        """Sink on Watchdog.on_alert: persists events, dispatches alerts, notifies SSE."""
        now_dt = utc_now()
        persisted_event_ids: list[int] = []

        # Retrieve cached observed schema if available
        cache_key = f"{event.vendor}:{event.endpoint}"
        observed_node = self._latest_observed_schemas.get(cache_key)
        observed_json = json.dumps(observed_node.to_dict()) if observed_node else None

        with self.session_factory() as session:
            # 1. Ensure Endpoint exists
            stmt = select(Endpoint).where(
                Endpoint.vendor == event.vendor,
                Endpoint.endpoint == event.endpoint,
            )
            ep = session.scalars(stmt).first()
            if ep is None:
                ep = Endpoint(
                    vendor=event.vendor,
                    endpoint=event.endpoint,
                    sample_count=self.settings.learn_samples,
                )
                session.add(ep)
                session.flush()

            # 2. Persist each change as a DriftEventModel row
            for change in event.changes:
                event_row = DriftEventModel(
                    endpoint_id=ep.id,
                    vendor=event.vendor,
                    endpoint=event.endpoint,
                    field_path=change.path,
                    kind=change.kind,
                    severity=change.severity,
                    was_value=str(change.was) if change.was is not None else None,
                    now_value=str(change.now) if change.now is not None else None,
                    detail=change.detail,
                    observed_schema_json=observed_json,
                    acknowledged=False,
                    detected_at=datetime.fromtimestamp(event.detected_at, timezone.utc).replace(
                        tzinfo=None
                    ),
                )
                session.add(event_row)
                session.flush()
                persisted_event_ids.append(event_row.id)

            session.commit()

        # 3. Dispatch external alerts if configured and severity meets threshold
        if self._should_dispatch_alert(event.highest_severity) and self.alert_channels:
            for channel_name, sender in self.alert_channels:
                success = False
                error_msg: str | None = None
                try:
                    success = sender(event)
                except Exception as exc:
                    error_msg = type(exc).__name__

                with self.session_factory() as session:
                    for evt_id in persisted_event_ids:
                        deliv = AlertDelivery(
                            drift_event_id=evt_id,
                            channel=channel_name,
                            status="delivered" if success else "failed",
                            delivered_at=now_dt,
                            error_message=error_msg,
                        )
                        session.add(deliv)
                    session.commit()

        # 4. Bridge to SSE subscribers
        loop = self._loop
        if loop is None or not loop.is_running():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

        if loop is not None and loop.is_running():
            broadcast_payload = {
                "vendor": event.vendor,
                "endpoint": event.endpoint,
                "highest_severity": event.highest_severity,
                "detected_at": event.detected_at,
                "event_ids": persisted_event_ids,
                "changes": [c.to_dict() for c in event.changes],
            }
            self.sse_manager.broadcast_threadsafe(loop, "drift", broadcast_payload)

    def ingest_payload(
        self, vendor: str, endpoint: str, raw_payload: Any
    ) -> tuple[bool, list[Change], list[int]]:
        """Ingest a payload via /api/ingest, observing it through the watchdog."""
        # Sanitize and store observed shape for accept flow
        try:
            clean = redact(raw_payload)
            node = infer_schema(clean)
            self._latest_observed_schemas[f"{vendor}:{endpoint}"] = node
        except Exception:
            pass

        # Observe payload through watchdog
        changes = self.watchdog.observe(vendor, endpoint, raw_payload)

        # Retrieve IDs of recently created events for this endpoint if any changes detected
        event_ids: list[int] = []
        if changes:
            with self.session_factory() as session:
                stmt = (
                    select(DriftEventModel.id)
                    .where(
                        DriftEventModel.vendor == vendor,
                        DriftEventModel.endpoint == endpoint,
                    )
                    .order_by(desc(DriftEventModel.id))
                    .limit(len(changes))
                )
                event_ids = list(session.scalars(stmt).all())

        return True, changes, event_ids

    def list_endpoints(
        self,
        cursor: int | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        """List monitored endpoints with health status and active alert counts."""
        with self.session_factory() as session:
            total_stmt = select(func.count(Endpoint.id))
            total = session.scalar(total_stmt) or 0

            stmt = select(Endpoint).order_by(Endpoint.id.desc()).limit(limit + 1)
            if cursor is not None:
                stmt = stmt.where(Endpoint.id < cursor)

            endpoints = list(session.scalars(stmt).all())
            has_next = len(endpoints) > limit
            if has_next:
                items = endpoints[:limit]
                next_cursor = str(items[-1].id)
            else:
                items = endpoints
                next_cursor = None

            result: list[dict[str, Any]] = []
            for ep in items:
                # Count open/unacknowledged alerts
                open_alerts_stmt = select(DriftEventModel.severity).where(
                    DriftEventModel.endpoint_id == ep.id,
                    DriftEventModel.acknowledged.is_(False),
                )
                open_severities = list(session.scalars(open_alerts_stmt).all())
                open_count = len(open_severities)

                # Determine status
                if ep.sample_count < self.settings.learn_samples:
                    status = "learning"
                elif SEVERITY_BREAKING in open_severities:
                    status = "broken"
                elif SEVERITY_WARNING in open_severities:
                    status = "warning"
                else:
                    status = "healthy"

                result.append(
                    {
                        "id": ep.id,
                        "vendor": ep.vendor,
                        "endpoint": ep.endpoint,
                        "sample_count": ep.sample_count,
                        "current_baseline_version": ep.current_baseline_version,
                        "open_alerts_count": open_count,
                        "status": status,
                        "created_at": ep.created_at,
                        "updated_at": ep.updated_at,
                    }
                )

            return result, next_cursor, total

    def get_endpoint(self, endpoint_id: int) -> dict[str, Any] | None:
        """Get detail for a single endpoint."""
        with self.session_factory() as session:
            ep = session.get(Endpoint, endpoint_id)
            if ep is None:
                return None

            open_alerts_stmt = select(DriftEventModel.severity).where(
                DriftEventModel.endpoint_id == ep.id,
                DriftEventModel.acknowledged.is_(False),
            )
            open_severities = list(session.scalars(open_alerts_stmt).all())
            open_count = len(open_severities)

            if ep.sample_count < self.settings.learn_samples:
                status = "learning"
            elif SEVERITY_BREAKING in open_severities:
                status = "broken"
            elif SEVERITY_WARNING in open_severities:
                status = "warning"
            else:
                status = "healthy"

            return {
                "id": ep.id,
                "vendor": ep.vendor,
                "endpoint": ep.endpoint,
                "sample_count": ep.sample_count,
                "current_baseline_version": ep.current_baseline_version,
                "open_alerts_count": open_count,
                "status": status,
                "created_at": ep.created_at,
                "updated_at": ep.updated_at,
            }

    def get_baseline(self, endpoint_id: int, version: int | None = None) -> dict[str, Any] | None:
        """Retrieve baseline schema for an endpoint."""
        with self.session_factory() as session:
            ep = session.get(Endpoint, endpoint_id)
            if ep is None:
                return None

            target_version = version or ep.current_baseline_version
            if target_version is None:
                return None

            stmt = select(Baseline).where(
                Baseline.endpoint_id == ep.id,
                Baseline.version == target_version,
            )
            b_row = session.scalars(stmt).first()
            if b_row is None:
                return None

            return {
                "id": b_row.id,
                "endpoint_id": b_row.endpoint_id,
                "version": b_row.version,
                "schema": json.loads(b_row.schema_json),
                "created_at": b_row.created_at,
            }

    def accept_baseline(self, endpoint_id: int) -> tuple[int, int] | None:
        """Adopt latest observed shape as new baseline version and acknowledge open events.

        Returns (new_version, events_acknowledged) or None if endpoint not found.
        """
        with self.session_factory() as session:
            ep = session.get(Endpoint, endpoint_id)
            if ep is None:
                return None

            # 1. Determine new schema to adopt:
            # Check cached observed schema first, or latest drift event observed_schema_json
            cache_key = f"{ep.vendor}:{ep.endpoint}"
            new_node = self._latest_observed_schemas.get(cache_key)

            if new_node is None:
                latest_evt_stmt = (
                    select(DriftEventModel.observed_schema_json)
                    .where(
                        DriftEventModel.endpoint_id == ep.id,
                        DriftEventModel.observed_schema_json.is_not(None),
                    )
                    .order_by(desc(DriftEventModel.id))
                    .limit(1)
                )
                raw_schema_json = session.scalars(latest_evt_stmt).first()
                if raw_schema_json:
                    new_node = SchemaNode.from_dict(json.loads(raw_schema_json))

            new_version = (ep.current_baseline_version or 0) + 1
            if new_node is not None:
                new_baseline_row = Baseline(
                    endpoint_id=ep.id,
                    version=new_version,
                    schema_json=json.dumps(new_node.to_dict()),
                    created_at=utc_now(),
                )
                session.add(new_baseline_row)
                ep.current_baseline_version = new_version
                ep.updated_at = utc_now()

            # 2. Acknowledge all open events for this endpoint
            ack_time = utc_now()
            ack_stmt = (
                update(DriftEventModel)
                .where(
                    DriftEventModel.endpoint_id == ep.id,
                    DriftEventModel.acknowledged.is_(False),
                )
                .values(acknowledged=True, acknowledged_at=ack_time)
            )
            result = session.execute(ack_stmt)
            session.commit()

            return new_version, int(getattr(result, "rowcount", 0))

    def list_events(
        self,
        severity: str | None = None,
        vendor: str | None = None,
        endpoint_id: int | None = None,
        acknowledged: bool | None = None,
        since: datetime | None = None,
        cursor: int | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        """Query drift events with filters and cursor pagination."""
        with self.session_factory() as session:
            stmt = select(DriftEventModel)

            if severity is not None:
                stmt = stmt.where(DriftEventModel.severity == severity.lower())
            if vendor is not None:
                stmt = stmt.where(DriftEventModel.vendor == vendor)
            if endpoint_id is not None:
                stmt = stmt.where(DriftEventModel.endpoint_id == endpoint_id)
            if acknowledged is not None:
                stmt = stmt.where(DriftEventModel.acknowledged.is_(acknowledged))
            if since is not None:
                since_val = (
                    since.astimezone(timezone.utc).replace(tzinfo=None) if since.tzinfo else since
                )
                stmt = stmt.where(DriftEventModel.detected_at >= since_val)

            total_stmt = select(func.count()).select_from(stmt.subquery())
            total = session.scalar(total_stmt) or 0

            # Cursor pagination
            stmt = stmt.order_by(desc(DriftEventModel.id)).limit(limit + 1)
            if cursor is not None:
                stmt = stmt.where(DriftEventModel.id < cursor)

            rows = list(session.scalars(stmt).all())
            has_next = len(rows) > limit
            if has_next:
                items = rows[:limit]
                next_cursor = str(items[-1].id)
            else:
                items = rows
                next_cursor = None

            events_data: list[dict[str, Any]] = []
            for row in items:
                obs_json = row.observed_schema_json
                obs_dict = json.loads(obs_json) if obs_json else None
                events_data.append(
                    {
                        "id": row.id,
                        "endpoint_id": row.endpoint_id,
                        "vendor": row.vendor,
                        "endpoint": row.endpoint,
                        "field_path": row.field_path,
                        "kind": row.kind,
                        "severity": row.severity,
                        "was_value": row.was_value,
                        "now_value": row.now_value,
                        "detail": row.detail,
                        "observed_schema": obs_dict,
                        "acknowledged": row.acknowledged,
                        "acknowledged_at": row.acknowledged_at,
                        "detected_at": row.detected_at,
                    }
                )

            return events_data, next_cursor, total

    def set_event_acknowledgment(self, event_id: int, acknowledged: bool) -> bool | None:
        """Acknowledge or unacknowledge a single drift event."""
        with self.session_factory() as session:
            evt = session.get(DriftEventModel, event_id)
            if evt is None:
                return None
            evt.acknowledged = acknowledged
            evt.acknowledged_at = utc_now() if acknowledged else None
            session.commit()
            return acknowledged

    def get_stats(self) -> dict[str, Any]:
        """Compute system summary stats and hourly alert distribution for the last 12 hours."""
        with self.session_factory() as session:
            total_endpoints = session.scalar(select(func.count(Endpoint.id))) or 0

            # Active (unacknowledged) alerts counts
            active_stmt = (
                select(DriftEventModel.severity, func.count(DriftEventModel.id))
                .where(DriftEventModel.acknowledged.is_(False))
                .group_by(DriftEventModel.severity)
            )
            active_counts: dict[str, int] = dict(session.execute(active_stmt).all())

            total_active = sum(active_counts.values())
            breaking_active = active_counts.get(SEVERITY_BREAKING, 0)
            warning_active = active_counts.get(SEVERITY_WARNING, 0)
            info_active = active_counts.get(SEVERITY_INFO, 0)

            # Last 12 hours hourly distribution
            now = utc_now().replace(minute=0, second=0, microsecond=0)
            hourly_stats: list[dict[str, Any]] = []

            for i in range(11, -1, -1):
                window_start = now - timedelta(hours=i)
                window_end = window_start + timedelta(hours=1)

                h_stmt = (
                    select(DriftEventModel.severity, func.count(DriftEventModel.id))
                    .where(
                        DriftEventModel.detected_at >= window_start,
                        DriftEventModel.detected_at < window_end,
                    )
                    .group_by(DriftEventModel.severity)
                )
                h_counts: dict[str, int] = dict(session.execute(h_stmt).all())

                hourly_stats.append(
                    {
                        "hour": window_start.isoformat() + "Z",
                        "count": sum(h_counts.values()),
                        "breaking": h_counts.get(SEVERITY_BREAKING, 0),
                        "warning": h_counts.get(SEVERITY_WARNING, 0),
                        "info": h_counts.get(SEVERITY_INFO, 0),
                    }
                )

            return {
                "total_endpoints": total_endpoints,
                "active_alerts_count": total_active,
                "breaking_alerts_count": breaking_active,
                "warning_alerts_count": warning_active,
                "info_alerts_count": info_active,
                "alerts_per_hour": hourly_stats,
            }
