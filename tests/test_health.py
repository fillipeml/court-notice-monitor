from datetime import datetime

from notice_monitor.config import Config
from notice_monitor.health import expected_last_business_day, report
from notice_monitor.state import State


def test_expected_day_on_a_weekday_after_the_slack_hour():
    # Wednesday 2026-09-16 at 10:00 -> that same Wednesday
    assert expected_last_business_day(datetime(2026, 9, 16, 10, 0)).isoformat() == "2026-09-16"


def test_expected_day_before_the_slack_hour_and_on_weekends():
    assert (
        expected_last_business_day(datetime(2026, 9, 16, 8, 15)).isoformat() == "2026-09-15"
    )  # Tuesday
    assert (
        expected_last_business_day(datetime(2026, 9, 20, 12, 0)).isoformat() == "2026-09-18"
    )  # Sunday -> Friday
    assert (
        expected_last_business_day(datetime(2026, 9, 21, 7, 0)).isoformat() == "2026-09-18"
    )  # Monday 07:00 -> Friday


def _config(tmp_path, **overrides):
    values = dict(
        client_id="c",
        client_secret="s",
        on_behalf_of_cpf="12345678901",
        dry_run=False,
        email_recipients="team@example.com",
        db_path=tmp_path / "state.sqlite",
    )
    values.update(overrides)
    return Config(**values)


def test_healthy_after_a_recent_successful_run(tmp_path):
    config = _config(tmp_path)
    state = State(config.db_path)
    state.record_run(success=True, listed=0, new=0, alert_sent=False, dry_run=False)
    state.close()
    text, code = report(config, now=datetime.now())
    assert code == 0 and "HEALTHY" in text


def test_attention_when_the_last_run_failed(tmp_path):
    config = _config(tmp_path)
    state = State(config.db_path)
    state.record_run(success=False, error="simulated HTTP 500")
    state.close()
    text, code = report(config)
    assert code == 1 and "FAILED" in text and "simulated HTTP 500" in text


def test_attention_without_database_or_runs(tmp_path):
    text, code = report(_config(tmp_path))
    assert code == 1 and "no sweep has run" in text


def test_attention_with_dry_run_on(tmp_path):
    config = _config(tmp_path, dry_run=True)
    state = State(config.db_path)
    state.record_run(success=True, listed=0, new=0, alert_sent=False, dry_run=True)
    state.close()
    text, code = report(config)
    assert code == 1 and "DRY_RUN" in text


def test_demo_mode_does_not_need_credentials(tmp_path):
    config = _config(tmp_path, client_id="", client_secret="", on_behalf_of_cpf="", demo_mode=True)
    state = State(config.db_path)
    state.record_run(success=True, listed=6, new=6, alert_sent=True, dry_run=False)
    state.close()
    text, code = report(config, now=datetime.now())
    assert code == 0 and "DEMO_MODE" in text
