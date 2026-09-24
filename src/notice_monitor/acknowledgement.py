"""Acknowledging service: DISABLED IN THIS PHASE, BY DESIGN.

PUT /api/v1/processos/{case}/comunicacoes/{id} tells the court the party is aware of the
communication. That has irreversible procedural effect: deadlines start counting. This
module exists only to make the rule explicit in code. An implementation would require:

1. formal approval of the acknowledgement regime by the legal team;
2. an individual human approval per communication;
3. `ACKNOWLEDGE_AUTOMATICALLY=true` set consciously in `.env` (default: false).
"""

from __future__ import annotations


def acknowledge(*_args, **_kwargs) -> None:
    raise NotImplementedError(
        "Acknowledging service is out of scope for this phase and requires a human approval. "
        "See 'Non-negotiable rule number two' in the README."
    )
