# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-18

### Fixed
- Fixed key collision in schema diff and merge where literal `"*"` keys collided with the dynamic-key map wildcard sentinel `*`.
  - Introduced `DYNAMIC_KEY_WILDCARD` sentinel to distinguish dynamic maps from literal `"*"` property names.
  - Resolved false breaking `became_nullable` drift alerts for payloads containing literal `"*"` keys alongside siblings (e.g. `{'0': None, '*': False}`).
  - Fixed property collision during `merge` of dynamic maps and literal asterisk objects, ensuring associativity, commutativity, and lossless serialization round-trips.
  - Added backward compatibility: legacy baselines persisted with `properties: {"*": ...}` automatically upgrade on read into dynamic wildcard maps.
  - Frontend schema tree now displays `* (dynamic map)` badge for wildcard maps to clearly distinguish them from literal `"*"` keys.

### Added
- Initial open-source release of `schemawatch` (core library) and `schemawatch-api` (FastAPI monitoring server).
- HTTP middleware and hooks for third-party client monitoring (including `httpx`).
- Automated schema inference, merge, redaction, and contract drift alerting (Slack, generic webhooks).
