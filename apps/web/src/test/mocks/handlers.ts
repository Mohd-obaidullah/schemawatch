import { http, HttpResponse } from "msw";

export const mockStats = {
  total_endpoints: 4,
  active_alerts_count: 3,
  breaking_alerts_count: 1,
  warning_alerts_count: 1,
  info_alerts_count: 1,
  alerts_per_hour: [
    {
      hour: "2026-10-17T18:00:00",
      count: 3,
      breaking: 1,
      warning: 1,
      info: 1,
    },
  ],
};

export const mockConfig = {
  slack_configured: true,
  webhook_configured: false,
  dev_mode: false,
  min_alert_severity: "info",
  learn_samples: 10,
  sample_rate: 1.0,
  cooldown_seconds: 3600,
  database_type: "sqlite",
};

export const mockEndpoints = [
  {
    id: 1,
    vendor: "stripe",
    endpoint: "POST /v1/charges",
    sample_count: 55,
    current_baseline_version: 1,
    open_alerts_count: 1,
    status: "broken",
    created_at: "2026-10-12T10:00:00Z",
    updated_at: "2026-10-17T18:00:00Z",
  },
  {
    id: 2,
    vendor: "twilio",
    endpoint: "POST /2010-04-01/Accounts/{id}/Messages",
    sample_count: 130,
    current_baseline_version: 1,
    open_alerts_count: 1,
    status: "drifting",
    created_at: "2026-10-10T10:00:00Z",
    updated_at: "2026-10-17T16:00:00Z",
  },
];

export const mockEvents = [
  {
    id: 101,
    endpoint_id: 1,
    vendor: "stripe",
    endpoint: "POST /v1/charges",
    field_path: "$.amount",
    kind: "type_changed",
    severity: "breaking",
    was_value: "integer",
    now_value: "string",
    detail: "integer -> string",
    observed_schema: { type: "object" },
    acknowledged: false,
    acknowledged_at: null,
    detected_at: "2026-10-17T18:00:00Z",
  },
  {
    id: 102,
    endpoint_id: 2,
    vendor: "twilio",
    endpoint: "POST /2010-04-01/Accounts/{id}/Messages",
    field_path: "$.status",
    kind: "enum_changed",
    severity: "warning",
    was_value: "sent",
    now_value: "partially_delivered",
    detail: "new enum value: partially_delivered",
    observed_schema: { type: "object" },
    acknowledged: false,
    acknowledged_at: null,
    detected_at: "2026-10-17T16:00:00Z",
  },
  {
    id: 103,
    endpoint_id: 1,
    vendor: "stripe",
    endpoint: "POST /v1/charges",
    field_path: "$.fee",
    kind: "field_added",
    severity: "info",
    was_value: "absent",
    now_value: "present",
    detail: "new field added",
    observed_schema: { type: "object" },
    acknowledged: true,
    acknowledged_at: "2026-10-17T19:00:00Z",
    detected_at: "2026-10-17T15:00:00Z",
  },
];

export const mockBaseline = {
  id: 1,
  endpoint_id: 1,
  version: 1,
  schema: {
    type: "object",
    required: ["id", "amount", "currency"],
    properties: {
      id: { type: "string" },
      amount: { type: "integer" },
      currency: { type: "string" },
    },
  },
  created_at: "2026-10-12T10:00:00Z",
};

export const handlers = [
  http.get("*/api/stats", () => {
    return HttpResponse.json(mockStats);
  }),

  http.get("*/api/config", () => {
    return HttpResponse.json(mockConfig);
  }),

  http.get("*/api/endpoints", () => {
    return HttpResponse.json({
      items: mockEndpoints,
      next_cursor: null,
      total: mockEndpoints.length,
    });
  }),

  http.get("*/api/endpoints/:id", ({ params }) => {
    const ep = mockEndpoints.find((e) => e.id === Number(params.id)) ?? mockEndpoints[0];
    return HttpResponse.json(ep);
  }),

  http.get("*/api/endpoints/:id/baseline", () => {
    return HttpResponse.json(mockBaseline);
  }),

  http.post("*/api/endpoints/:id/accept", ({ params }) => {
    return HttpResponse.json({
      status: "ok",
      endpoint_id: Number(params.id),
      new_baseline_version: 2,
      events_acknowledged: 1,
    });
  }),

  http.get("*/api/events", ({ request }) => {
    const url = new URL(request.url);
    const severity = url.searchParams.get("severity");
    const vendor = url.searchParams.get("vendor");
    const acknowledged = url.searchParams.get("acknowledged");

    let items = [...mockEvents];
    if (severity && severity !== "all") {
      items = items.filter((e) => e.severity === severity);
    }
    if (vendor && vendor !== "all") {
      items = items.filter((e) => e.vendor === vendor);
    }
    if (acknowledged === "false") {
      items = items.filter((e) => !e.acknowledged);
    }

    return HttpResponse.json({
      items,
      next_cursor: null,
      total: items.length,
    });
  }),

  http.post("*/api/events/:id/ack", ({ params }) => {
    return HttpResponse.json({
      status: "ok",
      id: Number(params.id),
      acknowledged: true,
      acknowledged_at: new Date().toISOString(),
    });
  }),

  http.post("*/api/events/:id/unack", ({ params }) => {
    return HttpResponse.json({
      status: "ok",
      id: Number(params.id),
      acknowledged: false,
      acknowledged_at: null,
    });
  }),
];
