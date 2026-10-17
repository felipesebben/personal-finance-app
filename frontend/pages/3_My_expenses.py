"""
My expenses: how my own spending is doing. This month day by day and the
same over time, each with a Show switch (everything I spent = my share of
shared + my personal expenses, personal only, or my share of shared), and
every entry I can see. Nothing here shows a partner's personal spending.
"""
import streamlit as st

import ui
from common import require_login, show_toast
from sections import daily, history, overview

ui.setup("My expenses")
token = require_login()
show_toast()

ui.page_header("My expenses", "How your own spending is doing: your part of what you share, plus what's only yours.")

month_tab, trend_tab, entries_tab = st.tabs(["This month", "Over time", "My entries"])

with month_tab:
    daily.render(token, lens="My share", key="mine", show_view=True)
with trend_tab:
    overview.render(token, lens="My share", key="mine", show_view=True)
with entries_tab:
    history.render(token)
