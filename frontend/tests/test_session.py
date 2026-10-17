"""
The session: renewed while the app is used, and an expiry (any 401) goes
back to the login form on Home with one message, from any page.
"""
import time
from unittest.mock import MagicMock, patch

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from common import EXPIRED_MESSAGE, RENEW_AFTER_SECONDS, RENEWED_KEY

ME = "me@example.com"


def response(payload, status_code=200):
    r = MagicMock(status_code=status_code)
    r.json.return_value = payload
    return r


@pytest.fixture(autouse=True)
def fresh_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def logged_in(renewed_ago=0.0):
    at = AppTest.from_file("Home.py", default_timeout=30)
    at.session_state["access_token"] = "old-token"
    at.session_state["user_email"] = ME
    at.session_state[RENEWED_KEY] = time.time() - renewed_ago
    return at


def shows_login_form(at):
    return any(b.label == "Log In" for b in at.button) and not any(b.label == "Log Out" for b in at.button)


def test_an_expired_session_on_home_shows_the_login_form_once():
    at = logged_in()
    with patch("requests.get", return_value=response({"detail": "Could not validate credentials"}, 401)), \
            patch("requests.post"):
        at.run()
    assert not at.exception
    assert shows_login_form(at)
    assert [i.value for i in at.info] == [EXPIRED_MESSAGE]
    assert not at.error
    assert at.session_state["access_token"] is None


@pytest.mark.parametrize("page", ["pages/2_Our_expenses.py", "pages/3_My_expenses.py", "pages/5_Settings.py"])
def test_an_expired_session_on_any_page_goes_back_to_login(page):
    at = logged_in()
    with patch("requests.get", return_value=response([])), patch("requests.post"):
        at.run()
    at.switch_page(page)
    with patch("requests.get", return_value=response({"detail": "expired"}, 401)), patch("requests.post"):
        at.run()
    assert not at.exception
    assert shows_login_form(at)
    assert [i.value for i in at.info] == [EXPIRED_MESSAGE]


def test_using_the_app_renews_an_old_token():
    at = logged_in(renewed_ago=RENEW_AFTER_SECONDS + 60)
    fresh = "new-token"
    with patch("requests.get", return_value=response([])), \
            patch("requests.post", return_value=response(dict(access_token=fresh))) as post:
        at.run()
    assert not at.exception
    assert post.call_args.args[0].endswith("/token/refresh")
    assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer old-token"}
    assert at.session_state["access_token"] == "new-token"
    assert time.time() - at.session_state[RENEWED_KEY] < 5


def test_a_recent_token_is_not_renewed():
    at = logged_in(renewed_ago=10)
    with patch("requests.get", return_value=response([])), patch("requests.post") as post:
        at.run()
    post.assert_not_called()
    assert at.session_state["access_token"] == "old-token"


def test_a_token_too_old_to_renew_logs_out():
    at = logged_in(renewed_ago=RENEW_AFTER_SECONDS + 60)
    with patch("requests.get", return_value=response([])), \
            patch("requests.post", return_value=response({"detail": "expired"}, 401)):
        at.run()
    assert shows_login_form(at)
    assert [i.value for i in at.info] == [EXPIRED_MESSAGE]


def test_logging_out_says_nothing_about_expiry():
    at = logged_in()
    with patch("requests.get", return_value=response([])), patch("requests.post"):
        at.run()
        at.button(key="main_logout").click().run()
        # AppTest keeps the elements of a run that st.rerun() cut short; settle it.
        at.run()
    assert shows_login_form(at)
    assert not at.info
