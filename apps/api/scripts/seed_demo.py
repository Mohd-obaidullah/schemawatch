from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

# Ensure repo packages are importable if executed directly outside uv
_api_dir = Path(__file__).resolve().parent.parent
_repo_root = _api_dir.parent.parent
for _p in (str(_api_dir), str(_repo_root / "packages" / "core")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from schemawatch.infer import infer_schema  # noqa: E402
from schemawatch_api.config import Settings  # noqa: E402
from schemawatch_api.database import (  # noqa: E402
    create_db_engine,
    create_session_factory,
    init_db,
)
from schemawatch_api.models import (  # noqa: E402
    Baseline,
    DriftEventModel,
    Endpoint,
    utc_now,
)
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def seed_demo_data(session: Session, learn_samples: int = 10) -> dict[str, int]:
    """Seed realistic vendors, endpoints, baselines, and sample drift events.

    Includes:
    - 4 realistic vendors and endpoints (Stripe, Twilio, SendGrid, GitHub)
    - 4 baseline schemas
    - Exactly:
      - 1 breaking event (Stripe: integer -> string)
      - 1 warning event (Twilio: enum value changed)
      - 1 info event (SendGrid: new field added)
      - 1 acknowledged event (GitHub: field became nullable)
    """
    now = utc_now()

    # 1. Vendor: Stripe (charges) -> unacknowledged breaking alert
    stripe_baseline_node = infer_schema(
        {
            "id": "ch_3N8v2xLkdIwHu7ix0rW7e4jC",
            "amount": 2500,
            "currency": "usd",
            "status": "succeeded",
            "customer": "cus_N7x6v8LkdIwHu",
            "paid": True,
        }
    )
    stripe_ep = Endpoint(
        vendor="stripe",
        endpoint="POST /v1/charges",
        sample_count=learn_samples + 45,
        current_baseline_version=1,
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(hours=2),
    )
    session.add(stripe_ep)
    session.flush()

    session.add(
        Baseline(
            endpoint_id=stripe_ep.id,
            version=1,
            schema_json=json.dumps(stripe_baseline_node.to_dict()),
            created_at=now - timedelta(days=5),
        )
    )

    observed_stripe_drift = infer_schema(
        {
            "id": "ch_3N8v2xLkdIwHu7ix0rW7e4jC",
            "amount": "25.00_USD",
            "currency": "usd",
            "status": "succeeded",
            "customer": "cus_N7x6v8LkdIwHu",
            "paid": True,
        }
    )
    stripe_event = DriftEventModel(
        endpoint_id=stripe_ep.id,
        vendor=stripe_ep.vendor,
        endpoint=stripe_ep.endpoint,
        field_path="$.amount",
        kind="type_changed",
        severity="breaking",
        was_value="integer",
        now_value="string",
        detail="integer -> string",
        observed_schema_json=json.dumps(observed_stripe_drift.to_dict()),
        acknowledged=False,
        detected_at=now - timedelta(hours=2),
    )
    session.add(stripe_event)

    # 2. Vendor: Twilio (messages) -> unacknowledged warning alert
    twilio_baseline_node = infer_schema(
        {
            "sid": "SM1234567890abcdef1234567890abcdef",
            "status": "sent",
            "to": "+15551234567",
            "num_segments": 1,
            "price": "0.0075",
        }
    )
    twilio_ep = Endpoint(
        vendor="twilio",
        endpoint="POST /2010-04-01/Accounts/{id}/Messages",
        sample_count=learn_samples + 120,
        current_baseline_version=1,
        created_at=now - timedelta(days=7),
        updated_at=now - timedelta(hours=4),
    )
    session.add(twilio_ep)
    session.flush()

    session.add(
        Baseline(
            endpoint_id=twilio_ep.id,
            version=1,
            schema_json=json.dumps(twilio_baseline_node.to_dict()),
            created_at=now - timedelta(days=7),
        )
    )

    observed_twilio_drift = infer_schema(
        {
            "sid": "SM1234567890abcdef1234567890abcdef",
            "status": "partially_delivered",
            "to": "+15551234567",
            "num_segments": 1,
            "price": "0.0075",
        }
    )
    twilio_event = DriftEventModel(
        endpoint_id=twilio_ep.id,
        vendor=twilio_ep.vendor,
        endpoint=twilio_ep.endpoint,
        field_path="$.status",
        kind="enum_changed",
        severity="warning",
        was_value="sent",
        now_value="partially_delivered",
        detail="new enum value: partially_delivered",
        observed_schema_json=json.dumps(observed_twilio_drift.to_dict()),
        acknowledged=False,
        detected_at=now - timedelta(hours=4),
    )
    session.add(twilio_event)

    # 3. Vendor: SendGrid (mail send) -> unacknowledged info alert (field added)
    sendgrid_baseline_node = infer_schema(
        {
            "message_id": "msg_abc123",
            "recipient": "user@example.com",
            "status": "accepted",
        }
    )
    sendgrid_ep = Endpoint(
        vendor="sendgrid",
        endpoint="POST /v3/mail/send",
        sample_count=learn_samples + 80,
        current_baseline_version=1,
        created_at=now - timedelta(days=10),
        updated_at=now - timedelta(hours=6),
    )
    session.add(sendgrid_ep)
    session.flush()

    session.add(
        Baseline(
            endpoint_id=sendgrid_ep.id,
            version=1,
            schema_json=json.dumps(sendgrid_baseline_node.to_dict()),
            created_at=now - timedelta(days=10),
        )
    )

    observed_sendgrid_drift = infer_schema(
        {
            "message_id": "msg_abc123",
            "recipient": "user@example.com",
            "status": "accepted",
            "ip_pool": "transactional-1",
        }
    )
    sendgrid_event = DriftEventModel(
        endpoint_id=sendgrid_ep.id,
        vendor=sendgrid_ep.vendor,
        endpoint=sendgrid_ep.endpoint,
        field_path="$.ip_pool",
        kind="field_added",
        severity="info",
        was_value="absent",
        now_value="present",
        detail="new field added",
        observed_schema_json=json.dumps(observed_sendgrid_drift.to_dict()),
        acknowledged=False,
        detected_at=now - timedelta(hours=6),
    )
    session.add(sendgrid_event)

    # 4. Vendor: GitHub (user) -> acknowledged event
    github_baseline_node = infer_schema(
        {
            "id": 583231,
            "login": "octocat",
            "avatar_url": "https://avatars.githubusercontent.com/u/583231",
            "type": "User",
            "site_admin": False,
        }
    )
    github_ep = Endpoint(
        vendor="github",
        endpoint="GET /users/{id}",
        sample_count=learn_samples + 200,
        current_baseline_version=1,
        created_at=now - timedelta(days=14),
        updated_at=now - timedelta(days=1),
    )
    session.add(github_ep)
    session.flush()

    session.add(
        Baseline(
            endpoint_id=github_ep.id,
            version=1,
            schema_json=json.dumps(github_baseline_node.to_dict()),
            created_at=now - timedelta(days=14),
        )
    )

    github_event = DriftEventModel(
        endpoint_id=github_ep.id,
        vendor=github_ep.vendor,
        endpoint=github_ep.endpoint,
        field_path="$.site_admin",
        kind="became_nullable",
        severity="breaking",
        was_value="boolean",
        now_value="null",
        detail="became nullable",
        observed_schema_json=json.dumps(github_baseline_node.to_dict()),
        acknowledged=True,
        acknowledged_at=now - timedelta(days=1, hours=2),
        detected_at=now - timedelta(days=1, hours=5),
    )
    session.add(github_event)

    session.commit()

    return {
        "endpoints": 4,
        "events": 4,
    }


def main() -> None:
    settings = Settings(dev_mode=True)
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        # Check if already seeded
        count = session.scalar(select(Endpoint.id).limit(1))
        if count:
            print("Database already contains data, skipping seed.")
            return

        result = seed_demo_data(session, learn_samples=settings.learn_samples)
        print(f"Successfully seeded {result['endpoints']} endpoints and {result['events']} events.")


if __name__ == "__main__":
    main()
