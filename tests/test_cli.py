from pathlib import Path

from notice_monitor.cli import main

ROOT = Path(__file__).resolve().parents[1]


def _demo_env(monkeypatch, tmp_path, dry_run="false"):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DRY_RUN", dry_run)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "state.sqlite"))
    monkeypatch.setenv("FIXTURES_PATH", str(ROOT / "fixtures" / "notices.json"))
    monkeypatch.setenv("OUTBOX_DIR", str(tmp_path / "outbox"))
    monkeypatch.setenv("EMAIL_RECIPIENTS", "team@example.com")
    for key in ("PDPJ_CLIENT_ID", "PDPJ_CLIENT_SECRET", "PDPJ_ON_BEHALF_OF_CPF", "PDPJ_TENANT_ID"):
        monkeypatch.delenv(key, raising=False)


def test_demo_sweep_end_to_end(monkeypatch, tmp_path, capsys):
    _demo_env(monkeypatch, tmp_path)
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "Environment: DEMO" in out and "new: 6" in out and "alert_sent: True" in out
    assert len(list((tmp_path / "outbox").glob("*.eml"))) == 1

    assert main(["--health"]) == 0
    assert "HEALTHY" in capsys.readouterr().out

    assert main([]) == 0
    assert "new: 0" in capsys.readouterr().out


def test_me_and_diagnose_in_demo_mode(monkeypatch, tmp_path, capsys):
    _demo_env(monkeypatch, tmp_path)
    assert main(["--me"]) == 0
    assert "tenantId" in capsys.readouterr().out
    assert main(["--diagnose"]) == 0
    assert "ready to sweep" in capsys.readouterr().out


def test_sample_in_demo_mode(monkeypatch, tmp_path, capsys):
    _demo_env(monkeypatch, tmp_path)
    assert main(["--sample", "3"]) == 0
    assert "Sample saved" in capsys.readouterr().out
    assert (tmp_path / "sample-staging.json").exists()


def test_live_mode_refuses_without_credentials(monkeypatch, tmp_path):
    _demo_env(monkeypatch, tmp_path)
    monkeypatch.setenv("DEMO_MODE", "false")
    import pytest

    with pytest.raises(ValueError, match="PDPJ_CLIENT_ID"):
        main([])
