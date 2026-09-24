"""Authentication against the PDPJ gateway.

The staging Swagger declares BasicAuth; the institutional documentation says OAuth2
client credentials. Both are implemented and `PDPJ_AUTH_MODE` chooses; OAuth is the one
that works in practice (verified 2026-08-28).
"""

from __future__ import annotations

import base64
import time

import requests

from .config import Config


class Authenticator:
    def __init__(self, config: Config, session: requests.Session | None = None) -> None:
        self._config = config
        self._session = session or requests.Session()
        self._token = ""
        self._expires_at = 0.0

    def header(self) -> dict[str, str]:
        if self._config.auth_mode == "basic":
            pair = f"{self._config.client_id}:{self._config.client_secret}".encode()
            return {"Authorization": "Basic " + base64.b64encode(pair).decode()}
        return {"Authorization": f"Bearer {self._get_token()}"}

    def _get_token(self) -> str:
        if self._token and time.monotonic() < self._expires_at:
            return self._token
        if not self._config.token_url:
            raise ValueError("PDPJ_TOKEN_URL is required with PDPJ_AUTH_MODE=oauth")
        response = self._session.post(
            self._config.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"token request failed ({response.status_code}): {response.text[:300]}"
            )
        body = response.json()
        self._token = body["access_token"]
        self._expires_at = (
            time.monotonic() + int(body.get("expires_in", 300)) - 60
        )  # renew a minute early
        return self._token
