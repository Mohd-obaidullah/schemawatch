from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

# Ensure schemawatch core is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "core"))

from schemawatch import DriftEvent, Watchdog, create_httpx_hook


def main() -> None:
    print("=" * 65)
    print("schemawatch M2: httpx Event Hook + Mock Vendor Drift Demo")
    print("=" * 65)

    detected_alerts: list[DriftEvent] = []

    def on_alert_callback(event: DriftEvent) -> None:
        detected_alerts.append(event)
        for change in event.changes:
            sev = change.severity.upper()
            msg = f"{change.field}: {change.detail} ({change.kind})"
            print(f"  ALERT [{sev}]: {event.vendor} {event.endpoint} {msg}")

    # Watchdog with 5 samples learning phase
    watchdog = Watchdog(
        learning_threshold=5,
        sample_rate=1.0,
        cooldown_seconds=60,
        on_alert=on_alert_callback,
    )

    hook = create_httpx_hook(
        watchdog=watchdog,
        vendor="payco",
        endpoint="/v1/payments",
    )

    request_counter = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_counter
        request_counter += 1

        if request_counter <= 5:
            # Conforming samples during learning phase
            data = {
                "user_id": 1000 + request_counter,
                "amount": 49.99,
                "currency": "USD",
            }
        elif request_counter == 6:
            # Drift 1: user_id integer changed to string (BREAKING)
            data = {
                "user_id": "usr_9999",
                "amount": 49.99,
                "currency": "USD",
            }
        elif request_counter == 7:
            # Drift 2: required field amount missing (BREAKING)
            data = {
                "user_id": 1007,
                "currency": "USD",
            }
        else:
            data = {"user_id": 1008, "amount": 50.0, "currency": "USD"}

        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            content=json.dumps(data).encode("utf-8"),
            request=request,
        )

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport, event_hooks={"response": [hook]})

    try:
        print("\nPhase 1: Sending 5 client requests to learn vendor baseline...")
        for i in range(1, 6):
            resp = client.get("https://api.payco.com/v1/payments")
            assert resp.status_code == 200
            hook.flush()
            print(f"  Request {i}/5 completed. Body: {resp.json()}")

        print("\nPhase 2: Sending request with 'user_id' changed to string...")
        resp_drift_1 = client.get("https://api.payco.com/v1/payments")
        assert resp_drift_1.status_code == 200
        hook.flush()

        print("\nPhase 3: Sending request with 'amount' missing...")
        resp_drift_2 = client.get("https://api.payco.com/v1/payments")
        assert resp_drift_2.status_code == 200
        hook.flush()

    finally:
        hook.close()
        client.close()

    print("\n" + "=" * 65)
    print(f"Demo complete! Total breaking alerts captured: {len(detected_alerts)}")
    print("=" * 65)


if __name__ == "__main__":
    main()
