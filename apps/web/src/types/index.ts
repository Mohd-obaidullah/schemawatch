export type Severity = "breaking" | "warning" | "info";

export type ChangeKind =
  | "type_changed"
  | "field_missing"
  | "field_added"
  | "became_nullable"
  | "enum_changed";

export type EndpointStatus = "healthy" | "drifting" | "broken";

export interface SchemaNode {
  type: string | string[];
  required?: string[];
  properties?: Record<string, SchemaNode>;
  items?: SchemaNode;
  enum?: (string | number | boolean | null)[];
  [key: string]: unknown;
}

export interface Endpoint {
  id: number;
  vendor: string;
  endpoint: string;
  sample_count: number;
  current_baseline_version: number;
  open_alerts_count: number;
  status: EndpointStatus;
  created_at: string;
  updated_at: string;
}

export interface DriftEvent {
  id: number;
  endpoint_id: number;
  vendor: string;
  endpoint: string;
  field_path: string;
  kind: ChangeKind;
  severity: Severity;
  was_value: string;
  now_value: string;
  detail: string;
  observed_schema: Record<string, unknown>;
  acknowledged: boolean;
  acknowledged_at: string | null;
  detected_at: string;
}

export interface Baseline {
  id: number;
  endpoint_id: number;
  version: number;
  schema: Record<string, unknown>;
  created_at: string;
}

export interface HourlyStat {
  hour: string;
  count: number;
  breaking: number;
  warning: number;
  info: number;
}

export interface Stats {
  total_endpoints: number;
  active_alerts_count: number;
  breaking_alerts_count: number;
  warning_alerts_count: number;
  info_alerts_count: number;
  alerts_per_hour: HourlyStat[];
}

export interface AppConfig {
  slack_configured: boolean;
  webhook_configured: boolean;
  dev_mode: boolean;
  min_alert_severity: string;
  learn_samples: number;
  sample_rate: number;
  cooldown_seconds: number;
  database_type: string;
}

export interface PaginatedResult<T> {
  items: T[];
  next_cursor: number | null;
  total: number;
}

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";
