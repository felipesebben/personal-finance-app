"""
My expenses: how my own spending is doing. This month day by day and the
same over time, each with a Show switch (everything I spent = my share of
shared + my personal expenses, personal only, or my share of shared).
Every entry I can see is on the Entries page. Nothing here shows a
partner's personal spending.
"""
import streamlit as st

import ui
from common import require_login, show_toast
from sections import daily, overview

ui.setup("My expenses")
token = require_login()
show_toast()

ui.page_header("My expenses", "How your own spending is doing: your part of what you share, plus what's only yours.")

month_tab, trend_tab = st.tabs(["This month", "Over time"])

with month_tab:
    daily.render(token, lens="My share", key="mine", show_view=True)
with trend_tab:
    overview.render(token, lens="My share", key="mine", show_view=True)
st.page_link("pages/4_Entries.py", label="Check or fix what was logged", icon=":material/fact_check:")
