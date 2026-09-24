import json

import pytest

from notice_monitor.config import ClientAccount


def test_load_valid_file(tmp_path):
    path = tmp_path / "client_accounts.json"
    path.write_text(
        json.dumps(
            [
                {
                    "name": "ALFA LTDA.",
                    "client_id": "abc",
                    "client_secret": "xyz",
                    "tenant_id": "11111111-1111-1111-1111-111111111111",
                }
            ]
        ),
        encoding="utf-8",
    )
    accounts = ClientAccount.load_file(path)
    assert len(accounts) == 1 and accounts[0].name == "ALFA LTDA."
    assert accounts[0].tenant_id.startswith("1111")


def test_missing_file_means_primary_account_only(tmp_path):
    assert ClientAccount.load_file(tmp_path / "missing.json") == []


def test_missing_required_field_is_rejected(tmp_path):
    path = tmp_path / "client_accounts.json"
    path.write_text(
        json.dumps([{"name": "X", "client_id": "abc", "client_secret": ""}]), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="client_secret"):
        ClientAccount.load_file(path)


def test_invalid_json_is_reported_with_the_file_name(tmp_path):
    path = tmp_path / "client_accounts.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="client_accounts.json"):
        ClientAccount.load_file(path)
