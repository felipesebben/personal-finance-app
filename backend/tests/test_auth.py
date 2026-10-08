"""The auth boundary: which routes demand a token, and login behaviour."""
import pytest

from conftest import signup_and_login

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
