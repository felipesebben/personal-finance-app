"""The auth boundary: which routes demand a token, and login behaviour."""
import pytest

from conftest import expenditure_payload, signup_and_login

PROTECTED_ROUTES = [
    ("get", "/users/"),
    ("get", "/categories/"),
    ("post", "/categories/"),
    ("delete", "/categories/1"),
    ("get", "/payment_methods/"),
    ("post", "/payment_methods/"),
    ("delete", "/payment_methods/1"),
    ("delete", "/users/1"),
    ("get", "/household_settings/"),
    ("put", "/household_settings/"),
    ("get", "/balances/"),
    ("get", "/summary/"),
    ("get", "/settlements/"),
    ("post", "/settlements/"),
    ("delete", "/settlements/1"),
    ("get", "/expenditures/"),
    ("post", "/expenditures/"),
    ("delete", "/expenditures/1"),
    ("post", "/refresh"),
]


@pytest.mark.parametrize("method, path", PROTECTED_ROUTES)
def test_protected_routes_reject_missing_token(client, method, path):
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize("method, path", PROTECTED_ROUTES)
def test_protected_routes_reject_garbage_token(client, method, path):
    headers = {"Authorization": "Bearer not-a-real-token"}
    assert getattr(client, method)(path, headers=headers).status_code == 401


def test_signup_and_login(client):
    _, headers = signup_and_login(client, "alice")
    assert client.get("/users/", headers=headers).status_code == 200


def test_wrong_password_is_rejected(client):
    signup_and_login(client, "alice")
    resp = client.post("/token", data={"username": "alice@example.com", "password": "nope"})
    assert resp.status_code == 401


def test_duplicate_signup_is_a_400(client):
    signup_and_login(client, "alice")
    resp = client.post("/users/", json={"full_name": "x", "email": "alice@example.com", "password": "pw"})
    assert resp.status_code == 400


def test_login_does_not_print_the_email(client, capsys):
    signup_and_login(client, "alice")
    assert "alice@example.com" not in capsys.readouterr().out


# --- deleting accounts ----------------------------------------------------

def test_cannot_delete_another_user(client):
    a_id, _ = signup_and_login(client, "alice")
    _, b_headers = signup_and_login(client, "bob")
    assert client.delete(f"/users/{a_id}", headers=b_headers).status_code == 403
    # Alice is still there and can still log in.
    assert client.post("/token", data={"username": "alice@example.com", "password": "pw"}).status_code == 200


def test_can_delete_yourself(client):
    a_id, a_headers = signup_and_login(client, "alice")
    assert client.delete(f"/users/{a_id}", headers=a_headers).status_code == 200
    assert client.post("/token", data={"username": "alice@example.com", "password": "pw"}).status_code == 401


def test_deleting_yourself_with_expenses_is_a_400(client, household):
    resp = client.post("/expenditures/", headers=household["a"], json=expenditure_payload(household))
    assert resp.status_code == 200, resp.text
    assert client.delete(f"/users/{household['a_id']}", headers=household["a"]).status_code == 400


# --- signup allowlist -----------------------------------------------------

@pytest.fixture
def allowlist(monkeypatch):
    """Sets ALLOWED_SIGNUP_EMAILS on the already-built settings, parsed as at startup."""
    from config import Settings, settings

    def set_list(raw):
        monkeypatch.setattr(settings, "allowed_signup_emails", Settings.parse_email_list(raw))
    return set_list


def signup(client, email):
    return client.post("/users/", json={"full_name": "x", "email": email, "password": "pw"})


def test_empty_allowlist_keeps_signup_open(client, allowlist):
    allowlist("")
    assert signup(client, "anyone@example.com").status_code == 200


def test_allowlist_blocks_unlisted_email(client, allowlist):
    allowlist("alice@example.com, bob@example.com")
    resp = signup(client, "mallory@example.com")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Sign-up is restricted on this installation"


def test_allowlist_is_case_insensitive(client, allowlist):
    allowlist(" Alice@Example.com ,bob@example.com")
    assert signup(client, "ALICE@example.COM").status_code == 200
    assert signup(client, "bob@example.com").status_code == 200
