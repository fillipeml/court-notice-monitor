# Three-minute demo

Before the call, in the repository root:

```bash
cp .env.example .env            # DEMO_MODE=true; set DRY_RUN=false and EMAIL_RECIPIENTS=team@example.com
uv sync
```

| Time | Do | Say |
|---|---|---|
| 0:00 | `uv run notice-monitor` | "Every business day this lists the company's inbox at the national judiciary platform, triages each communication by type and e-mails the team. Nothing is ever opened: opening acknowledges service. Here it runs on six invented communications." |
| 0:30 | Open the file in `.demo/outbox/` | "The same e-mail a lawyer receives: automated items on top, the ones a human must handle below, the reminder never to open anything outside the flow. The subject is [URGENT] because one deadline is within a day." |
| 1:00 | `uv run notice-monitor` again | "Zero new: the SQLite state makes the sweep idempotent. A missed day or an overlapping window never produces a duplicate alert." |
| 1:20 | `uv run notice-monitor --health` | "Silence is never success. This checks that the sweep ran when it should, that it succeeded, and that the configuration is still sound. The scheduler calls the sweep; a human calls this." |
| 1:45 | Open `src/notice_monitor/api_client.py` | "The client has no write method by construction. The acknowledgement module exists only to raise NotImplementedError and say why. The API quirks are documented where they bit: OffsetDateTime, the two-letter status enum, the tenantId header that returns 500 when missing, the Swagger that declares an auth scheme the gateway rejects." |
| 2:20 | Open `src/notice_monitor/sweep.py`, the account loop | "One credential per monitored company. A failure in one inbox is reported and the others still run; the failure alert goes out separately." |
| 2:45 | `uv run pytest -q` | "Tests run offline against the same fixture the demo uses." |

## Questions to expect

- "Why not let it acknowledge automatically?" Acknowledgement starts a legal deadline against the company. That decision belongs to a lawyer, per item. The code makes the boundary impossible to cross by accident.
- "How did you find the API quirks?" By running against staging and production and reading the 500s. Each one is now a comment next to the code that handles it.
- "What happens if the machine is off at 08:00?" Task Scheduler starts the task when the machine is back, the window overlaps by seven days, and the state removes duplicates. The health check flags the gap.
