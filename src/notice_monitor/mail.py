"""Mail delivery behind one interface: Microsoft Graph in production, a local outbox in demo.

Graph pattern: an app registration with the application permission Mail.Send, a
client-credentials token, and POST /users/{sender}/sendMail.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Protocol

import requests

from .config import Config

TIMEOUT = 30


class MailError(RuntimeError):
    pass


class Mailer(Protocol):
    def send(self, subject: str, body: str, recipients: list[str]) -> None: ...


class GraphMailer:
    def __init__(self, config: Config, session: requests.Session | None = None) -> None:
        self._config = config
        self._session = session or requests.Session()
        self._token = ""
        self._expires_at = 0.0

    def _get_token(self) -> str:
        if self._token and time.monotonic() < self._expires_at:
            return self._token
        url = f"https://login.microsoftonline.com/{self._config.graph_tenant_id}/oauth2/v2.0/token"
        response = self._session.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._config.graph_client_id,
                "client_secret": self._config.graph_client_secret,
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            raise MailError(
                f"Graph token request failed ({response.status_code}): {response.text[:300]}"
            )
        body = response.json()
        self._token = body["access_token"]
        self._expires_at = time.monotonic() + int(body.get("expires_in", 300)) - 60
        return self._token

    def send(self, subject: str, body: str, recipients: list[str]) -> None:
        recipients = [r.strip() for r in recipients if r.strip()]
        if not recipients:
            raise MailError("no recipients configured (EMAIL_RECIPIENTS)")
        url = f"https://graph.microsoft.com/v1.0/users/{self._config.email_sender}/sendMail"
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": r}} for r in recipients],
            },
            "saveToSentItems": True,
        }
        response = self._session.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=TIMEOUT,
        )
        if response.status_code != 202:
            raise MailError(
                f"Graph sendMail failed ({response.status_code}): {response.text[:300]}"
            )


class OutboxMailer:
    """Demo adapter: writes each message as a text file so the flow is visible offline."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def send(self, subject: str, body: str, recipients: list[str]) -> None:
        recipients = [r.strip() for r in recipients if r.strip()]
        if not recipients:
            raise MailError("no recipients configured (EMAIL_RECIPIENTS)")
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:60]
        path = self.directory / f"{stamp}-{slug}.eml"
        path.write_text(
            f"To: {', '.join(recipients)}\nSubject: {subject}\n\n{body}\n",
            encoding="utf-8",
        )
