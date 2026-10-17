"""
Helpers every page shares: the session (login check, renewal, logging
out on expiry), cached API reads, the post-save toast and the month
pickers. Sections in `sections/` and the pages under `pages/` import from
here rather than each defining their own.

The session is an inactivity timeout: the API's token lasts
ACCESS_TOKEN_EXPIRE_MINUTES, and keep_alive() swaps it for a fresh one
(POST /token/refresh) whenever the app is used and the token is more than
RENEW_AFTER_SECONDS old. Any 401 means it has expired: end_session()
clears everything and goes back to the login form on Home, with one
message saying why.
"""
from __future__ import annotations

import datetime
import time
from zoneinfo import ZoneInfo

import requests
import streamlit as st

from config import API_BASE_URL

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
TOAST_KEY = "tracker_toast"
RENEWED_KEY = "token_renewed_at"    # when the current token was issued, time.time()
LOGOUT_MESSAGE_KEY = "logout_message"  # shown once on the login form
RENEW_AFTER_SECONDS = 5 * 60
EXPIRED_MESSAGE = "You were logged out because the app wasn't used for a while. Please log in again."


def md(text: str) -> str:
    """Escapes "$" for Markdown elements, where a pair of them starts LaTeX ("R$ 1 · R$ 2")."""
    return text.replace("$", "\\$")


class ApiError(Exception):
    """A non-200 answer; raised (not returned) so st.cache_data never keeps it."""

    def __init__(self, status_code: int):
        super().__init__(status_code)
        self.status_code = status_code


def start_session(token: str, email: str) -> None:
    """After a successful login."""
    st.session_state.clear()
    st.session_state["access_token"] = token
    st.session_state["user_email"] = email
    st.session_state[RENEWED_KEY] = time.time()


def _go_home() -> None:
    try:
        st.switch_page("Home.py")
    except st.errors.StreamlitAPIException:
        # Not running as the multipage app (e.g. a page opened on its own).
        st.info("Please go to the **Home** page to log in.")
        st.stop()


def end_session(message: str | None = EXPIRED_MESSAGE) -> None:
    """Forget the login and every page's state, then show the login form on Home."""
    st.session_state.clear()
    st.session_state["access_token"] = None
    if message:
        st.session_state[LOGOUT_MESSAGE_KEY] = message
    st.cache_data.clear()
    _go_home()


def check(response):
    """Pass a mutation's response through: a 401 ends the session."""
    if response is not None and response.status_code == 401:
        end_session()
    return response


def keep_alive() -> str | None:
    """
    The session's token, renewed when it's older than RENEW_AFTER_SECONDS.
    Every page calls it (through require_login), so using the app keeps
    you logged in; an expired token can't be renewed and ends the session.
    """
    token = st.session_state.get("access_token")
    if not token:
        return None
    renewed = st.session_state.get(RENEWED_KEY)
    if renewed is None:
        # A session from before renewal existed: start counting now; a 401 still ends it.
        st.session_state[RENEWED_KEY] = time.time()
        return token
    if time.time() - renewed < RENEW_AFTER_SECONDS:
        return token
    try:
        response = requests.post(f"{API_BASE_URL}/token/refresh", headers=auth_headers(token))
    except requests.exceptions.RequestException:
        return token  # try again on the next run
    check(response)
    if response.status_code == 200:
        token = response.json().get("access_token") or token
        st.session_state["access_token"] = token
        st.session_state[RENEWED_KEY] = time.time()
    return token


def require_login() -> str:
    """The session's (renewed) token; without one, back to the login form on Home."""
    token = keep_alive()
    if not token:
        _go_home()
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def show_toast() -> None:
    """
    A save reruns the page straight away, so anything shown before st.rerun()
    is lost; its confirmation is stashed in session_state and shown here.
    """
    if TOAST_KEY in st.session_state:
        st.toast(md(st.session_state.pop(TOAST_KEY)), icon="✅")


def saved(message: str) -> None:
    """After a successful write: queue the toast, drop cached reads, rerun."""
    st.session_state[TOAST_KEY] = message
    st.cache_data.clear()
    st.rerun()


@st.cache_data(ttl=60)
def _cached_get(endpoint: str, token: str):
    response = requests.get(f"{API_BASE_URL}/{endpoint}", headers=auth_headers(token))
    if response.status_code != 200:
        raise ApiError(response.status_code)
    return response.json()


def get_data(endpoint: str, token: str, default=None):
    """
    GET from the API, cached per token (so per session). On failure it shows
    an error and returns `default` ([] unless given), so callers can treat
    "nothing" and "failed" alike; a 401 ends the session instead.
    """
    default = [] if default is None else default
    try:
        return _cached_get(endpoint, token)
    except ApiError as e:
        if e.status_code == 401:
            end_session()
        st.error(f"Failed to fetch {endpoint.split('?')[0]}. Status code: {e.status_code}")
    except requests.exceptions.ConnectionError:
        st.error(f"Connection Error: Could not connect to the API to fetch {endpoint.split('?')[0]}.")
    return default


def my_user_id(household_data) -> int | None:
    """The logged-in person's id, matched by the email Home.py keeps at login."""
    email = (st.session_state.get("user_email") or "").strip().lower()
    return next(
        (m["user_id"] for m in household_data or [] if (m["user"].get("email") or "").lower() == email),
        None,
    )


def today_brl() -> datetime.date:
    return datetime.datetime.now(SAO_PAULO).date()


def month_options(include_all_time: bool) -> list[str]:
    """The last 12 São Paulo months, newest first, optionally plus "All time"."""
    today = today_brl()
    options, y, m = [], today.year, today.month
    for _ in range(12):
        options.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return options + (["All time"] if include_all_time else [])


def period_label(period: str) -> str:
    return period if period == "All time" else datetime.date(int(period[:4]), int(period[5:]), 1).strftime("%B %Y")
