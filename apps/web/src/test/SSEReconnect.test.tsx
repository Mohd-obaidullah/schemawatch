import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { SSEClient } from "@/api/sse";
import type { DriftEvent } from "@/types";

describe("SSEClient Reconnect & Streaming", () => {
  let sseClient: SSEClient;

  beforeEach(() => {
    sseClient = new SSEClient();
  });

  afterEach(() => {
    sseClient.dispose();
  });

  it("handles status transitions and listener registrations", () => {
    const statusCalls: string[] = [];
    const unsubscribe = sseClient.onStatusChange((status) => {
      statusCalls.push(status);
    });

    expect(statusCalls).toContain("disconnected");
    unsubscribe();
  });

  it("dispatches drift events correctly to registered event listeners", () => {
    const receivedEvents: DriftEvent[] = [];
    sseClient.onDriftEvent((event) => {
      receivedEvents.push(event);
    });

    // Simulate parsing an incoming drift SSE event message
    const rawSSEMessage = [
      "event: drift",
      'data: {"id": 99, "endpoint_id": 1, "vendor": "stripe", "endpoint": "POST /charges", "field_path": "$.amount", "kind": "type_changed", "severity": "breaking", "was_value": "int", "now_value": "str", "detail": "changed", "observed_schema": {}, "acknowledged": false, "acknowledged_at": null, "detected_at": "2026-10-17T18:00:00Z"}',
    ].join("\n");

    // Access private dispatch through prototype or simulate dispatch
    // @ts-expect-error testing private dispatch method
    sseClient.parseAndDispatch(rawSSEMessage);

    expect(receivedEvents).toHaveLength(1);
    expect(receivedEvents[0].id).toBe(99);
    expect(receivedEvents[0].vendor).toBe("stripe");
    expect(receivedEvents[0].severity).toBe("breaking");
  });

  it("schedules reconnect with backoff when connection fails", () => {
    vi.useFakeTimers();
    const statuses: string[] = [];
    sseClient.onStatusChange((s) => statuses.push(s));

    // @ts-expect-error test private reconnect
    sseClient.scheduleReconnect();

    expect(statuses).toContain("reconnecting");
    vi.useRealTimers();
  });
});
