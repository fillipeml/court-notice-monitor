# court-notice-monitor

A read-only daily sweep of a company's inbox at Brazil's electronic judicial domicile (the national platform where courts serve companies electronically). It lists new communications, triages them by type, e-mails the team the same morning, and never opens anything, because opening a communication is the legal act of acknowledging it. Running in production for a law firm since September 2026, rebranded and anonymised here.

![CI](https://github.com/fillipeml/court-notice-monitor/actions/workflows/ci.yml/badge.svg) ![Licence: MIT](https://img.shields.io/badge/licence-MIT-informational)

**Status:** in production (pilot) · **Runs offline:** yes, `DEMO_MODE=true` needs no credential and no network

```
$ notice-monitor
Environment: DEMO | base: https://gateway.stg.cloud.pje.jus.br/domicilio-eletronico-hml | DRY_RUN: False
tenantId obtained via /api/v1/eu: 00000000-0000-0000-0000-000000000000 (store it in PDPJ_TENANT_ID to skip this call)
Run report:
  period: 2026-09-17 to 2026-09-24
  accounts: ['primary']
  failed_accounts: []
  listed: 6
  new: 6
  new_automated: 3
  new_human: 3
  alert_sent: True
```

The alert lands in `.demo/outbox/` as the e-mail the team would receive. Every party and case number in the demo is invented.

## The problem

A company served electronically has three business days to acknowledge, and after ten calendar days it is deemed served whether anyone read it or not. Missing a communication means a default judgment. Checking the inbox by hand every morning is tedious, easy to forget, and dangerous in the other direction: the platform treats fetching a communication's text as acknowledgement, so a curious click starts a deadline. The firm needed something that reads the list every business day, tells the lawyers what arrived, flags what is urgent, and is physically incapable of opening anything.

## What it does

- Sweeps the inbox every business day through the platform's official API, over a rolling window, and stores what it has seen so nothing is alerted twice.
- Triages each communication by its type: service of process and formal notices go to the automated flow; court notices that start procedural deadlines, and anything unknown, are flagged for a human and never touched.
- Sends one e-mail per sweep, grouped by monitored company and by category, marked `[URGENT]` when an acknowledgement deadline is within a day or the court flagged it.
- Monitors several companies (one API credential each), isolating a failure in one inbox from the others.
- Alerts on its own failure and offers a health check, because a quiet automation is not the same as a working one.

## Architecture

```mermaid
flowchart LR
  S[Task Scheduler\n08:00 business days] --> C[cli]
  C --> A[api_client\nGET only]
  A --> N[notice.py\nmap API fields once]
  N --> T[triage\nby type]
  T --> ST[(SQLite state\nnotices + runs)]
  ST -->|new only| AL[alerts]
  AL --> M[Mailer\nGraph | Outbox]
  C --> H[health]
  A -. DEMO_MODE .-> F[FixtureNoticeClient]
```

The API client authenticates with OAuth2 client credentials against the platform's SSO and lists communications page by page. Each raw item is mapped once into a `Notice` (English field names from here on), classified, and inserted into SQLite; only inserts that succeed are new. New notices become one e-mail through a `Mailer` interface: Microsoft Graph in production, a local outbox in demo mode. The factory is the only module that reads `DEMO_MODE`.

## Design decisions

- **Read-only by construction, not by discipline.** The API client has no write method. The acknowledgement endpoint lives in its own module that raises `NotImplementedError` and documents the three conditions an implementation would need (legal approval, a human decision per item, an explicit flag). A reviewer can prove the property by reading one file.
- **Unknown means human.** Triage is a two-element allow-list. A new communication type the platform adds tomorrow is flagged for a person, never processed. Cost: the team sees an occasional item it could have ignored. Gain: no silent misclassification.
- **Idempotency in the database, not in the schedule.** Every notice is inserted with `INSERT OR IGNORE` on its platform id (or a synthetic key when the platform omits one). The window overlaps by seven days on purpose; a missed run or a re-run costs nothing and duplicates nothing.
- **Silence is never success.** A failed sweep sends a failure e-mail. If that fails too, it is logged and swallowed, never raised, so the original error stays the headline. `--health` answers whether the last scheduled run happened, whether it succeeded, and whether the configuration is still sound.
- **Map the API once, at the boundary.** The platform speaks Portuguese (`numeroComunicacao`, `dataFinalCiencia`). `notice.py` translates every field once; everything else is English. Wire names are listed in the glossary and never renamed.
- **Document the API where it bit.** The OpenAPI document declares BasicAuth that the gateway rejects with 401; dates must be `OffsetDateTime` or the API returns 500; the status filter accepts only two letters; the `tenantId` header is mandatory and its absence is also a 500; the staging database does not contain production registrations. Each of these is a comment next to the code that works around it, learned the expensive way.

## How AI was used

- **Generated:** the original Portuguese version was written with an AI coding assistant over several weeks against the real API; this English version was produced by translating and restructuring it with the same assistant, introducing the `Notice` boundary model and the `Mailer` interface in the process.
- **Rewritten by me:** the API contract facts came from running against staging and production and reading the errors; the assistant's first drafts assumed the Swagger was right (Basic auth, plain dates, a three-value status enum) and were corrected against observed behaviour. The scheduler script gained battery and wake settings after a real missed run on a laptop.
- **Validated:** 63 tests run offline against the same fixture the demo uses; the CI job runs the demo sweep twice and the health check, so idempotency and delivery are exercised on every push.
- **Rejected:** a version of the state module that keyed notices by case number (two communications on one case collided); a retry loop that also retried 4xx responses.
- **Commits:** made with an AI coding assistant; attribution trailers are omitted and AI usage is documented here.

## Evaluation

There is no model in this system; every decision is a rule, and the rules are the test suite. The triage table has one test per type, including unknown, empty and `None`. The sweep is tested end to end on six synthetic communications: three automated, three human, one urgent, two without a deadline, one of an unknown type. The second run of the same sweep must find nothing new.

## Cost & latency

One paginated `GET` per monitored company per business day, plus one token request. A sweep over a handful of inboxes finishes in a few seconds. The platform's API is metered by the operator; the firm's own inbox produced zero communications in a year, which made monitoring it a free insurance policy and moved the value to client inboxes.

## Known failure modes

- The platform answers `200` with an empty body when a credential has no registration in that environment; the sweep reports the inbox as failed rather than as empty.
- A company registered in production but not in staging cannot be tested in staging without a separate registration; the pilot ran read-only against production for that reason.
- If the scheduled task does not fire (machine off, battery policy), nothing runs; the health check exists to make that visible, and the window overlap makes the next run catch up.
- The list endpoint carries metadata only. Anything requiring the text of a communication is out of scope by design.

## Data & privacy

In production the sweep reads communication metadata (case number, parties, court, deadlines) and stores it in a local SQLite file inside the firm's infrastructure; alerts go through the firm's Microsoft 365 tenant; nothing is sent to any third party. The lawyer's tax id travels only in the platform's audit header. This repository runs on fictional data: every party is invented and every case number fails the official check digit.

## Tests & CI

`uv run pytest` runs 63 tests, all offline: configuration parsing (including the `.env` quirk where a filled value below an empty placeholder must win), triage, the notice model and state idempotency, alert wording and urgency, Graph payloads against a fake session, the outbox, health verdicts, the multi-account sweep with an injected failure, and the CLI end to end in demo mode. CI runs lint, tests, the demo sweep with delivery to the outbox, the health check, and a gitleaks scan.

## Stack

`Python 3.12` `uv` `requests` `SQLite` `Microsoft Graph` `OAuth2 client credentials` `pytest` `ruff` `GitHub Actions` `Windows Task Scheduler`

## Running locally

```bash
git clone https://github.com/fillipeml/court-notice-monitor
cd court-notice-monitor
uv sync
cp .env.example .env          # DEMO_MODE=true; set DRY_RUN=false and EMAIL_RECIPIENTS to see delivery
uv run notice-monitor         # sweep the fixture inbox, deliver to .demo/outbox
uv run notice-monitor         # nothing new: idempotent
uv run notice-monitor --health
uv run pytest
```

Live mode: set `DEMO_MODE=false`, the platform credentials, the responsible lawyer's tax id and the Graph application settings in `.env`; run `notice-monitor --diagnose` once, store the printed `tenantId`, then schedule `scripts/register_scheduled_task.ps1`. Additional companies go in `client_accounts.json` (see the example).

With Docker:

```bash
docker build -t court-notice-monitor .
docker run --rm -v notice-data:/data court-notice-monitor
docker run --rm -v notice-data:/data court-notice-monitor --health
```

## Demo mode

`DEMO_MODE=true` replaces the API client with one that replays `fixtures/notices.json` and the Graph mailer with a folder of `.eml` files. Configuration, triage, state, alerts and the CLI are the same code that runs in production. See [docs/DEMO.md](docs/DEMO.md) for the three-minute walkthrough and [docs/GLOSSARY.md](docs/GLOSSARY.md) for the procedural terms kept in Portuguese.

## What I'd do next

- Assisted acknowledgement: a per-item approval in the team's mail client that triggers the acknowledgement call and stores the receipt, behind the flag and the module that already exist for it.
- Registration of new cases in the firm's case-management system from the same sweep, once the vendor exposes the webhook.
- A weekly digest of everything flagged for humans that was never acted on.

## Licence

MIT
