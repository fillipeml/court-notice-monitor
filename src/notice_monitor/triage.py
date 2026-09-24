"""Triage by communication type: non-negotiable rule number one, in code.

Only CITACAO (service of process) and NOTIFICACAO (formal notice) enter the automated
flow. INTIMACAO (court notice that starts a procedural deadline), VISTA, IPTA and any
unknown type go to a human. When in doubt, a human; never the automation.
"""

from __future__ import annotations

AUTOMATED = "AUTOMATED"
HUMAN = "HUMAN"

AUTOMATED_TYPES = frozenset({"CITACAO", "NOTIFICACAO"})


def classify(notice_type: str | None) -> str:
    kind = (notice_type or "").strip().upper()
    return AUTOMATED if kind in AUTOMATED_TYPES else HUMAN
