from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return current UTC datetime without timezone info for DB consistency."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Base class for all schemawatch database models."""

    pass


class Endpoint(Base):
    """Monitored API endpoint for a specific vendor."""

    __tablename__ = "endpoints"
    __table_args__ = (UniqueConstraint("vendor", "endpoint", name="uq_endpoints_vendor_endpoint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(1024), index=True, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_baseline_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    baselines: Mapped[list[Baseline]] = relationship(
        "Baseline", back_populates="endpoint_rel", cascade="all, delete-orphan"
    )
    events: Mapped[list[DriftEventModel]] = relationship(
        "DriftEventModel", back_populates="endpoint_rel", cascade="all, delete-orphan"
    )


class Baseline(Base):
    """Versioned JSON baseline schema representation for an endpoint."""

    __tablename__ = "baselines"
    __table_args__ = (
        UniqueConstraint("endpoint_id", "version", name="uq_baselines_endpoint_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("endpoints.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    endpoint_rel: Mapped[Endpoint] = relationship("Endpoint", back_populates="baselines")


class DriftEventModel(Base):
    """Recorded schema drift change between baseline and observed traffic."""

    __tablename__ = "drift_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("endpoints.id", ondelete="CASCADE"), index=True, nullable=False
    )
    vendor: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(1024), index=True, nullable=False)
    field_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    was_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    now_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_schema_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, index=True, nullable=False
    )

    endpoint_rel: Mapped[Endpoint] = relationship("Endpoint", back_populates="events")
    deliveries: Mapped[list[AlertDelivery]] = relationship(
        "AlertDelivery", back_populates="drift_event_rel", cascade="all, delete-orphan"
    )


class AlertDelivery(Base):
    """Record of an alert delivery attempt to an external channel."""

    __tablename__ = "alert_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drift_event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("drift_events.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    drift_event_rel: Mapped[DriftEventModel] = relationship(
        "DriftEventModel", back_populates="deliveries"
    )
