"""
Settle up: who owes whom for a period, and recording the payment.

The answer first (who owes whom), then the action in the payer's own voice:
one button that settles it all ("I paid Felipe R$ 447,53") and, right
under it, a different amount. How it was worked out, other payments and
the payments recorded come after. `settle_box` (the answer and the
action) is shared with the monthly recap.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pandas as pd
import requests
import streamlit as st

import ui
from common import (
    SAO_PAULO, auth_headers, check, get_data, month_options, my_user_id, period_label, saved, today_brl,
)
from config import API_BASE_URL
from money import format_brl, parse_brl


def net_text(net) -> str:
    """'Is owed R$ 120,00', 'Owes R$ 120,00' or 'Square'."""
    value = Decimal(str(net))
    if value == 0:
        return "Square"
    return f"{'Is owed' if value > 0 else 'Owes'} {format_brl(abs(value))}"


def person_lines(m: dict) -> list[tuple[str, None]]:
    """What a person paid, their share, and any payments between you, as ui.kpi lines."""
    lines = [(f"Paid {format_brl(m['paid'])}", None), (f"Their share {format_brl(m['borne'])}", None)]
    if Decimal(str(m.get("settled_out") or 0)):
        lines.append((f"Paid back {format_brl(m['settled_out'])}", None))
    if Decimal(str(m.get("settled_in") or 0)):
        lines.append((f"Received {format_brl(m['settled_in'])}", None))
    return lines


def action_labels(transfer: dict, me: int | None) -> dict:
    """
    The settle buttons' words, from the point of view of whoever is
    looking: the one who owes says "I paid Felipe R$ 447,53", the one owed
    "Lívia paid me R$ 447,53", anyone else "Lívia paid Felipe R$ 447,53".
    Returns {all, other}: the button for the whole amount, and the one for
    a different amount.
    """
    amount = format_brl(transfer["amount"])
    payer, payee = transfer["from_name"], transfer["to_name"]
    if me == transfer["from_user_id"]:
        return {"all": f"I paid {payee} {amount}", "other": f"I paid {payee} a different amount"}
    if me == transfer["to_user_id"]:
        return {"all": f"{payer} paid me {amount}", "other": f"{payer} paid me a different amount"}
    return {"all": f"{payer} paid {payee} {amount}", "other": f"{payer} paid {payee} a different amount"}


def record_settlement(token: str, from_id: int, to_id: int, amount, paid_on: datetime.date, note: str | None,
                      month: str | None) -> None:
    """POST the payment (squaring up `month`, or the all-time balance for None); a toast and a rerun on success."""
    now_brl = datetime.datetime.now(SAO_PAULO)
    payload = {
        "settled_at": datetime.datetime.combine(paid_on, now_brl.time(), tzinfo=SAO_PAULO).isoformat(),
        "from_user_id": from_id,
        "to_user_id": to_id,
        "amount": str(amount),
        "month": month,
        "note": note or None,
    }
    res = check(requests.post(f"{API_BASE_URL}/settlements/", json=payload, headers=auth_headers(token)))
    if res.status_code == 200:
        saved(f"Payment recorded: {format_brl(amount)}. Made a mistake? Remove it under Payments recorded.")
    else:
        st.error(f"Error: {res.status_code} – {res.json().get('detail', res.text)}")


def settle_box(token: str, period: str, key: str) -> dict | None:
    """
    Who owes whom for `period` ("YYYY-MM" or "All time") and, for each
    debt, the action: one button for the whole amount and a field for a
    different one, in the viewer's own voice. Returns the balance report.
    """
    label = period_label(period)
    report = get_data("balances/" if period == "All time" else f"balances/?month={period}", token)
    if not report:
        return None
    transfers = report["transfers"]
    if not transfers:
        ui.callout("All square", "", f"Nobody owes anything for {label}.")
        return report
    me = my_user_id(get_data("household_settings", token))
    month = None if period == "All time" else period
    for i, t in enumerate(transfers):
        ui.callout(f"{t['from_name']} owes {t['to_name']}", format_brl(t["amount"]),
                   f"for {label} · after payments already recorded")
        words = action_labels(t, me)
        if st.button(words["all"], type="primary", icon=":material/check_circle:", width="stretch",
                     key=f"{key}_all_{i}", help=f"Records it as paid today, squaring up {label}."):
            record_settlement(token, t["from_user_id"], t["to_user_id"], Decimal(str(t["amount"])), today_brl(),
                              None, month)
        amount_col, button_col = st.columns([2, 3], vertical_alignment="bottom")
        other = amount_col.text_input("Amount (R$)", placeholder="0,00", key=f"{key}_amount_{i}")
        if button_col.button(words["other"], key=f"{key}_other_{i}", width="stretch"):
            try:
                amount = parse_brl(other)
            except ValueError as e:
                st.error(f"Amount: {e}")
            else:
                record_settlement(token, t["from_user_id"], t["to_user_id"], amount, today_brl(), None, month)
    return report


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
    balance_report = settle_box(token, selected_period, "settle")
    if not balance_report:
        return

    people = balance_report["members"]
    if people:
        st.subheader("How we got there")
        for col, m in zip(st.columns(max(len(people), 2), gap="small"), people):
            with col, ui.card(f"settle_{m['user_id']}"):
                ui.kpi(m["full_name"] or "—", net_text(m["net"]), person_lines(m),
                       help="Paid: what went out of their account for shared expenses. Their share: what the "
                            "household ratio puts on them. The difference, after payments, is what they're owed "
                            "(or owe).")

    members = {m["user_id"]: m["full_name"] for m in balance_report["members"]}
    suggestion = balance_report["transfers"][0] if balance_report["transfers"] else None
    squares_up = "the running all-time balance" if selected_period == "All time" else label
    month_value = None if selected_period == "All time" else selected_period
    today = today_brl()

    if len(members) >= 2:
        with st.expander("Another payment (other direction, another day, a note)"):
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
                        record_settlement(token, from_id, to_id, amount, paid_on, note, month_value)

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
                res = check(requests.delete(f"{API_BASE_URL}/settlements/{target}", headers=auth_headers(token)))
                if res.status_code == 200:
                    saved("Payment removed.")
                else:
                    st.error(f"Error: {res.status_code} – {res.json().get('detail', res.text)}")
