"""Command-line entry point.

    notice-monitor                  # sweep the configured window (WINDOW_DAYS)
    notice-monitor --me             # identify the tenant (GET /api/v1/eu) and exit
    notice-monitor --diagnose       # check auth, representative link and company registration
    notice-monitor --sample 20      # save raw communications for schema study (no alert)
    notice-monitor --health         # pilot health from the local state, no API call

Read only: no call acknowledges a communication.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import factory
from .alerts import send_failure
from .api_client import ApiError
from .config import Config
from .state import State
from .sweep import run, sample

DEMO_CNPJ = "00000000000100"  # invalid by construction; replace with the real company id


def _diagnose(client, cnpj: str) -> int:
    """Check, in order, what must be in place for the sweep to work."""
    print("\n[1/3] Authentication and profile (GET /api/v1/eu)")
    profile = client.me()
    if profile:
        print(
            "      OK: profile found. tenantId:",
            profile.get("tenantId") or "(inside perfis[], see JSON)",
        )
        print(json.dumps(profile, indent=2, ensure_ascii=False)[:800])
    else:
        print(
            "      EMPTY body: the credential authenticates, but no profile is linked in this environment."
        )

    print("\n[2/3] Representative link (GET /api/v2/existe-representante)")
    link = client.representative_status() or {}
    print(
        "      empresaPrivada:",
        link.get("empresaPrivada"),
        "| orgaoPublico:",
        link.get("orgaoPublico"),
    )
    if link and not any(link.values()):
        print("      The authenticated tax id does NOT represent any company in this environment.")

    print(
        f"\n[3/3] Company registration in the PDPJ base (GET /api/v1/pessoas-juridicas-pdpj?cnpj={cnpj})"
    )
    company = client.lookup_company(cnpj)
    if company:
        print("      OK:", company.get("razaoSocial"), "| active:", company.get("ativo"))
    else:
        print("      Company not found.")

    if not profile:
        print("\nCONCLUSION: the company <-> credential link is missing in THIS environment.")
        print("Without a tenantId there is no listing (the API answers 500).")
        return 3
    print("\nCONCLUSION: ready to sweep. Store the tenantId in PDPJ_TENANT_ID.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only sweep of the electronic judicial domicile"
    )
    parser.add_argument("--me", action="store_true", help="GET /api/v1/eu (identity and tenant)")
    parser.add_argument(
        "--diagnose", action="store_true", help="check auth, representative link and registration"
    )
    parser.add_argument("--cnpj", default=DEMO_CNPJ, help="company id for --diagnose (digits only)")
    parser.add_argument("--window-days", type=int, default=None, help="how many days back to sweep")
    parser.add_argument(
        "--sample", type=int, metavar="N", help="save the first N raw communications (no alert)"
    )
    parser.add_argument(
        "--health", action="store_true", help="pilot health from the local state, no API call"
    )
    args = parser.parse_args(argv)

    config = Config.from_env()

    if args.health:
        from .health import report

        text, code = report(config)
        print(text)
        return code

    if not config.demo_mode:
        config.require_credentials()
    if args.window_days:
        config.window_days = args.window_days

    mode = "DEMO" if config.demo_mode else config.environment
    print(f"Environment: {mode} | base: {config.base_url} | DRY_RUN: {config.dry_run}")

    mailer = factory.build_mailer(config)
    try:
        if args.diagnose:
            return _diagnose(factory.build_client(config), args.cnpj)
        if args.me:
            profile = factory.build_client(config).me()
            if profile is None:
                print("GET /api/v1/eu answered 200 with an EMPTY body.")
                print(
                    "Authentication works, but no profile is linked to this credential in this environment."
                )
                print("Run `notice-monitor --diagnose` for details.")
                return 3
            print(json.dumps(profile, indent=2, ensure_ascii=False))
            return 0
        if args.sample:
            target = sample(config, args.sample, factory.build_client(config))
            print(f"Sample saved to {target} (outside version control).")
            return 0
        result = run(config, factory.build_client, mailer)
    except ApiError as exc:
        print(f"SWEEP FAILED: {exc}", file=sys.stderr)
        print(
            "Action: check the inbox manually today (contingency) and investigate the cause.",
            file=sys.stderr,
        )
        try:
            state = State(config.db_path)
            state.record_run(success=False, dry_run=config.dry_run, error=str(exc)[:500])
            state.close()
        except Exception as inner:  # noqa: BLE001 - recording must never mask the original failure
            print(f"WARNING: could not record the failure in the history: {inner}", file=sys.stderr)
        sent = send_failure(config, mailer, str(exc))
        print(
            f"Failure alert by e-mail: {'sent' if sent else 'not sent (DRY_RUN or error)'}",
            file=sys.stderr,
        )
        return 2

    print("Run report:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    if result.get("failed_accounts"):
        errors = "; ".join(result["failed_accounts"])
        print(f"FAILURE in inbox(es): {errors}", file=sys.stderr)
        print("Action: check the affected inboxes manually today (contingency).", file=sys.stderr)
        sent = send_failure(config, mailer, f"Inbox(es) failed during the sweep: {errors}")
        print(
            f"Failure alert by e-mail: {'sent' if sent else 'not sent (DRY_RUN or error)'}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
