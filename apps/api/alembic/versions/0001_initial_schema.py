"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. endpoints
    op.create_table(
        "endpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vendor", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=1024), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_baseline_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vendor", "endpoint", name="uq_endpoints_vendor_endpoint"),
    )
    op.create_index("ix_endpoints_vendor", "endpoints", ["vendor"])
    op.create_index("ix_endpoints_endpoint", "endpoints", ["endpoint"])

    # 2. baselines
    op.create_table(
        "baselines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("endpoint_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_id", "version", name="uq_baselines_endpoint_version"),
    )
    op.create_index("ix_baselines_endpoint_id", "baselines", ["endpoint_id"])

    # 3. drift_events
    op.create_table(
        "drift_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("endpoint_id", sa.Integer(), nullable=False),
        sa.Column("vendor", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=1024), nullable=False),
        sa.Column("field_path", sa.String(length=1024), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("was_value", sa.String(length=255), nullable=True),
        sa.Column("now_value", sa.String(length=255), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("observed_schema_json", sa.Text(), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_drift_events_endpoint_id", "drift_events", ["endpoint_id"])
    op.create_index("ix_drift_events_vendor", "drift_events", ["vendor"])
    op.create_index("ix_drift_events_endpoint", "drift_events", ["endpoint"])
    op.create_index("ix_drift_events_kind", "drift_events", ["kind"])
    op.create_index("ix_drift_events_severity", "drift_events", ["severity"])
    op.create_index("ix_drift_events_acknowledged", "drift_events", ["acknowledged"])
    op.create_index("ix_drift_events_detected_at", "drift_events", ["detected_at"])

    # 4. alert_deliveries
    op.create_table(
        "alert_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("drift_event_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["drift_event_id"], ["drift_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_deliveries_drift_event_id", "alert_deliveries", ["drift_event_id"])


def downgrade() -> None:
    op.drop_table("alert_deliveries")
    op.drop_table("drift_events")
    op.drop_table("baselines")
    op.drop_table("endpoints")
