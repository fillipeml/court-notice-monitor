"""The domain model, built once at the API boundary.

The PDPJ API speaks Portuguese (`numeroComunicacao`, `dataFinalCiencia`, ...). Everything
past this module speaks English. Field names on the wire are documented in
docs/GLOSSARY.md and never renamed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


def _names(value: Any) -> list[str]:
    """Party lists arrive either as person objects or as bare strings."""
    if not value:
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = item.get("nome") or item.get("nomeParte") or item.get("razaoSocial")
            if name:
                names.append(str(name))
        elif item:
            names.append(str(item))
    return names


@dataclass(frozen=True)
class Notice:
    """One communication from a court, as listed (never opened) by the sweep."""

    id: str  # numeroComunicacao; empty when the API omits it
    case_number: str  # numeroProcesso (CNJ unified format)
    type: str  # tipoComunicacao: CITACAO, NOTIFICACAO, INTIMACAO, VISTA, IPTA, ...
    status: str  # EM_CURSO, INTEIRO_TEOR_OBTIDO, CIENTE, ...
    sent_at: str  # dataComunicacao (ISO timestamp as sent)
    acknowledge_by: str | None  # dataFinalCiencia: legal deadline to acknowledge
    court: str  # tribunalOrigem
    urgent: bool  # urgente == "S"
    claimants: list[str] = field(default_factory=list)  # autoresReclamantes
    defendants: list[str] = field(default_factory=list)  # reus
    recipient: str = ""  # nomeDestinatario

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Notice:
        return cls(
            id=str(raw.get("numeroComunicacao") or "").strip(),
            case_number=str(raw.get("numeroProcesso") or "").strip(),
            type=str(raw.get("tipoComunicacao") or "").strip().upper(),
            status=str(raw.get("status") or "").strip(),
            sent_at=str(raw.get("dataComunicacao") or ""),
            acknowledge_by=(
                str(raw["dataFinalCiencia"])[:10] if raw.get("dataFinalCiencia") else None
            ),
            court=str(raw.get("tribunalOrigem") or "").strip(),
            urgent=str(raw.get("urgente") or "").strip().upper() == "S",
            claimants=_names(raw.get("autoresReclamantes")),
            defendants=_names(raw.get("reus")),
            recipient=str(raw.get("nomeDestinatario") or "").strip(),
        )

    def key(self, account: str) -> str:
        """Idempotency key. Without an id there is no identity; build a synthetic one."""
        return self.id or f"NO-ID/{account}/{self.case_number}/{self.sent_at}"

    def parties(self) -> str:
        if self.claimants or self.defendants:
            text = (
                f"{', '.join(self.claimants) or 'claimant not given'}"
                f" v {', '.join(self.defendants) or 'defendant not given'}"
            )
        else:
            text = self.recipient or "parties not given"
        return text if len(text) <= 120 else text[:117] + "..."

    def deadline_within(self, days: int, today: date | None = None) -> bool:
        if not self.acknowledge_by:
            return False
        try:
            deadline = date.fromisoformat(self.acknowledge_by)
        except ValueError:
            return False
        return deadline <= (today or date.today()) + timedelta(days=days)
