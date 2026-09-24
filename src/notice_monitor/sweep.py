"""The sweep: list -> triage -> state -> alert -> run report. One sweep per business day."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Protocol

from . import alerts, triage
from .api_client import ApiError
from .config import Config
from .mail import Mailer
from .notice import Notice
from .state import State


class NoticeSource(Protocol):
    """What the sweep needs from an API client (real or fixture)."""

    config: Config

    def me(self) -> dict[str, Any] | None: ...

    def list_notices(self, start: date, end: date, pending_only: bool = True): ...


ClientFactory = Callable[[Config], NoticeSource]


def resolve_tenant(config: Config, client: NoticeSource) -> None:
    """Ensure the tenantId, fetching it through GET /api/v1/eu when not configured."""
    if config.tenant_id:
        return
    profile = client.me()
    if not profile:
        raise ApiError(
            "GET /api/v1/eu answered empty: the company is not registered in this "
            f"environment ({config.environment}). Without a registration there is no tenantId and no notices."
        )
    # real /eu shape (production, 2026-08-28): {"pessoa": {...}, "perfis": [{"tenantId": ...}], "termo": ...}
    profiles = profile.get("perfis") or []
    tenant = profile.get("tenantId") or (profiles[0].get("tenantId") if profiles else None)
    if not tenant:
        raise ApiError(
            f"GET /api/v1/eu did not include a tenantId; fields received: {sorted(profile)}"
        )
    if len(profiles) > 1:
        print(
            f"Note: {len(profiles)} profiles in /eu; using the first ({profiles[0].get('tenantName')})"
        )
    config.tenant_id = str(tenant)
    print(
        f"tenantId obtained via /api/v1/eu: {config.tenant_id} (store it in PDPJ_TENANT_ID to skip this call)"
    )


def sample(config: Config, count: int, client: NoticeSource) -> Path:
    """Save the first N RAW communications next to the state file, for schema study."""
    resolve_tenant(config, client)
    end = date.today()
    start = end - timedelta(days=config.window_days)
    items: list[dict[str, Any]] = []
    for raw in client.list_notices(start, end, pending_only=True):
        items.append(raw)
        if len(items) >= count:
            break
    target = Path(config.db_path).parent / f"sample-{config.environment}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def run(config: Config, client_factory: ClientFactory, mailer: Mailer) -> dict[str, Any]:
    """Sweep the primary inbox and every configured client inbox.

    A failure in one inbox does not stop the others: it lands in `failed_accounts` and the
    caller decides about the failure alert.
    """
    end = date.today()
    start = end - timedelta(days=config.window_days)

    accounts: list[tuple[str, NoticeSource]] = [
        (config.primary_account_name, client_factory(config))
    ]
    accounts += [
        (acc.name, client_factory(config.with_account(acc))) for acc in config.client_accounts
    ]

    state = State(config.db_path)
    try:
        listed_total = 0
        new: list[alerts.NewNotice] = []
        failed_accounts: list[str] = []
        for account_name, client in accounts:
            try:
                resolve_tenant(client.config, client)
                raw_items = list(client.list_notices(start, end, pending_only=True))
            except ApiError as exc:
                print(f"FAILURE in inbox {account_name}: {exc}")
                failed_accounts.append(f"{account_name}: {exc}")
                continue
            listed_total += len(raw_items)
            for raw in raw_items:
                notice = Notice.from_api(raw)
                category = triage.classify(notice.type)
                if state.record(notice, category, account_name):
                    new.append((notice, category, account_name))

        alerted = False
        if new:
            subject = alerts.build_subject(
                new, config.urgent_deadline_days, config.primary_account_name
            )
            body = alerts.build_body(new)
            alerted = alerts.send(config, mailer, subject, body)
            if alerted:
                state.mark_alerted([n.key(account) for n, _, account in new])
        state.record_run(
            success=not failed_accounts,
            listed=listed_total,
            new=len(new),
            alert_sent=alerted,
            dry_run=config.dry_run,
            error="; ".join(failed_accounts)[:500] or None,
        )
    finally:
        state.close()

    return {
        "period": f"{start.isoformat()} to {end.isoformat()}",
        "accounts": [name for name, _ in accounts],
        "failed_accounts": failed_accounts,
        "listed": listed_total,
        "new": len(new),
        "new_automated": sum(1 for _, cat, _ in new if cat == triage.AUTOMATED),
        "new_human": sum(1 for _, cat, _ in new if cat != triage.AUTOMATED),
        "alert_sent": alerted,
        "dry_run": config.dry_run,
        "demo_mode": config.demo_mode,
    }
