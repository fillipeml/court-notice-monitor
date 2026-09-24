import json

from notice_monitor.api_client import ApiError
from notice_monitor.config import ClientAccount, Config
from notice_monitor.demo import DEMO_TENANT, FixtureNoticeClient
from notice_monitor.mail import OutboxMailer
from notice_monitor.sweep import resolve_tenant, run, sample


def test_first_sweep_detects_and_triages_everything(config, capsys):
    result = run(config, FixtureNoticeClient, OutboxMailer(config.outbox_dir))
    assert result["listed"] == 6 and result["new"] == 6
    assert result["new_automated"] == 3  # 2 CITACAO + 1 NOTIFICACAO
    assert result["new_human"] == 3  # INTIMACAO, VISTA and the unknown EDITAL
    assert result["alert_sent"] is False  # DRY_RUN never sends
    out = capsys.readouterr().out
    assert "FOR HUMAN HANDLING" in out and "EDITAL" in out


def test_second_sweep_finds_nothing_new(config):
    run(config, FixtureNoticeClient, OutboxMailer(config.outbox_dir))
    result = run(config, FixtureNoticeClient, OutboxMailer(config.outbox_dir))
    assert result["new"] == 0  # end-to-end idempotency


def test_demo_delivery_writes_to_the_outbox(config):
    config.dry_run = False
    config.email_recipients = "team@example.com"
    result = run(config, FixtureNoticeClient, OutboxMailer(config.outbox_dir))
    assert result["alert_sent"] is True
    files = list(config.outbox_dir.glob("*.eml"))
    assert len(files) == 1
    assert "[URGENT]" in files[0].read_text(encoding="utf-8")  # DEMO-0001 has urgente=S


def test_tenant_is_resolved_through_me(config):
    assert config.tenant_id == ""
    resolve_tenant(config, FixtureNoticeClient(config))
    assert config.tenant_id == DEMO_TENANT


def test_empty_profile_becomes_a_failed_account(config):
    class NoProfileClient(FixtureNoticeClient):
        def me(self):
            return None

    result = run(config, NoProfileClient, OutboxMailer(config.outbox_dir))
    assert result["failed_accounts"] and "not registered" in result["failed_accounts"][0]
    assert result["new"] == 0


def test_one_failing_inbox_does_not_stop_the_others(config):
    config.client_accounts = [ClientAccount(name="ALFA LTDA.", client_id="a", client_secret="b")]

    class FlakyClient(FixtureNoticeClient):
        def list_notices(self, start, end, pending_only=True):
            if self.config.client_id == "a":
                raise ApiError("simulated 500 on the client inbox")
            yield from super().list_notices(start, end, pending_only)

    result = run(config, FlakyClient, OutboxMailer(config.outbox_dir))
    assert result["accounts"] == ["primary", "ALFA LTDA."]
    assert result["failed_accounts"] == ["ALFA LTDA.: simulated 500 on the client inbox"]
    assert result["new"] == 6  # the primary inbox was still processed


def test_sample_saves_raw_json(config):
    target = sample(config, 2, FixtureNoticeClient(config))
    items = json.loads(target.read_text(encoding="utf-8"))
    assert len(items) == 2 and items[0]["numeroComunicacao"] == "DEMO-0001"


def test_fixture_case_numbers_are_synthetic():
    """Every case number in the demo fixture must fail the CNJ check digit."""
    import re

    from _ids import case_number

    raw = json.loads(Config().fixtures_path.read_text(encoding="utf-8"))
    for item in raw:
        n, dd, year, j, tr, unit = re.match(
            r"(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})", item["numeroProcesso"]
        ).groups()
        base = int(f"{n}{year}{j}{tr}{unit}00")
        assert int(dd) != 98 - (base % 97), item["numeroProcesso"]
    assert case_number(1) != case_number(2)
