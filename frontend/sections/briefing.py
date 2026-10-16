"""The login briefing on Home: how this month is going, in a few lines."""
from __future__ import annotations

import datetime
from urllib.parse import urlencode

import streamlit as st

import analytics_shaping as shape
import briefing
from common import SAO_PAULO, get_data, md, my_user_id


def render(token: str) -> None:
    month = datetime.datetime.now(SAO_PAULO).strftime("%Y-%m")
    # Four months: this one plus the three that make "usual".
    query = urlencode({"month": month, "months": 4})
    shared = get_data(f"analytics/shared?{query}", token) or None
    personal = get_data(f"analytics/personal?{query}", token) or None
    household = get_data("household_settings", token) or []
    me = my_user_id(household)
    in_household = any(m["user_id"] == me for m in household)

    lines = []
    if shared:
        lines.append(briefing.spending_line("Shared", shape.to_frame(shared), shared, "Household", top_category=True))
    payloads = [p for p in (shared, personal) if p]
    if payloads:
        # Mine = my share of shared + my personal: the same window, rows added together.
        mine = dict(payloads[0], rows=[row for p in payloads for row in p["rows"]])
        lines.append(briefing.spending_line("Yours", shape.to_frame(mine), mine, "My share"))
    if in_household:
        lines.append(briefing.settle_line(get_data(f"balances/?month={month}", token), me, briefing.month_name(month)))
        lines.extend(briefing.joint_lines(get_data("joint/status", token)))
    lines = [line for line in lines if line]

    if not lines:
        return
    with st.container(border=True):
        st.markdown("**This month so far**")
        st.markdown("\n".join(f"- {md(line)}" for line in lines))
        st.caption("Usual = the average of your last three months over the same days.")
