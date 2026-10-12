from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly without prior pip install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "core"))

from schemawatch import Watchdog


def main() -> None:
    print("=" * 60)
    print("schemawatch demo: third-party API contract drift monitor")
    print("=" * 60)

    # Initialize Watchdog with 5 samples for the learning phase
    watchdog = Watchdog(
        learning_threshold=5,
        sample_rate=1.0,
        cooldown_seconds=60,
    )

    vendor = "payco"
    endpoint = "/v1/payments"

    print("\nPhase 1: Learning baseline schema from live traffic (5 samples)...")
    for i in range(1, 6):
        sample = {
            "user_id": 1000 + i,
            "amount": 49.99,
            "currency": "USD",
            "status": "completed",
        }
        changes = watchdog.observe(vendor, endpoint, sample)
        print(f"  [Sample {i}/5] Observed payload. In-flight drift alerts: {len(changes)}")

    baseline = watchdog.store.get_baseline(vendor, endpoint)
    print(f"\nBaseline established for {vendor} {endpoint}:")
    if baseline:
        print(f"  Types: {baseline.types}")
        print(f"  Required fields: {sorted(baseline.required)}")
        print(f"  Properties: {list(baseline.properties.keys())}")

    print("\nPhase 2: Sending a normal conforming payload...")
    normal_payload = {
        "user_id": 1006,
        "amount": 120.00,
        "currency": "USD",
        "status": "completed",
    }
    normal_changes = watchdog.observe(vendor, endpoint, normal_payload)
    print(f"  Drift detected: {len(normal_changes)}")

    print("\nPhase 3: Vendor silently changes 'user_id' from integer to string...")
    drift_payload_1 = {
        "user_id": "usr_1007",  # BREAKING: integer -> string
        "amount": 75.50,
        "currency": "USD",
        "status": "completed",
    }
    changes_1 = watchdog.observe(vendor, endpoint, drift_payload_1)
    for change in changes_1:
        sev = change.severity.upper()
        msg = f"{vendor} {endpoint} {change.field}: {change.detail} ({change.kind})"
        print(f"  ALERT [{sev}]: {msg}")

    print("\nPhase 4: Vendor drops required field 'amount'...")
    drift_payload_2 = {
        "user_id": 1008,
        # amount missing! (BREAKING)
        "currency": "USD",
        "status": "completed",
    }
    changes_2 = watchdog.observe(vendor, endpoint, drift_payload_2)
    for change in changes_2:
        sev = change.severity.upper()
        msg = f"{vendor} {endpoint} {change.field}: {change.detail} ({change.kind})"
        print(f"  ALERT [{sev}]: {msg}")

    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
