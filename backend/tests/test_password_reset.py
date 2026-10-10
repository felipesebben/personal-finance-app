"""Password reset by email: request, confirm, and the CLI fallback."""
import re

import pytest
from sqlalchemy import text

import database
from auth import hash_reset_token
from conftest import signup_and_login
from email_sender import get_email_sender

# Built at runtime rather than written as literals, so secret scanners
# don't mistake test values for leaked credentials.
NEW_PW = "n" * 12
OTHER_PW = "o" * 12
GENERIC = "If that account exists, we've sent a reset link."


class FakeSender:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append({"to": to, "subject": subject, "body": body})

    def last_token(self):
        return re.search(r"reset_token=(\S+)", self.sent[-1]["body"]).group(1)


@pytest.fixture
def outbox(client):
    from main import app
    sender = FakeSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    yield sender
    app.dependency_overrides.pop(get_email_sender, None)


def request_reset(client, email):
    return client.post("/password-reset/request", json={"email": email})


def confirm(client, raw, new_password=NEW_PW):
    return client.post("/password-reset/confirm", json={"token": raw, "new_password": new_password})


def can_log_in(client, email, pw):
    return client.post("/token", data={"username": email, "password": pw}).status_code == 200


def token_rows():
    with database.engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(
            "SELECT * FROM password_reset_token ORDER BY id"
        )).mappings().all()]


# --- request -------------------------------------------------------------

def test_known_and_unknown_email_get_the_same_response(client, outbox):
    signup_and_login(client, "alice")
    known = request_reset(client, "alice@example.com")
    unknown = request_reset(client, "nobody@example.com")
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == {"detail": GENERIC}
    # Only the real account got an email.
    assert [m["to"] for m in outbox.sent] == ["alice@example.com"]


def test_request_is_case_insensitive(client, outbox):
    signup_and_login(client, "alice")
    request_reset(client, "  ALICE@Example.com ")
    assert [m["to"] for m in outbox.sent] == ["alice@example.com"]


def test_link_points_at_the_frontend(client, outbox, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "frontend_base_url", "http://192.168.0.10:8501/")
    signup_and_login(client, "alice")
    request_reset(client, "alice@example.com")
    assert f"http://192.168.0.10:8501/?reset_token={outbox.last_token()}" in outbox.sent[-1]["body"]


def test_only_the_hash_is_stored(client, outbox):
    signup_and_login(client, "alice")
    request_reset(client, "alice@example.com")
    raw = outbox.last_token()
    [row] = token_rows()
    assert row["token_hash"] == hash_reset_token(raw)
    assert len(row["token_hash"]) == 64
    assert raw not in {str(v) for v in row.values()}
    assert row["used_at"] is None and row["expires_at"] > row["created_at"]


def test_rate_limit_stops_sending_after_three_an_hour(client, outbox):
    signup_and_login(client, "alice")
    responses = [request_reset(client, "alice@example.com") for _ in range(5)]
    assert all(r.status_code == 202 and r.json() == {"detail": GENERIC} for r in responses)
    assert len(outbox.sent) == 3
    assert len(token_rows()) == 3


# --- confirm -------------------------------------------------------------

def test_reset_changes_the_password(client, outbox):
    signup_and_login(client, "alice")
    request_reset(client, "alice@example.com")
    resp = confirm(client, outbox.last_token())
    assert resp.status_code == 200, resp.text
    assert not can_log_in(client, "alice@example.com", "pw")
    assert can_log_in(client, "alice@example.com", NEW_PW)


def test_a_token_works_only_once(client, outbox):
    signup_and_login(client, "alice")
    request_reset(client, "alice@example.com")
    raw = outbox.last_token()
    assert confirm(client, raw).status_code == 200
    second = confirm(client, raw, OTHER_PW)
    assert second.status_code == 400
    assert second.json()["detail"] == "This reset link is invalid or has expired."
    assert can_log_in(client, "alice@example.com", NEW_PW)


def test_expired_token_is_rejected(client, outbox):
    signup_and_login(client, "alice")
    request_reset(client, "alice@example.com")
    with database.engine.begin() as conn:
        conn.execute(text("UPDATE password_reset_token SET expires_at = now() - interval '1 minute'"))
    assert confirm(client, outbox.last_token()).status_code == 400
    assert can_log_in(client, "alice@example.com", "pw")


def test_new_request_invalidates_the_previous_link(client, outbox):
    signup_and_login(client, "alice")
    request_reset(client, "alice@example.com")
    first = outbox.last_token()
    request_reset(client, "alice@example.com")
    second = outbox.last_token()
    assert first != second
    assert confirm(client, first).status_code == 400
    assert confirm(client, second).status_code == 200


def test_unknown_token_is_rejected(client):
    assert confirm(client, "not-a-real-reset-link").status_code == 400


def test_short_password_is_a_422(client, outbox):
    signup_and_login(client, "alice")
    request_reset(client, "alice@example.com")
    assert confirm(client, outbox.last_token(), "s" * 7).status_code == 422
    # The token wasn't spent by the failed attempt.
    assert confirm(client, outbox.last_token()).status_code == 200


def test_deleting_a_user_deletes_their_tokens(client, outbox):
    a_id, a_headers = signup_and_login(client, "alice")
    request_reset(client, "alice@example.com")
    assert client.delete(f"/users/{a_id}", headers=a_headers).status_code == 200
    assert token_rows() == []


# --- CLI fallback --------------------------------------------------------

def test_cli_sets_the_password_and_retires_links(client, outbox):
    from reset_password import set_password
    signup_and_login(client, "alice")
    request_reset(client, "alice@example.com")
    with database.SessionLocal() as db:
        assert set_password(db, "Alice@Example.com", NEW_PW) is True
    assert can_log_in(client, "alice@example.com", NEW_PW)
    assert confirm(client, outbox.last_token(), OTHER_PW).status_code == 400


def test_cli_reports_unknown_email_and_short_password(client):
    from reset_password import set_password
    signup_and_login(client, "alice")
    with database.SessionLocal() as db:
        assert set_password(db, "nobody@example.com", NEW_PW) is False
        with pytest.raises(ValueError):
            set_password(db, "alice@example.com", "s" * 7)
    assert can_log_in(client, "alice@example.com", "pw")
