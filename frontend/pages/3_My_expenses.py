"""
My expenses: how my own spending is doing. This month (my share of
shared plus my personal expenses), the same over time, and every entry I
can see. Nothing here shows a partner's personal spending.
"""
import streamlit as st

import ui
from common import require_login, show_toast
from sections import history, my_month, overview

# What "Over time" can show: everything I spent, or one half of it.
VIEWS = {
    "all": "Everything I spent",
    "personal": "Personal only",
    "shared": "My share of shared",
}

ui.setup("My expenses")
token = require_login()
show_toast()

ui.page_header("My expenses", "How your own spending is doing: your part of what you share, plus what's only yours.")

month_tab, trend_tab, entries_tab = st.tabs(["This month", "Over time", "My entries"])

with month_tab:
    my_month.render(token)
with trend_tab:
    # Set through session state (not `default=`) so a test can preset it.
    st.session_state.setdefault("mine_view", "all")
    view = st.segmented_control(
        "Show", list(VIEWS), format_func=VIEWS.get, key="mine_view",
        help="Everything I spent = my share of shared expenses + my personal ones.",
    ) or "all"
    overview.render(token, lens="My share", key="mine", scope=view)
with entries_tab:
    history.render(token)
