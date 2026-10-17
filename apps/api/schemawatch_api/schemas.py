from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service health status ('ok')")
    version: str = Field(..., description="Schemawatch API version")


class EndpointResponse(BaseModel):
    """Monitored API endpoint metadata and health status."""

    id: int = Field(..., description="Unique endpoint ID")
    vendor: str = Field(..., description="Third-party vendor identifier")
    endpoint: str = Field(..., description="Normalized API endpoint path")
    sample_count: int = Field(..., description="Total learned/observed samples")
    current_baseline_version: int | None = Field(
        None, description="Active baseline schema version, or null if still learning"
    )
    open_alerts_count: int = Field(
        ..., description="Number of currently unacknowledged drift alerts"
    )
    status: str = Field(
        ...,
        description="Endpoint status: 'learning', 'healthy', 'warning', or 'broken'",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class BaselineResponse(BaseModel):
    """Versioned schema baseline for an endpoint."""

    id: int = Field(..., description="Unique baseline ID")
    endpoint_id: int = Field(..., description="Parent endpoint ID")
    version: int = Field(..., description="Baseline version number")
    schema_dict: dict[str, Any] = Field(
        ..., alias="schema", description="Inferred SchemaNode JSON representation"
    )
    created_at: datetime = Field(..., description="Timestamp when baseline was adopted")

    model_config = {"populate_by_name": True}


class DriftEventResponse(BaseModel):
    """Recorded API contract drift event change."""

    id: int = Field(..., description="Unique drift event ID")
    endpoint_id: int = Field(..., description="Associated endpoint ID")
    vendor: str = Field(..., description="Vendor identifier")
    endpoint: str = Field(..., description="Endpoint path")
    field_path: str = Field(..., description="JSONPath of drifting field")
    kind: str = Field(..., description="Change kind (e.g. 'type_changed', 'field_missing')")
    severity: str = Field(..., description="Severity level ('breaking', 'warning', 'info')")
    was_value: str | None = Field(None, description="Previous baseline type or representation")
    now_value: str | None = Field(None, description="Observed type or representation")
    detail: str | None = Field(None, description="Human-readable description of drift")
    observed_schema: dict[str, Any] | None = Field(
        None, description="Observed SchemaNode structure at time of drift"
    )
    acknowledged: bool = Field(..., description="Whether this drift event has been acknowledged")
    acknowledged_at: datetime | None = Field(None, description="Timestamp of acknowledgment")
    detected_at: datetime = Field(..., description="Detection timestamp")


class HourlyStat(BaseModel):
    """Aggregated drift alert counts for a single hourly window."""

    hour: str = Field(..., description="ISO 8601 hourly timestamp")
    count: int = Field(..., description="Total alerts in this hour")
    breaking: int = Field(..., description="Breaking alerts in this hour")
    warning: int = Field(..., description="Warning alerts in this hour")
    info: int = Field(..., description="Info alerts in this hour")


class StatsResponse(BaseModel):
    """Global system health and alert frequency statistics."""

    total_endpoints: int = Field(..., description="Total monitored endpoints")
    active_alerts_count: int = Field(..., description="Total unacknowledged drift alerts")
    breaking_alerts_count: int = Field(..., description="Total active breaking alerts")
    warning_alerts_count: int = Field(..., description="Total active warning alerts")
    info_alerts_count: int = Field(..., description="Total active info alerts")
    alerts_per_hour: list[HourlyStat] = Field(
        ..., description="Hourly alert distribution for the last 12 hours"
    )


class ConfigResponse(BaseModel):
    """Public read-only server configuration. NEVER exposes tokens or URLs."""

    slack_configured: bool = Field(..., description="Whether Slack alerts are configured")
    webhook_configured: bool = Field(..., description="Whether Webhook alerts are configured")
    dev_mode: bool = Field(..., description="Whether developer mode is active")
    min_alert_severity: str = Field(..., description="Minimum severity threshold for alerts")
    learn_samples: int = Field(..., description="Required samples to establish baseline")
    sample_rate: float = Field(..., description="Configured sampling rate")
    cooldown_seconds: int = Field(..., description="Cooldown deduplication window in seconds")
    database_type: str = Field(..., description="Storage engine type ('sqlite' or 'postgres')")


class IngestRequest(BaseModel):
    """Payload ingest request for out-of-band monitoring."""

    vendor: str = Field(..., min_length=1, max_length=255, description="Vendor name")
    endpoint: str = Field(..., min_length=1, max_length=1024, description="Endpoint path")
    payload: Any = Field(..., description="JSON payload data structure (dict, list, primitive)")


class IngestResponse(BaseModel):
    """Result of payload ingestion and observation."""

    status: str = Field(..., description="Processing status ('ok')")
    observed: bool = Field(..., description="True if payload was observed, False if sampled out")
    changes_detected: int = Field(..., description="Number of new active drift changes detected")
    event_ids: list[int] = Field(default_factory=list, description="IDs of newly persisted events")


class AcceptResponse(BaseModel):
    """Result of accepting an observed shape as the new baseline."""

    status: str = Field(..., description="Operation status ('ok')")
    endpoint_id: int = Field(..., description="Endpoint ID")
    new_baseline_version: int = Field(..., description="New baseline version number")
    events_acknowledged: int = Field(..., description="Number of open events marked acknowledged")


class AckResponse(BaseModel):
    """Result of acknowledging or unacknowledging an event."""

    status: str = Field(..., description="Operation status ('ok')")
    event_id: int = Field(..., description="Event ID")
    acknowledged: bool = Field(..., description="Current acknowledgment status")


class PaginatedResponse(BaseModel, Generic[T]):
    """Cursor-paginated list of items."""

    items: list[T] = Field(..., description="List of items for current page")
    next_cursor: str | None = Field(None, description="Cursor token for next page, or null if end")
    total: int | None = Field(None, description="Total matching items if computed")
