"""Demo adapter for the API: replays synthetic communications from a JSON file.

The fixture ignores the requested date window on purpose, so the demo is the same on any
day. Every case number in the fixture has an invalid check digit and every party is
invented.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from .config import Config

DEMO_TENANT = "00000000-0000-0000-0000-000000000000"


class FixtureNoticeClient:
    def __init__(self, config: Config, path: Path | None = None) -> None:
        self.config = config
        self.path = Path(path or config.fixtures_path)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            raise FileNotFoundError(f"demo fixture not found: {self.path}")
        return json.loads(self.path.read_text(encoding="utf-8"))

    def me(self) -> dict[str, Any] | None:
        return {
            "pessoa": {"tipoPessoa": "JURIDICA", "cpfCnpj": "00000000000100"},
            "perfis": [{"tenantId": DEMO_TENANT, "tenantName": "DEMO COMPANY"}],
            "termo": None,
        }

    def lookup_company(self, cnpj: str) -> dict[str, Any] | None:
        return {"razaoSocial": "DEMO COMPANY LTDA", "ativo": True, "cnpj": cnpj}

    def representative_status(self) -> dict[str, Any] | None:
        return {"empresaPrivada": True, "orgaoPublico": False}

    def list_notices(
        self, start: date, end: date, pending_only: bool = True
    ) -> Iterator[dict[str, Any]]:
        yield from self._load()
