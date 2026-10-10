"""
Sending email, behind a tiny interface so the API never talks to SMTP directly.

- ConsoleSender (the default, EMAIL_BACKEND=console) prints each message to
  the backend log. Dev, tests and CI use it, so nothing needs SMTP
  credentials; in dev, `docker compose logs backend` shows the reset link.
- SmtpSender (EMAIL_BACKEND=smtp) sends for real over STARTTLS, e.g. through
  Gmail with an App Password.

Routes take the sender through the `get_email_sender` dependency, which tests
override with a fake that records what would have been sent.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from config import settings

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleSender:
    """Prints the message instead of sending it."""

    def send(self, to: str, subject: str, body: str) -> None:
        print(f"--- email (console backend) ---\nTo: {to}\nSubject: {subject}\n\n{body}\n--- end email ---", flush=True)


class SmtpSender:
    """Sends through an SMTP server with STARTTLS (Gmail: smtp.gmail.com:587)."""

    def __init__(self, host: str, port: int, user: str, password: str, from_addr: str):
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.from_addr = from_addr

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(self.user, self.password)
            smtp.send_message(msg)


def get_email_sender() -> EmailSender:
    """FastAPI dependency: the sender EMAIL_BACKEND selects."""
    if settings.email_backend == "smtp":
        settings.require_email()
        return SmtpSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_password.get_secret_value(),
            from_addr=settings.email_from,
        )
    return ConsoleSender()


def send_quietly(sender: EmailSender, to: str, subject: str, body: str) -> None:
    """
    Sends, logging rather than raising on failure. Runs as a background task
    after the response has gone out, so there is no client left to tell; the
    log is where a wrong App Password shows up.
    """
    try:
        sender.send(to, subject, body)
    except Exception:
        logger.exception("Failed to send email to %s", to)
