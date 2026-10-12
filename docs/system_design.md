# schemawatch — System Design

## 1. Deployment Modes
1. **Library mode (default)**: hook into the HTTP client inside the application process.
2. **Sidecar / proxy mode (v0.3)**: an HTTP proxy sits between the app and the vendor; no code changes in the app.
3. **Ingest API mode (v0.2)**: services POST sampled payloads to schemawatch from any language.

## 2. High-Level Architecture
```
+--------------------+   vendor API call   +------------------+
|  Your application  | ------------------> |  Third-party API |
|   (httpx client)   | <------------------ |  (payments, KYC) |
+---------+----------+      response       +------------------+
          | event hook (sampled copy)
          v
+-----------------------------------------------------------+
|                     schemawatch core                      |
|   Sampler -> Redactor -> Inferrer -> Differ -> Severity   |
|                 |                               |         |
|           Baseline Store                   Alert Dedupe   |
+--------------+---------------+-----------+----------------+
               |               |           |
               v               v           v
          +-----------+  +-----------+  +----------------+
          |   Redis   |  |  SQLite / |  | Alert channels |
          | baselines |  |  Postgres |  | Slack, webhook |
          | + cooldown|  |  events   |  |  email (later) |
          +-----------+  +-----+-----+  +----------------+
                               |
                        +------v---------+
                        | FastAPI server |---> Dashboard / CLI
                        +----------------+
```

## 3. Components
- **Integration hook**: Copies the response body, applies the sampling rate, enqueues without blocking the call.
- **Redactor**: Replaces every value with a type-preserving placeholder, caps array sizes, drops payloads above a size limit.
- **Inferrer**: Builds a schema node (types, properties, required, items) from one payload; merges nodes across samples.
- **Baseline manager**: Learning phase (first N samples), frozen baseline, versioning, accept and reset operations.
- **Differ**: Compares the observed schema to the baseline and emits typed change objects.
- **Severity engine**: Maps a change kind to breaking, warning or info.
- **Dedupe and cooldown**: Prevents the same (vendor, endpoint, path, kind) alert from repeating within the cooldown window.
- **Alert dispatcher**: Sends alerts to channels with retries; failures never reach host app.

## 4. Core Algorithms

### Schema Inference
Each JSON value maps to a type: `null`, `boolean`, `integer`, `number`, `string`, `array` or `object`.
Objects record properties and a required list; arrays record a merged item schema.
Booleans are checked before integers because bool is a subclass of int in Python.

### Merging Samples
Types are unioned. For objects, a field is required only if present in every merged sample. This stops optional fields from causing false alarms.

### Drift Detection
The observed payload schema is compared with the baseline recursively:

| Change | Condition | Severity |
| --- | --- | --- |
| `type_changed` | Observed type not allowed by baseline (integer allowed where number expected) | `breaking` |
| `became_nullable` | null observed where baseline had no null | `breaking` |
| `field_missing` (required) | Required baseline field absent | `breaking` |
| `field_missing` (optional) | Non-required baseline field absent | `info` |
| `enum_changed` | New value outside learned set (v0.2) | `warning` |
| `field_added` | New field not in baseline | `info` |

When a type mismatch is found at a node, comparison does not descend further, which avoids noisy child changes.

### Dedupe
Key = hash of vendor, endpoint, field path and change kind. Atomic SET with cooldown prevents spam.
