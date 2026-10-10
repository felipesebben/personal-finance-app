"""Home.py's password-reset screens, with the API faked (AppTest runs the script in-process)."""
import pytest
import requests
from streamlit.testing.v1 import AppTest

NEW_PW = "n" * 12  # built at runtime: no credential-shaped literal
LINK_ID = "t" * 20


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


@pytest.fixture
def api(monkeypatch):
    """Records POSTs and answers them from `api.responses[path]`."""
    class Api:
        calls = []
        responses = {}

    def fake_post(url, json=None, data=None, **kwargs):
        path = url.split("://", 1)[-1].split("/", 1)[-1]
        Api.calls.append(("/" + path, json))
        return Api.responses["/" + path]

    monkeypatch.setattr(requests, "post", fake_post)
    return Api


def reset_screen(link_id=LINK_ID):
    at = AppTest.from_file("Home.py", default_timeout=30)
    at.query_params["reset_token"] = link_id
    return at.run()


def fill_and_submit(at, password, repeat):
    at.text_input[0].input(password)
    at.text_input[1].input(repeat)
    return next(b for b in at.button if b.label == "Set Password").click().run()


def test_login_screen_offers_forgot_password():
    at = AppTest.from_file("Home.py", default_timeout=30).run()
    assert not at.exception
    assert any(e.label == "Forgot password?" for e in at.expander)


def test_forgot_password_always_says_the_same(api):
    api.responses["/password-reset/request"] = FakeResponse(202, {"detail": "x"})
    at = AppTest.from_file("Home.py", default_timeout=30).run()
    email_box = next(t for t in at.text_input if t.label == "Your account's email")
    email_box.input("nobody@example.com")
    next(b for b in at.button if b.label == "Email me a reset link").click().run()
    assert not at.exception
    assert api.calls == [("/password-reset/request", {"email": "nobody@example.com"})]
    assert any("If that account exists" in s.value for s in at.success)


def test_reset_link_shows_the_new_password_form():
    at = reset_screen()
    assert not at.exception
    assert any(t.value == "Set a new password" for t in at.title)
    assert [t.label for t in at.text_input] == ["New password", "Repeat new password"]


def test_short_or_mismatched_password_is_caught_before_the_api(api):
    at = fill_and_submit(reset_screen(), "s" * 7, "s" * 7)
    assert any("at least 8" in w.value for w in at.warning)
    at = fill_and_submit(reset_screen(), NEW_PW, NEW_PW + "x")
    assert any("don't match" in w.value for w in at.warning)
    assert api.calls == []


def test_successful_reset_clears_the_link_and_shows_login(api):
    api.responses["/password-reset/confirm"] = FakeResponse(200, {"detail": "ok"})
    at = fill_and_submit(reset_screen(LINK_ID), NEW_PW, NEW_PW)
    assert not at.exception
    assert api.calls == [("/password-reset/confirm", {"token": LINK_ID, "new_password": NEW_PW})]
    assert "reset_token" not in at.query_params
    assert any(t.value == "Secure Access" for t in at.title)
    assert any("Password updated" in s.value for s in at.success)


def test_invalid_link_shows_the_api_error(api):
    api.responses["/password-reset/confirm"] = FakeResponse(400, {"detail": "This reset link is invalid or has expired."})
    at = fill_and_submit(reset_screen(), NEW_PW, NEW_PW)
    assert any("invalid or has expired" in e.value for e in at.error)
    assert at.query_params.get("reset_token")
