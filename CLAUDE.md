# CLAUDE.md

Working rules for AI-assisted changes in this repository. They mirror the README; the README wins on conflict.

## Two non-negotiable rules

1. **Triage by type only.** `CITACAO` and `NOTIFICACAO` enter the automated flow. `INTIMACAO`, `VISTA`, `IPTA` and any unknown type are flagged for a human and never processed. Unknown is never automated.
2. **Read only.** `api_client.py` must not gain any method that acknowledges a communication or fetches its full text (`PUT /api/v1/processos/.../comunicacoes/...`, `linksDocumentos`). Fetching the full text is the acknowledgement, with legal effect. Anything of the kind lives in `acknowledgement.py`, stays `NotImplementedError`, and would need a flag plus a per-item human approval.

## Conventions

- Python 3.12, `uv`, `ruff`, `pytest`. Batch CLI, not a web app.
- `DRY_RUN=true` and `DEMO_MODE` are read only in `config.py` and `factory.py`; business modules never check them.
- API field names (Portuguese) are mapped to English once, in `notice.py`. Everything else is English. Domain terms kept in Portuguese are in `docs/GLOSSARY.md`.
- Tests run offline. Any new external call gets a fake in the tests and a demo adapter.
- Never commit `.env`, `client_accounts.json`, `data/`, `logs/`. Fixtures contain only invented parties and case numbers with invalid check digits.
- Commits: English, Conventional Commits, one logical change each, no AI attribution trailers.
