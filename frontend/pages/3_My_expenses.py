"""
My expenses: how my own spending is doing. This month (my share of
shared plus my personal expenses), my share of shared over time, and
every entry I can see. Nothing here shows a partner's personal spending.
"""
import streamlit as st

import ui
from common import require_login, show_toast
from sections import history, my_month, overview

ui.setup("My expenses")
token = require_login()
show_toast()

ui.page_header("My expenses", "How your own spending is doing: your part of what you share, plus what's only yours.")

month_tab, trend_tab, entries_tab = st.tabs(["This month", "My share over time", "My entries"])

with month_tab:
    my_month.render(token)
with trend_tab:
    overview.render(token, lens="My share", key="mine")
with entries_tab:
    history.render(token)
