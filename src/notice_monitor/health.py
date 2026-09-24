"""Health check for the pilot: "silence is never success" applied to the routine itself.

Answers three questions: did the sweep run when it should? Did it succeed? Is the
configuration still sound? Meant for the close follow-up of the first weeks:
`notice-monitor --health`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from .config import Config
from .state import State

EXPECTED_HOUR_WITH_SLACK = 9  # the task runs at 08:00; we start asking at 09:00


def expected_last_business_day(now: datetime) -> date:
    """Date on which the last scheduled sweep should have happened."""
    day = now.date()
    if day.weekday() < 5 and now.hour >= EXPECTED_HOUR_WITH_SLACK:
        return day
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def report(config: Config, now: datetime | None = None) -> tuple[str, int]:
    """Returns (report text, exit code): 0 = healthy, 1 = attention."""
    now = now or datetime.now()
    problems: list[str] = []
    lines: list[str] = ["PILOT HEALTH - court-notice-monitor", ""]

    # 1. Configuration
    if config.demo_mode:
        lines.append("[ok] DEMO_MODE=true (fixtures and local outbox)")
    else:
        try:
            config.require_credentials()
            lines.append("[ok] PDPJ credentials present")
        except ValueError as exc:
            problems.append(f"PDPJ credentials: {exc}")
    if config.dry_run:
        problems.append("DRY_RUN=true: the pilot is NOT sending real e-mails")
    else:
        lines.append("[ok] DRY_RUN=false (delivery active)")
    if config.recipients:
        lines.append(f"[ok] Recipients: {', '.join(config.recipients)}")
    else:
        problems.append("EMAIL_RECIPIENTS is empty")

    # 2. Runs
    if not Path(config.db_path).exists():
        problems.append("state database missing: no sweep has run on this machine yet")
    else:
        state = State(config.db_path)
        try:
            runs = state.recent_runs(5)
            summary = state.summary()
        finally:
            state.close()

        if not runs:
            problems.append("no run recorded in the history")
        else:
            last = runs[0]
            last_day = str(last["ran_at"])[:10]
            expected = expected_last_business_day(now).isoformat()
            if last_day < expected:
                problems.append(
                    f"last run was on {last_day}, expected on {expected}: check the scheduled task and the machine"
                )
            else:
                lines.append(f"[ok] Last run: {last['ran_at']}")
            failures = [r for r in runs if not r["success"]]
            if failures and not runs[0]["success"]:
                problems.append(f"the LAST run FAILED: {runs[0]['error']}")
            elif failures:
                lines.append(
                    f"[minor] {len(failures)} failure(s) in the last {len(runs)} runs (the latest succeeded)"
                )
            lines.append("")
            lines.append("Recent runs:")
            for r in runs:
                status = "OK     " if r["success"] else "FAILURE"
                lines.append(
                    f"  {r['ran_at']}  {status} listed={r['listed']} new={r['new']} alert={r['alert_sent']}"
                )
            if summary:
                lines.append(f"Notices known to the state: {summary}")

    lines.append("")
    if problems:
        lines.append("VERDICT: ATTENTION")
        lines.extend(f"  ! {p}" for p in problems)
        return "\n".join(lines), 1
    lines.append("VERDICT: HEALTHY")
    return "\n".join(lines), 0
