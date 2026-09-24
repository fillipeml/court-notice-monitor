from datetime import date, timedelta

import pytest

from notice_monitor.alerts import build_body, build_subject, send, send_failure
from notice_monitor.config import Config
from notice_monitor.mail import OutboxMailer
from notice_monitor.notice import Notice
from notice_monitor.triage import AUTOMATED, HUMAN


def _notice(deadline_in_days=None, urgent="N", kind="CITACAO", nid="X"):
    deadline = (
        (date.today() + timedelta(days=deadline_in_days)).isoformat()
        if deadline_in_days is not None
        else None
    )
    return Notice.from_api(
        {
            "numeroComunicacao": nid,
            "tipoComunicacao": kind,
            "dataFinalCiencia": deadline,
            "urgente": urgent,
        }
    )


def test_subject_is_urgent_when_the_deadline_is_close():
    assert build_subject([(_notice(1), AUTOMATED, "primary")], 1, "primary").startswith("[URGENT]")


def test_subject_is_calm_with_a_distant_deadline():
    subject = build_subject([(_notice(10), AUTOMATED, "primary")], 1, "primary")
    assert not subject.startswith("[URGENT]")
    assert "1 service(s) of process" in subject


def test_subject_respects_the_api_urgent_flag():
    assert build_subject([(_notice(10, urgent="S"), HUMAN, "primary")], 1, "primary").startswith(
        "[URGENT]"
    )


def test_subject_without_deadline_does_not_break():
    assert "[Judicial Domicile]" in build_subject(
        [(_notice(None), AUTOMATED, "primary")], 1, "primary"
    )


def test_subject_names_client_accounts_only_when_present():
    only_primary = build_subject([(_notice(10), AUTOMATED, "primary")], 1, "primary")
    with_client = build_subject([(_notice(10), AUTOMATED, "ALFA LTDA.")], 1, "primary")
    assert "[" not in only_primary.replace("[Judicial Domicile]", "")
    assert "[ALFA LTDA.]" in with_client


def test_body_groups_by_account_and_category():
    new = [
        (_notice(5, nid="A"), AUTOMATED, "primary"),
        (_notice(5, kind="INTIMACAO", nid="B"), HUMAN, "primary"),
        (_notice(5, nid="C"), AUTOMATED, "ALFA LTDA."),
    ]
    body = build_body(new)
    assert "=== ACCOUNT: ALFA LTDA. ===" in body and "=== ACCOUNT: primary ===" in body
    assert "FOR HUMAN HANDLING" in body and "INTIMACAO" in body
    assert "never open a communication outside the approved flow" in body


def test_send_in_dry_run_prints_and_never_sends(tmp_path, capsys):
    config = Config(dry_run=True, outbox_dir=tmp_path)
    assert send(config, OutboxMailer(tmp_path), "subject", "body") is False
    assert "subject" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.eml"))


def test_real_send_requires_graph_configuration():
    config = Config(dry_run=False, demo_mode=False)  # no GRAPH_*
    with pytest.raises(ValueError, match="GRAPH_TENANT_ID"):
        send(config, OutboxMailer("unused"), "subject", "body")


def test_demo_send_goes_to_the_outbox(tmp_path):
    config = Config(
        dry_run=False, demo_mode=True, email_recipients="team@example.com", outbox_dir=tmp_path
    )
    assert send(config, OutboxMailer(tmp_path), "subject", "body") is True
    assert len(list(tmp_path.glob("*.eml"))) == 1


def test_send_failure_never_raises(capsys):
    config = Config(
        dry_run=False, demo_mode=False
    )  # no GRAPH_*: send() raises inside, send_failure swallows
    assert send_failure(config, OutboxMailer("unused"), "simulated error") is False
    assert "failure alert" in capsys.readouterr().out.lower()
