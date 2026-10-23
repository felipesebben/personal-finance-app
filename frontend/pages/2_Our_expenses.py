"""
Our expenses: how the household's shared spending is doing. This month
day by day against earlier months, month by month, a monthly recap to
review together, the joint account (when there is one) and who owes whom.
"""
import streamlit as st

import ui
from common import get_data, my_user_id, require_login, show_toast
from sections import daily, joint, overview, recap, settle

ui.setup("Our expenses")
token = require_login()
show_toast()

ui.page_header("Our expenses", "How our shared spending is doing this month, against earlier months.")

payment_methods = get_data("payment_methods", token)
household = get_data("household_settings", token)
has_joint = joint.available(payment_methods, household, my_user_id(household))

names = ["This month", "Month by month", "Monthly recap", *(["Joint account"] if has_joint else []), "Settle up"]
tabs = dict(zip(names, st.tabs(names)))

with tabs["This month"]:
    daily.render(token, lens="Household", key="our")
with tabs["Month by month"]:
    overview.render(token, lens="Household", key="our")
with tabs["Monthly recap"]:
    recap.render(token)
if has_joint:
    with tabs["Joint account"]:
        joint.render(token)
with tabs["Settle up"]:
    settle.render(token)
