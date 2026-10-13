"""The joint account: what's left, the spending pace, deposits and balance checks."""
from __future__ import annotations

import datetime

import pandas as pd
import requests
import streamlit as st

import analytics_charts
import joint_shaping
import ui
from common import SAO_PAULO, auth_headers, get_data, md, saved, today_brl
from config import API_BASE_URL
from money import format_brl, format_brl_delta, parse_brl


def available(payment_methods, household_data, my_user_id) -> bool:
    """Shown once a payment method is ticked Joint, to household members (the pot is the household's)."""
    in_household = any(m["user_id"] == my_user_id for m in household_data or [])
    return in_household and any(m.get("is_joint") for m in payment_methods or [])


def render(token: str) -> None:
    ui.lede(
        "What's left in the account you both top up, and whether it's going faster than usual.",
        " Spending is whatever you log with the joint card; add money here when you top it up.",
    )
    statuses = get_data("joint/status", token) or []
    if len(statuses) > 1:
        labels = {s["label"]: s for s in statuses}
        status = labels[st.selectbox("Account", list(labels), key="joint_account_pick")]
    elif statuses:
        status = statuses[0]
    else:
        return

    def record(kind, amount, on_day, note):
        now_brl = datetime.datetime.now(SAO_PAULO)
        payload = {
            "payment_method_id": status["payment_method_id"],
            "kind": kind,
            "amount": str(amount),
            "entry_at": datetime.datetime.combine(on_day, now_brl.time(), tzinfo=SAO_PAULO).isoformat(),
            "note": note or None,
        }
        res = requests.post(f"{API_BASE_URL}/joint/entries", json=payload, headers=auth_headers(token))
        if res.status_code == 200:
            saved(f"{'Deposit recorded' if kind == 'deposit' else 'Balance updated'}: {format_brl(amount)}")
        else:
            st.error(f"Error: {res.status_code} – {res.json().get('detail', res.text)}")

    gap = joint_shaping.pace_gap(status)
    j1, j2, j3 = st.columns(3)
    with j1:
        st.metric("Left in the account",
                  format_brl(status["balance"]) if status["balance"] is not None else "–", border=True)
        st.caption(md(joint_shaping.counted_from_text(status, SAO_PAULO)))
    with j2:
        st.metric("Spent this month", format_brl(status["spent_to_day"]),
                  delta=f"{format_brl_delta(gap)} vs usual" if gap is not None else None,
                  delta_color="inverse", border=True)
        usual_total = status.get("usual_month_total")
        st.caption(md(f"A usual month: {format_brl(usual_total)}." if usual_total is not None
                      else "No usual month yet."))
    with j3:
        runs_out = status.get("runs_out_on")
        st.metric("Runs out", datetime.date.fromisoformat(runs_out).strftime("%d/%m") if runs_out else "–",
                  border=True)
        st.caption(md(joint_shaping.run_out_text(status) or "Needs the balance first."))

    st.subheader("Spending through the month")
    st.caption(md(joint_shaping.pace_sentence(status)))
    frame = joint_shaping.pace_frame(status)
    if not frame.empty:
        st.altair_chart(
            analytics_charts.joint_pace_chart(frame, joint_shaping.THIS_MONTH, joint_shaping.USUAL,
                                              status["days_in_month"]),
            use_container_width=True,
        )

    st.subheader("Add money or correct the balance")
    with st.form("joint_entry_form", clear_on_submit=True, border=True):
        kind = st.radio(
            "What happened?", ["deposit", "balance"], horizontal=True, key="joint_kind",
            format_func=lambda k: "Money went in" if k == "deposit" else "The bank shows this balance",
            help="Use the balance option the first time, and whenever the app drifts from what your bank "
                 "shows (e.g. a purchase nobody logged).",
        )
        e1, e2 = st.columns(2)
        amount_text = e1.text_input("Amount (R$)", placeholder="e.g. 1.500,00", key="joint_amount")
        on_day = e2.date_input("Date", today_brl(), format="DD/MM/YYYY", key="joint_date")
        note = st.text_input("Note (optional)", key="joint_note")
        if st.form_submit_button("Save", type="primary"):
            try:
                amount = parse_brl(amount_text)
            except ValueError as e:
                st.error(str(e))
            else:
                record(kind, amount, on_day, note)

    entries = get_data(f"joint/entries?payment_method_id={status['payment_method_id']}", token) or []
    if entries:
        st.subheader("Recent entries")
        shown = entries[:20]
        entries_df = pd.DataFrame({
            "Date": [pd.Timestamp(e["entry_at"]).tz_convert(SAO_PAULO).strftime("%d/%m/%Y") for e in shown],
            "What": ["Deposit" if e["kind"] == "deposit" else "Balance check" for e in shown],
            "Amount": [format_brl(e["amount"]) for e in shown],
            "Note": [e.get("note") or "" for e in shown],
        })
        st.dataframe(entries_df, width="stretch", hide_index=True)
        with st.expander("Remove an entry"):
            by_label = {
                f"{row.Date} · {row.What} · {row.Amount}": e["joint_entry_id"]
                for row, e in zip(entries_df.itertuples(), shown)
            }
            pick = st.selectbox("Entry", list(by_label), index=None, key="joint_remove_pick")
            if st.button("Remove", disabled=pick is None, key="joint_remove"):
                res = requests.delete(f"{API_BASE_URL}/joint/entries/{by_label[pick]}", headers=auth_headers(token))
                if res.status_code == 200:
                    saved("Entry removed")
                else:
                    st.error(f"Error: {res.status_code} – {res.json().get('detail', res.text)}")
