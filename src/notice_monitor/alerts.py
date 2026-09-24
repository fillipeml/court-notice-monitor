"""The e-mail to the team: one message per sweep, grouped by account and by triage category.

DRY_RUN prints instead of sending. Demo mode sends through the local outbox.
"""

from __future__ import annotations

from .config import Config
from .mail import Mailer
from .notice import Notice
from .triage import AUTOMATED

NewNotice = tuple[Notice, str, str]  # (notice, category, account)


def build_subject(new: list[NewNotice], urgent_days: int, primary: str) -> str:
    automated = sum(1 for _, cat, _ in new if cat == AUTOMATED)
    human = len(new) - automated
    urgent = any(n.deadline_within(urgent_days) or n.urgent for n, _, _ in new)
    parts = []
    if automated:
        parts.append(f"{automated} service(s) of process / formal notice(s)")
    if human:
        parts.append(f"{human} for human handling")
    summary = " and ".join(parts) or f"{len(new)} communication(s)"
    accounts = sorted({account for _, _, account in new})
    where = f" [{', '.join(accounts)}]" if accounts != [primary] else ""
    prefix = "[URGENT] " if urgent else ""
    return f"{prefix}[Judicial Domicile] {summary}{where} - action required"


def _line(n: Notice) -> str:
    deadline = n.acknowledge_by or "no deadline given"
    urgent = " [URGENT]" if n.urgent else ""
    return (
        f"- {n.type or '?'}{urgent} | case {n.case_number or '?'} | parties: {n.parties()} | "
        f"{n.court or 'court not given'} | sent {n.sent_at[:10] or '?'} | acknowledge by {deadline}"
    )


def build_body(new: list[NewNotice]) -> str:
    lines: list[str] = ["NEW COMMUNICATIONS IN THE ELECTRONIC JUDICIAL DOMICILE", ""]
    for account in sorted({a for _, _, a in new}):
        group = [(n, cat) for n, cat, a in new if a == account]
        automated = [n for n, cat in group if cat == AUTOMATED]
        human = [n for n, cat in group if cat != AUTOMATED]
        lines.append(f"=== ACCOUNT: {account} ===")
        if automated:
            lines.append("Service of process and formal notices (automated flow):")
            lines.extend(_line(n) for n in automated)
        if human:
            lines.append("FOR HUMAN HANDLING (the automation does NOT open these):")
            lines.extend(_line(n) for n in human)
        lines.append("")
    lines.append(
        "Reminder: never open a communication outside the approved flow; opening it acknowledges service."
    )
    lines.append("")
    lines.append("Automated message - court-notice-monitor.")
    return "\n".join(lines)


def send(config: Config, mailer: Mailer, subject: str, body: str) -> bool:
    """Returns True only when the alert actually left (real send or demo outbox)."""
    if config.dry_run:
        print(f"[DRY_RUN] Subject: {subject}")
        print("[DRY_RUN] To:", config.email_recipients or "(no recipients configured)")
        print(body)
        return False
    if not config.demo_mode:
        config.require_mail()
    mailer.send(subject, body, config.recipients or ["team@example.com"])
    return True


def send_failure(config: Config, mailer: Mailer, error: str) -> bool:
    """Failure alert: silence is never read as success.

    Best effort, never raises: the original failure is the information that matters;
    this is the safety net.
    """
    subject = "[FAILURE] Judicial Domicile sweep did NOT run - check the inbox manually"
    body = (
        "The automated sweep of the Electronic Judicial Domicile FAILED.\n\n"
        f"Error: {error}\n\n"
        "Immediate action: check the inbox manually today "
        "(https://domicilio-eletronico.pdpj.jus.br) and call the automation owner.\n\n"
        "Automated message - court-notice-monitor."
    )
    try:
        return send(config, mailer, subject, body)
    except Exception as exc:  # noqa: BLE001 - the safety net must not take the process down
        print(f"WARNING: the failure alert could not be sent either: {exc}")
        return False
