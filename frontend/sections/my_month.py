"""My month: what I spent (my share of shared + my personal), by category and cost type."""
from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

import ui
from common import get_data, md, month_options, period_label
from money import format_brl, format_brl_delta


def render(token: str) -> None:
    ui.lede(
        "Your spending this month, at a glance.",
        " “You spent” is your part of shared expenses plus your personal ones. "
        "Your personal expenses are only ever shown to you.",
    )
    selected_month = st.selectbox(
        "Month", options=month_options(include_all_time=False), index=0,
        format_func=period_label, key="month_tab_period",
    )
    summary = get_data(f"summary/?month={selected_month}", token)
    if not summary:
        return
    me = summary["me"]
    previous = period_label(summary["previous_month"])

    def change(now, before):
        return f"{format_brl_delta(Decimal(now) - Decimal(before))} vs {previous}"

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("You spent", format_brl(me["total"]), delta=change(me["total"], me["previous_total"]),
                  delta_color="inverse", border=True)
        st.caption("Your share of shared expenses + your personal ones.")
    with m2:
        st.metric("Your share of shared", format_brl(me["shared_share"]), border=True)
        st.caption("Your part of what you both share.")
    with m3:
        st.metric("Personal", format_brl(me["personal"]), border=True)
        st.caption("Only yours; your partner never sees these.")
    st.caption("▲ means more than the previous month, ▼ less.")

    if not summary["by_category"]:
        st.info("Nothing logged for this month yet.")
        st.page_link("pages/1_Add_expense.py", label="Add an expense", icon=":material/edit_note:")
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Where your money went")
        st.caption("Your part of each category this month, biggest first.")
        cat_df = pd.DataFrame(summary["by_category"]).rename(columns={"label": "Category", "amount": "Amount"})
        cat_df["Amount"] = pd.to_numeric(cat_df["Amount"])
        st.bar_chart(cat_df, x="Category", y="Amount", horizontal=True, sort="-Amount")
    with c2:
        st.subheader("Fixed vs variable")
        st.caption("Fixed costs repeat every month (rent, internet); variable ones change.")
        ct_df = pd.DataFrame(summary["by_cost_type"]).rename(columns={"label": "Cost type", "amount": "Amount"})
        amounts = pd.to_numeric(ct_df["Amount"])
        total = amounts.sum()
        ct_df["Share"] = amounts / total * 100 if total else 0
        # Pre-formatted text: NumberColumn can't put a comma before the cents.
        ct_df["Amount"] = ct_df["Amount"].map(format_brl)
        st.dataframe(
            ct_df, width="stretch", hide_index=True,
            column_config={
                "Share": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
            },
        )
    st.caption(md(f"Shared by the household this month: {format_brl(summary['household_shared']['total'])} "
                  "(see Our expenses)."))
