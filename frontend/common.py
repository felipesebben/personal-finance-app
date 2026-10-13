"""
Helpers every page shares: the login check, cached API reads, the
post-save toast and the month pickers. Sections in `sections/` and the
pages under `pages/` import from here rather than each defining their own.
"""
from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

import requests
import streamlit as st

from config import API_BASE_URL

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
TOAST_KEY = "tracker_toast"


def md(text: str) -> str:
    """Escapes "$" for Markdown elements, where a pair of them starts LaTeX ("R$ 1 · R$ 2")."""
    return text.replace("$", "\\$")


def require_login() -> str:
    """The session's token, or stop the page with a pointer to Home."""
    token = st.session_state.get("access_token")
    if not token:
        st.error("You are not logged in.")
        st.info("Please go to the **Home** page to log in.")
        st.stop()
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
def get_data(endpoint: str, token: str):
    """
    GET from the API, cached per token (so per session). Returns [] after
    showing an error, so callers can treat "nothing" and "failed" alike.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}", headers=auth_headers(token))
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            st.error("Session Expired. Please log in again.")
            return []
        else:
            st.error(f"Failed to fetch {endpoint}. Status code: {response.status_code}")
            return []
    except requests.exceptions.ConnectionError:
        st.error(f"Connection Error: Could not connect to the API to fetch {endpoint}.")
        return []


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
