# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses semantic versioning.

## [0.1.0] - 2026-09-24

### Added

- Read-only client for the PDPJ electronic judicial domicile: OAuth2 client credentials, paginated listing, tenant resolution through `/api/v1/eu`, documented API quirks.
- Triage by communication type; unknown types always go to a human.
- Idempotent SQLite state, one e-mail per sweep grouped by account and category, `[URGENT]` marking, failure alert and health check.
- Multi-account sweep with per-inbox failure isolation.
- Demo mode with a fixture inbox and a local outbox; 63 offline tests; CI runs the demo sweep on every push.
- Windows Task Scheduler registration script and Dockerfile.
