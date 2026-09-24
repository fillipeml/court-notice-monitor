import pytest

from notice_monitor.config import Config
from notice_monitor.mail import GraphMailer, MailError, OutboxMailer


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}
        self.text = str(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "login.microsoftonline.com" in url:
            return FakeResponse(200, {"access_token": "tok", "expires_in": 3600})
        return FakeResponse(202)


def _config():
    return Config(
        graph_tenant_id="t",
        graph_client_id="c",
        graph_client_secret="s",
        email_sender="notices@example.com",
        email_recipients="a@example.com, b@example.com",
    )


def test_graph_payload_is_built_correctly():
    session = FakeSession()
    GraphMailer(_config(), session).send("Subject", "Body", ["a@x.com", " b@x.com "])
    url, kwargs = session.calls[-1]
    assert url.endswith("/users/notices@example.com/sendMail")
    message = kwargs["json"]["message"]
    assert message["subject"] == "Subject"
    assert [r["emailAddress"]["address"] for r in message["toRecipients"]] == ["a@x.com", "b@x.com"]
    assert kwargs["headers"]["Authorization"] == "Bearer tok"


def test_graph_token_is_cached():
    session = FakeSession()
    mailer = GraphMailer(_config(), session)
    mailer.send("A", "B", ["a@x.com"])
    mailer.send("C", "D", ["a@x.com"])
    assert sum(1 for u, _ in session.calls if "login.microsoftonline" in u) == 1


def test_graph_refuses_without_recipients():
    with pytest.raises(MailError, match="recipients"):
        GraphMailer(_config(), FakeSession()).send("A", "B", [])


def test_graph_error_becomes_mail_error():
    class ErrorSession(FakeSession):
        def post(self, url, **kwargs):
            if "login" in url:
                return super().post(url, **kwargs)
            return FakeResponse(403, {"error": "denied"})

    with pytest.raises(MailError, match="403"):
        GraphMailer(_config(), ErrorSession()).send("A", "B", ["a@x.com"])


def test_outbox_writes_one_file_per_message(tmp_path):
    mailer = OutboxMailer(tmp_path / "outbox")
    mailer.send("[URGENT] Judicial Domicile", "line one\nline two", ["team@example.com"])
    files = list((tmp_path / "outbox").glob("*.eml"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert text.startswith("To: team@example.com\nSubject: [URGENT] Judicial Domicile\n\nline one")
    with pytest.raises(MailError):
        mailer.send("x", "y", [])
