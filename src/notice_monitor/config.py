"""Configuration from the environment (and `.env`). No secret lives in code or in git."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path

# PDPJ gateways per environment. Production was verified on 2026-08-28: /v3/api-docs
# answers 200 with the same OpenAPI contract as staging.
BASE_URLS = {
    "staging": "https://gateway.stg.cloud.pje.jus.br/domicilio-eletronico-hml",
    "production": "https://gateway.cloud.pje.jus.br/domicilio-eletronico",
}

# PDPJ Keycloak SSO (OAuth2). The OpenAPI document declares "BasicAuth" but never
# defines the scheme, and the gateway answers 401 to Basic: real authentication is a
# client-credentials token from the SSO. Credential databases are separate per
# environment (a staging credential gets invalid_client on the production SSO).
TOKEN_URLS = {
    "staging": "https://sso.stg.cloud.pje.jus.br/auth/realms/pje/protocol/openid-connect/token",
    "production": "https://sso.cloud.pje.jus.br/auth/realms/pje/protocol/openid-connect/token",
}

ENVIRONMENTS = tuple(BASE_URLS)


def load_dotenv(path: Path) -> None:
    """Load `.env` without a third-party dependency.

    Variables already set in the process win over the file. Inside the file, a repeated
    key with a filled value wins over an empty occurrence (common when a new block is
    pasted below the template); otherwise an empty placeholder at the top would silently
    cancel the real value further down.
    """
    if not path.exists():
        return
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value or key not in values:
            values[key] = value
    for key, value in values.items():
        os.environ.setdefault(key, value)


def _flag(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes"}


@dataclass
class ClientAccount:
    """An additional monitored inbox (a client of the firm), with its own API credential."""

    name: str
    client_id: str
    client_secret: str
    tenant_id: str = ""

    @classmethod
    def load_file(cls, path: Path) -> list[ClientAccount]:
        """Read `client_accounts.json` (git-ignored). Missing file = primary account only."""
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            raise ValueError(f"invalid client accounts file ({path.name}): {exc}") from exc
        accounts = []
        for item in raw:
            missing = [
                k
                for k in ("name", "client_id", "client_secret")
                if not str(item.get(k, "")).strip()
            ]
            if missing:
                raise ValueError(
                    f"client account missing required fields {missing} in {path.name}: {item.get('name') or item}"
                )
            accounts.append(
                cls(
                    name=str(item["name"]).strip(),
                    client_id=str(item["client_id"]).strip(),
                    client_secret=str(item["client_secret"]).strip(),
                    tenant_id=str(item.get("tenant_id", "")).strip(),
                )
            )
        return accounts


@dataclass
class Config:
    client_id: str = ""
    client_secret: str = ""
    on_behalf_of_cpf: str = ""  # the responsible lawyer's tax id, sent as the audit header
    environment: str = "staging"
    auth_mode: str = "oauth"  # oauth | basic
    token_url: str = ""
    tenant_id: str = ""
    base_url: str = BASE_URLS["staging"]
    dry_run: bool = True
    demo_mode: bool = False
    db_path: Path = field(default_factory=lambda: Path("data/state.sqlite"))
    window_days: int = 7
    urgent_deadline_days: int = 1
    email_recipients: str = ""
    email_sender: str = "notices@example.com"
    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = ""
    client_accounts: list[ClientAccount] = field(default_factory=list)
    primary_account_name: str = "primary"
    fixtures_path: Path = field(default_factory=lambda: Path("fixtures/notices.json"))
    outbox_dir: Path = field(default_factory=lambda: Path(".demo/outbox"))

    def with_account(self, account: ClientAccount) -> Config:
        """Copy of this config pointing at a client's credential.

        Inherits environment, URLs, the audit tax id and mail settings; swaps only the
        credential and tenant. No nested client accounts, to avoid recursion.
        """
        return replace(
            self,
            client_id=account.client_id,
            client_secret=account.client_secret,
            tenant_id=account.tenant_id,
            client_accounts=[],
        )

    @property
    def recipients(self) -> list[str]:
        return [e.strip() for e in self.email_recipients.split(",") if e.strip()]

    @classmethod
    def from_env(cls, dotenv: Path | None = Path(".env")) -> Config:
        if dotenv is not None:
            load_dotenv(dotenv)
        env = os.environ.get

        environment = env("PDPJ_ENVIRONMENT", "staging").strip().lower()
        if environment not in ENVIRONMENTS:
            raise ValueError(
                f"invalid PDPJ_ENVIRONMENT: {environment!r} (use staging or production)"
            )

        base_url = env(f"PDPJ_BASE_URL_{environment.upper()}", "").strip() or BASE_URLS[environment]

        cpf = env("PDPJ_ON_BEHALF_OF_CPF", "").strip()
        if cpf and (len(cpf) != 11 or not cpf.isdigit()):
            raise ValueError("PDPJ_ON_BEHALF_OF_CPF must be 11 digits, no punctuation")

        auth_mode = env("PDPJ_AUTH_MODE", "oauth").strip().lower()
        if auth_mode not in {"basic", "oauth"}:
            raise ValueError(f"invalid PDPJ_AUTH_MODE: {auth_mode!r} (use oauth or basic)")

        db_raw = env("DB_PATH", "").strip()
        demo_mode = _flag(env("DEMO_MODE"), default=False)
        db_path = (
            Path(db_raw)
            if db_raw
            else Path(".demo/state.sqlite" if demo_mode else "data/state.sqlite")
        )

        return cls(
            client_id=env("PDPJ_CLIENT_ID", "").strip(),
            client_secret=env("PDPJ_CLIENT_SECRET", "").strip(),
            on_behalf_of_cpf=cpf,
            environment=environment,
            auth_mode=auth_mode,
            token_url=env("PDPJ_TOKEN_URL", "").strip() or TOKEN_URLS[environment],
            tenant_id=env("PDPJ_TENANT_ID", "").strip(),
            base_url=base_url.rstrip("/"),
            dry_run=_flag(env("DRY_RUN"), default=True),
            demo_mode=demo_mode,
            db_path=db_path,
            window_days=int(env("WINDOW_DAYS", "7")),
            urgent_deadline_days=int(env("URGENT_DEADLINE_DAYS", "1")),
            email_recipients=env("EMAIL_RECIPIENTS", "").strip(),
            email_sender=env("EMAIL_SENDER", "").strip() or "notices@example.com",
            graph_tenant_id=env("GRAPH_TENANT_ID", "").strip(),
            graph_client_id=env("GRAPH_CLIENT_ID", "").strip(),
            graph_client_secret=env("GRAPH_CLIENT_SECRET", "").strip(),
            client_accounts=ClientAccount.load_file(
                Path(env("CLIENT_ACCOUNTS_PATH", "").strip() or "client_accounts.json")
            ),
            primary_account_name=env("PRIMARY_ACCOUNT_NAME", "").strip() or "primary",
            fixtures_path=Path(env("FIXTURES_PATH", "").strip() or "fixtures/notices.json"),
            outbox_dir=Path(env("OUTBOX_DIR", "").strip() or ".demo/outbox"),
        )

    def require_mail(self) -> None:
        """Validate what a REAL e-mail send needs (outside dry run and demo mode)."""
        missing = [
            name
            for name, value in [
                ("GRAPH_TENANT_ID", self.graph_tenant_id),
                ("GRAPH_CLIENT_ID", self.graph_client_id),
                ("GRAPH_CLIENT_SECRET", self.graph_client_secret),
                ("EMAIL_RECIPIENTS", self.email_recipients),
            ]
            if not value
        ]
        if missing:
            raise ValueError(f"real e-mail delivery needs in .env: {', '.join(missing)}")

    def require_credentials(self) -> None:
        missing = [
            name
            for name, value in [
                ("PDPJ_CLIENT_ID", self.client_id),
                ("PDPJ_CLIENT_SECRET", self.client_secret),
                ("PDPJ_ON_BEHALF_OF_CPF", self.on_behalf_of_cpf),
            ]
            if not value
        ]
        if missing:
            raise ValueError(f"missing credentials in .env: {', '.join(missing)}")
