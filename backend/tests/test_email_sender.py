"""email_sender: picking a backend, and what SmtpSender says to the server."""
import pytest
from pydantic import SecretStr

import email_sender
from config import settings
from email_sender import ConsoleSender, SmtpSender, get_email_sender, send_quietly


def test_console_is_the_default(capsys):
    sender = get_email_sender()
    assert isinstance(sender, ConsoleSender)
    sender.send("a@example.com", "Hello", "the body")
    out = capsys.readouterr().out
    assert "a@example.com" in out and "Hello" in out and "the body" in out


def test_smtp_backend_with_missing_settings_names_them(monkeypatch):
    monkeypatch.setattr(settings, "email_backend", "smtp")
    monkeypatch.setattr(settings, "smtp_user", None)
    monkeypatch.setattr(settings, "smtp_password", None)
    monkeypatch.setattr(settings, "email_from", None)
    with pytest.raises(ValueError, match="SMTP_USER.*SMTP_PASSWORD.*EMAIL_FROM"):
        get_email_sender()


def test_smtp_sender_uses_starttls_and_logs_in(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            calls.append(("quit",))

        def starttls(self, context):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user, password))

        def send_message(self, msg):
            calls.append(("send", msg["From"], msg["To"], msg["Subject"], msg.get_content().strip()))

    monkeypatch.setattr(email_sender.smtplib, "SMTP", FakeSMTP)
    app_pw = "x" * 16  # built at runtime: no credential-shaped literal
    monkeypatch.setattr(settings, "email_backend", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "mail.example.test")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "me@example.com")
    monkeypatch.setattr(settings, "smtp_password", SecretStr(app_pw))
    monkeypatch.setattr(settings, "email_from", "Finance <me@example.com>")

    sender = get_email_sender()
    assert isinstance(sender, SmtpSender)
    sender.send("you@example.com", "Subject line", "Body text")

    assert calls == [
        ("connect", "mail.example.test", 587),
        ("starttls",),
        ("login", "me@example.com", app_pw),
        ("send", "Finance <me@example.com>", "you@example.com", "Subject line", "Body text"),
        ("quit",),
    ]


def test_send_quietly_logs_instead_of_raising(caplog, monkeypatch):
    # The test session's alembic run applies alembic.ini's logging config,
    # which disables loggers created before it; re-enable ours.
    monkeypatch.setattr(email_sender.logger, "disabled", False)

    class Broken:
        def send(self, to, subject, body):
            raise OSError("smtp down")

    send_quietly(Broken(), "a@example.com", "s", "b")
    assert "Failed to send email to a@example.com" in caplog.text
