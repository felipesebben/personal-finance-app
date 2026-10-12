"""Settle up: who owes whom for a period, and recording the payment."""
from __future__ import annotations

import datetime
from decimal import Decimal

import pandas as pd
import requests
import streamlit as st

import ui
from common import SAO_PAULO, auth_headers, get_data, md, month_options, period_label, saved, today_brl
from config import API_BASE_URL
from money import format_brl, parse_brl


def render(token: str) -> None:
    ui.lede(
        "Who owes whom, and recording the payment.",
        " Compares what each of you paid for shared expenses with what the household ratio says "
        "you should have paid, minus payments already recorded. The joint account never counts: "
        "you've both already paid into it.",
    )
    selected_period = st.selectbox(
        "Period", options=month_options(include_all_time=True), index=0,
        format_func=period_label, key="settle_tab_period",
        help="Usually the month you're squaring up. “All time” is the running balance across every month.",
    )
    label = period_label(selected_period)
    balance_endpoint = "balances/" if selected_period == "All time" else f"balances/?month={selected_period}"
    balance_report = get_data(balance_endpoint, token)
    if not balance_report:
        return

    if balance_report["transfers"]:
        for t in balance_report["transfers"]:
            ui.callout(f"{t['from_name']} owes {t['to_name']}", format_brl(t["amount"]),
                       f"for {label} · after payments already recorded")
    else:
        ui.callout("All square", "", f"Nobody owes anything for {label}.")

    balance_df = pd.DataFrame(balance_report["members"])
    if not balance_df.empty:
        st.subheader("How we got there")
        st.caption(
            "**Paid**: what went out of each person's account for shared expenses. "
            "**Should have paid**: their share by the household ratio. "
            "**Difference**: paid − should have paid + paid back − received; "
            "positive means the others owe this person."
        )
        money_cols = {
            "paid": "Paid", "borne": "Should have paid",
            "settled_out": "Paid back", "settled_in": "Received", "net": "Difference",
        }
        for col in money_cols:
            balance_df[col] = balance_df[col].map(format_brl)
        st.dataframe(
            balance_df[["full_name", *money_cols]].rename(columns={"full_name": "Person", **money_cols}),
            width="stretch", hide_index=True,
        )

    members = {m["user_id"]: m["full_name"] for m in balance_report["members"]}
    suggestion = balance_report["transfers"][0] if balance_report["transfers"] else None
    squares_up = "the running all-time balance" if selected_period == "All time" else label
    month_value = None if selected_period == "All time" else selected_period
    today = today_brl()

    def record_settlement(from_id, to_id, amount, paid_on, note):
        now_brl = datetime.datetime.now(SAO_PAULO)
        payload = {
            "settled_at": datetime.datetime.combine(paid_on, now_brl.time(), tzinfo=SAO_PAULO).isoformat(),
            "from_user_id": from_id,
            "to_user_id": to_id,
            "amount": str(amount),
            "month": month_value,
            "note": note or None,
        }
        res = requests.post(f"{API_BASE_URL}/settlements/", json=payload, headers=auth_headers(token))
        if res.status_code == 200:
            saved(f"Payment recorded: {format_brl(amount)}")
        else:
            st.error(f"Error: {res.status_code} – {res.json().get('detail', res.text)}")

    if suggestion:
        owed = Decimal(str(suggestion["amount"]))
        with st.popover(f"Record {suggestion['from_name']}'s payment of {format_brl(owed)}", icon=":material/payments:"):
            st.write(
                f"{suggestion['from_name']} paid {suggestion['to_name']} **{md(format_brl(owed))}**, "
                f"squaring up {squares_up}."
            )
            quick_date = st.date_input("Paid on", today, format="DD/MM/YYYY", key="quick_paid_on")
            quick_note = st.text_input("Note (optional)", placeholder="e.g. Pix transfer", key="quick_note")
            if st.button("Confirm payment", type="primary", key="quick_confirm"):
                record_settlement(suggestion["from_user_id"], suggestion["to_user_id"], owed, quick_date, quick_note)

    if len(members) >= 2:
        with st.expander("Record a different payment (partial amount, other direction)"):
            st.caption(f"Squares up **{squares_up}**.")
            member_ids = list(members)
            with st.form("settlement_form", clear_on_submit=True):
                f1, f2 = st.columns(2)
                from_id = f1.selectbox(
                    "From", member_ids, format_func=members.get,
                    index=member_ids.index(suggestion["from_user_id"]) if suggestion else 0,
                )
                to_id = f2.selectbox(
                    "To", member_ids, format_func=members.get,
                    index=member_ids.index(suggestion["to_user_id"]) if suggestion else 1,
                )
                f3, f4 = st.columns(2)
                amount_text = f3.text_input(
                    "Amount (R$)", placeholder="0,00",
                    value=format_brl(suggestion["amount"], symbol=False) if suggestion else "",
                )
                paid_on = f4.date_input("Paid on", today, format="DD/MM/YYYY")
                note = st.text_input("Note (optional)", placeholder="e.g. Pix transfer")

                if st.form_submit_button("Record payment", type="primary"):
                    try:
                        amount, amount_error = parse_brl(amount_text), None
                    except ValueError as e:
                        amount, amount_error = None, str(e)
                    if from_id == to_id:
                        st.error("From and To must be different people.")
                    elif amount_error:
                        st.error(f"Amount: {amount_error}")
                    else:
                        record_settlement(from_id, to_id, amount, paid_on, note)

    # --- Past payments for this period ---
    settlements_endpoint = "settlements/" if selected_period == "All time" else f"settlements/?month={selected_period}"
    settlements = get_data(settlements_endpoint, token)
    if settlements:
        with st.expander(f"Payments recorded for {label} ({len(settlements)})"):
            st_df = pd.DataFrame(settlements)
            st_df["amount"] = st_df["amount"].map(format_brl)
            st_df["settled_at"] = pd.to_datetime(st_df["settled_at"], utc=True).dt.tz_convert(SAO_PAULO)
            st.dataframe(
                st_df.assign(settled_at=st_df["settled_at"].dt.strftime("%d/%m/%Y"))[
                    ["settled_at", "from_name", "to_name", "amount", "month", "note"]
                ].rename(columns={
                    "settled_at": "Paid on", "from_name": "From", "to_name": "To",
                    "amount": "Amount", "month": "For month", "note": "Note",
                }),
                width="stretch", hide_index=True,
            )
            labels = {
                row["settlement_id"]: f"{row['settled_at'].strftime('%d/%m')} – {row['from_name']} → {row['to_name']} {row['amount']}"
                for _, row in st_df.iterrows()
            }
            target = st.selectbox("Remove a payment entered by mistake:", options=list(labels),
                                  format_func=labels.get, index=None)
            if st.button("Delete payment") and target:
                res = requests.delete(f"{API_BASE_URL}/settlements/{target}", headers=auth_headers(token))
                if res.status_code == 200:
                    saved("Payment removed.")
                else:
                    st.error(f"Error: {res.status_code} – {res.json().get('detail', res.text)}")
