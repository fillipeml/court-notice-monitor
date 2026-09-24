"""HTTP client for the electronic judicial domicile API. READ ONLY.

Non-negotiable rule number two: this module contains no call that acknowledges a
communication or fetches its full text. Fetching the full text IS the acknowledgement,
with legal effect, and belongs exclusively to `acknowledgement.py` (a later phase,
behind an explicit flag and a human approval).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import date
from typing import Any

import requests

from .auth import Authenticator
from .config import Config

ATTEMPTS = 3
TIMEOUT = 30
PAGE_SIZE = 100


class ApiError(RuntimeError):
    pass


class NoticeApiClient:
    def __init__(
        self,
        config: Config,
        authenticator: Authenticator | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self._session = session or requests.Session()
        self._auth = authenticator or Authenticator(config, self._session)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", **self._auth.header()}
        if self.config.on_behalf_of_cpf:
            headers["On-behalf-Of"] = self.config.on_behalf_of_cpf
        if self.config.tenant_id:
            headers["tenantId"] = self.config.tenant_id
        return headers

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET with retry. Returns None when the API answers 200 with an empty body."""
        url = f"{self.config.base_url}{path}"
        last_failure = ""
        for attempt in range(1, ATTEMPTS + 1):
            try:
                response = self._session.get(
                    url, params=params, headers=self._headers(), timeout=TIMEOUT
                )
            except requests.RequestException as exc:
                last_failure = f"network error: {exc}"
            else:
                if response.status_code == 200:
                    if not response.content.strip():
                        return None  # 200 without a body: no profile or link in this environment
                    try:
                        return response.json()
                    except ValueError:
                        raise ApiError(
                            f"GET {path} returned 200 with a non-JSON body: {response.text[:300]!r}"
                        ) from None
                last_failure = f"HTTP {response.status_code}: {response.text[:300]}"
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    break  # 4xx (except 429) does not improve with retries
            if attempt < ATTEMPTS:
                time.sleep(2**attempt)
        raise ApiError(f"GET {path} failed after {ATTEMPTS} attempt(s): {last_failure}")

    def me(self) -> dict[str, Any] | None:
        """Profile and tenant of the authenticated institution (GET /api/v1/eu).

        None when the credential authenticates but no profile is linked in this
        environment: typical in staging, whose database is separate from production
        and does not contain the company's registration.
        """
        return self._get("/api/v1/eu")

    def lookup_company(self, cnpj: str) -> dict[str, Any] | None:
        """Registration data of a company in the PDPJ base (no tenantId needed)."""
        return self._get("/api/v1/pessoas-juridicas-pdpj", params={"cnpj": cnpj})

    def representative_status(self) -> dict[str, Any] | None:
        """Whether the authenticated tax id represents a private company or public body."""
        return self._get("/api/v2/existe-representante")

    def list_notices(
        self, start: date, end: date, pending_only: bool = True
    ) -> Iterator[dict[str, Any]]:
        """List communications in a period. Does NOT acknowledge anything (metadata only).

        `statusCiente` is mandatory and the real enum (probed in production, 2026-08-28)
        accepts only 'N' (pending) and 'A' (all); 'S' is rejected. The `tenantId` header
        is mandatory too: the API answers HTTP 500 without it, so it is checked first.
        """
        if not self.config.tenant_id:
            raise ApiError(
                "tenantId missing: listing communications requires the tenantId header (UUID). "
                "Run `notice-monitor --me` to obtain it and store it in PDPJ_TENANT_ID. "
                "If GET /api/v1/eu comes back empty, the company is not registered in this environment."
            )
        page = 0
        while True:
            body = self._get(
                "/api/v1/comunicacoes",
                params={
                    # the API requires OffsetDateTime (HTTP 500 with a bare date); Brasília offset
                    "dataInicio": f"{start.isoformat()}T00:00:00-03:00",
                    "dataFim": f"{end.isoformat()}T23:59:59-03:00",
                    "statusCiente": "N" if pending_only else "A",
                    "page": page,
                    "size": PAGE_SIZE,
                },
            )
            # contract: {"page": {...}, "data": [...]}; tolerate a bare list just in case
            if isinstance(body, list):
                yield from body
                return
            items = body.get("data") or []
            yield from items
            info = body.get("page") or {}
            total_pages = int(info.get("totalPages") or 0)
            page += 1
            if not items or page >= total_pages:
                return
