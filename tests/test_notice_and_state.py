from datetime import date

from _ids import case_number

from notice_monitor.notice import Notice
from notice_monitor.state import State
from notice_monitor.triage import AUTOMATED, HUMAN

RAW = {
    "numeroComunicacao": "COM-001",
    "numeroProcesso": case_number(1),
    "tipoComunicacao": "citacao",
    "status": "EM_CURSO",
    "dataComunicacao": "2026-08-27T10:00:00",
    "dataFinalCiencia": "2026-09-01",
    "tribunalOrigem": "TJ-EX",
    "urgente": "N",
    "autoresReclamantes": [{"nome": "ALFA LTDA."}],
    "reus": [{"nome": "DEMO COMPANY LTDA"}, "OUTRA RE S.A."],
}


def test_notice_is_built_once_at_the_boundary():
    n = Notice.from_api(RAW)
    assert n.id == "COM-001" and n.type == "CITACAO" and n.acknowledge_by == "2026-09-01"
    assert n.claimants == ["ALFA LTDA."] and n.defendants == ["DEMO COMPANY LTDA", "OUTRA RE S.A."]
    assert n.parties() == "ALFA LTDA. v DEMO COMPANY LTDA, OUTRA RE S.A."
    assert n.urgent is False


def test_parties_fallbacks():
    assert Notice.from_api({"nomeDestinatario": "COMPANY X"}).parties() == "COMPANY X"
    assert Notice.from_api({}).parties() == "parties not given"
    assert (
        Notice.from_api({"autoresReclamantes": ["JOAO"], "reus": []}).parties()
        == "JOAO v defendant not given"
    )


def test_deadline_within_days():
    n = Notice.from_api(RAW)
    assert n.deadline_within(1, today=date(2026, 8, 31)) is True
    assert n.deadline_within(1, today=date(2026, 8, 20)) is False
    assert Notice.from_api({**RAW, "dataFinalCiencia": None}).deadline_within(30) is False
    assert Notice.from_api({**RAW, "dataFinalCiencia": "not a date"}).deadline_within(30) is False


def test_state_is_idempotent(tmp_path):
    state = State(tmp_path / "state.sqlite")
    n = Notice.from_api(RAW)
    assert state.record(n, AUTOMATED, "primary") is True
    assert state.record(n, AUTOMATED, "primary") is False  # duplicate
    assert state.summary() == {AUTOMATED: 1}
    state.close()


def test_missing_id_gets_a_stable_synthetic_key(tmp_path):
    state = State(tmp_path / "state.sqlite")
    n = Notice.from_api({**RAW, "numeroComunicacao": None})
    assert n.key("primary").startswith("NO-ID/primary/")
    assert state.record(n, HUMAN, "primary") is True
    assert state.record(n, HUMAN, "primary") is False
    state.close()


def test_mark_alerted_and_accounts(tmp_path):
    state = State(tmp_path / "state.sqlite")
    n = Notice.from_api(RAW)
    state.record(n, AUTOMATED, "Alfa Ltda.")
    assert state.alerted_at(n.key("Alfa Ltda.")) is None
    state.mark_alerted([n.key("Alfa Ltda.")])
    assert state.alerted_at(n.key("Alfa Ltda.")) is not None
    assert state.account_of(n.key("Alfa Ltda.")) == "Alfa Ltda."
    state.close()


def test_runs_history(tmp_path):
    state = State(tmp_path / "state.sqlite")
    state.record_run(success=True, listed=3, new=1, alert_sent=False, dry_run=True)
    state.record_run(success=False, error="HTTP 500")
    runs = state.recent_runs(5)
    assert [r["success"] for r in runs] == [0, 1]
    assert runs[0]["error"] == "HTTP 500"
    state.close()
