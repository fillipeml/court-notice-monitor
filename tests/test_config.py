import os

import pytest

from notice_monitor.config import BASE_URLS, ClientAccount, Config, load_dotenv


def _clear(monkeypatch, *keys):
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_filled_value_beats_empty_placeholder(tmp_path, monkeypatch):
    """A block pasted below the template must not be cancelled by the empty key at the top."""
    _clear(monkeypatch, "PDPJ_CLIENT_ID", "PDPJ_CLIENT_SECRET")
    env = tmp_path / ".env"
    env.write_text(
        "# template\nPDPJ_CLIENT_ID=\nPDPJ_CLIENT_SECRET=\n\n"
        "# pasted later\nPDPJ_CLIENT_ID=abc123\nPDPJ_CLIENT_SECRET=secret\n",
        encoding="utf-8",
    )
    load_dotenv(env)
    assert os.environ["PDPJ_CLIENT_ID"] == "abc123"
    assert os.environ["PDPJ_CLIENT_SECRET"] == "secret"


def test_quotes_and_bom_are_tolerated(tmp_path, monkeypatch):
    _clear(monkeypatch, "PDPJ_TENANT_ID")
    env = tmp_path / ".env"
    env.write_text('﻿PDPJ_TENANT_ID="uuid-with-quotes"\n', encoding="utf-8")
    load_dotenv(env)
    assert os.environ["PDPJ_TENANT_ID"] == "uuid-with-quotes"


def test_process_environment_wins_over_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PDPJ_CLIENT_ID", "from-process")
    env = tmp_path / ".env"
    env.write_text("PDPJ_CLIENT_ID=from-file\n", encoding="utf-8")
    load_dotenv(env)
    assert os.environ["PDPJ_CLIENT_ID"] == "from-process"


def test_malformed_cpf_is_rejected(monkeypatch):
    monkeypatch.setenv("PDPJ_ON_BEHALF_OF_CPF", "123.456.789-00")
    monkeypatch.setenv("PDPJ_ENVIRONMENT", "staging")
    with pytest.raises(ValueError, match="11 digits"):
        Config.from_env(dotenv=None)


def test_production_uses_verified_defaults(monkeypatch):
    monkeypatch.setenv("PDPJ_ENVIRONMENT", "production")
    monkeypatch.setenv("PDPJ_BASE_URL_PRODUCTION", "")
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    config = Config.from_env(dotenv=None)
    assert config.base_url == BASE_URLS["production"]
    assert "sso.cloud.pje.jus.br" in config.token_url  # production SSO, not staging
    assert str(config.db_path).replace("\\", "/") == "data/state.sqlite"


def test_demo_mode_defaults_to_a_demo_database(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("PDPJ_ENVIRONMENT", raising=False)
    config = Config.from_env(dotenv=None)
    assert config.demo_mode is True
    assert str(config.db_path).replace("\\", "/") == ".demo/state.sqlite"


def test_require_credentials_lists_what_is_missing():
    config = Config(client_id="x", client_secret="y", on_behalf_of_cpf="")
    with pytest.raises(ValueError, match="PDPJ_ON_BEHALF_OF_CPF"):
        config.require_credentials()


def test_with_account_swaps_credential_and_keeps_environment():
    base = Config(
        client_id="main-id",
        client_secret="main-secret",
        tenant_id="t-main",
        on_behalf_of_cpf="12345678901",
        environment="production",
        base_url="https://example/api",
    )
    account = ClientAccount(name="ALFA LTDA.", client_id="cli-id", client_secret="cli-secret")
    derived = base.with_account(account)
    assert derived.client_id == "cli-id"
    assert derived.tenant_id == ""  # resolved through /eu for that account
    assert derived.on_behalf_of_cpf == "12345678901"  # audit id stays the same
    assert derived.base_url == base.base_url
    assert derived.client_accounts == []  # no recursion
    assert base.client_id == "main-id"  # original untouched
