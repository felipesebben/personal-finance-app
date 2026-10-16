"""
Spending over time: KPIs against earlier months, the monthly trend,
categories, a heatmap, a drill-down and fixed vs variable.

`scope` picks the expenses: "shared" (/analytics/shared), "personal"
(/analytics/personal, only the caller's own) or "all" (both, i.e. my share
of shared plus my personal spending). `lens` picks the amount: "Household"
(full prices, on Our expenses) or "My share" (the caller's part). Data
shaping lives in analytics_shaping, the Altair specs in analytics_charts.
"""
from __future__ import annotations

import datetime
from urllib.parse import urlencode

import pandas as pd
import requests
import streamlit as st

import analytics_charts as charts
import analytics_shaping as shape
from common import SAO_PAULO, auth_headers
from config import API_BASE_URL
from money import format_brl

# scope -> (endpoints, what the rows are called)
SCOPES = {
    "shared": (["analytics/shared"], "shared expenses"),
    "personal": (["analytics/personal"], "personal expenses"),
    "all": (["analytics/shared", "analytics/personal"], "expenses"),
}
BASIS = "Purchase month · São Paulo time."


@st.cache_data(ttl=60)
def fetch(endpoint: str, token: str):
    """GET from the API; None (with a message) on failure."""
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}", headers=auth_headers(token))
    except requests.exceptions.ConnectionError:
        st.error("Connection Error: Could not connect to the API.")
        return None
    if response.status_code == 200:
        return response.json()
    if response.status_code == 401:
        st.error("Session Expired. Please log in again.")
    else:
        st.error(f"Failed to fetch {endpoint.split('?')[0]}. Status code: {response.status_code}")
    return None


def metric_delta(change: float, pct: float):
    """st.metric delta text and colour; spending up is bad, so colours are inverted."""
    if round(change, 2) == 0:
        return "no change", "off"
    return shape.delta_text(change, pct), "inverse"


def money_table(frame: pd.DataFrame, columns: dict[str, str]) -> pd.DataFrame:
    """Selects and renames columns, formatting amounts as BRL text."""
    out = frame[list(columns)].rename(columns=columns)
    for name in out.columns:
        if pd.api.types.is_float_dtype(out[name]):
            out[name] = out[name].map(format_brl)
    return out


def changes_table(comparison: pd.DataFrame, by: str, label: str, previous_title: str) -> pd.DataFrame:
    table = shape.biggest_changes(comparison, by)
    table["change_pct"] = table["pct"].map(shape.pct_text)
    table["change"] = table["change"].map(shape.signed_brl)
    return money_table(table, {
        by: label, "current": "This month", "previous": previous_title,
        "change": "Change", "change_pct": "Change %",
    })


def fetch_window(endpoints: list[str], selected: str, token: str):
    """One /analytics payload, or several merged (same window, rows added together); None on failure."""
    payloads = [fetch(f"{e}?{urlencode({'month': selected, 'months': 12})}", token) for e in endpoints]
    if any(p is None for p in payloads):
        return None
    merged = dict(payloads[0])
    merged["rows"] = [row for p in payloads for row in p["rows"]]
    return merged


def fetch_items(endpoints: list[str], selected: str, category: str, token: str):
    """The expenses behind one category and month, newest first across every endpoint; None on failure."""
    lists = [fetch(f"{e}/expenses?{urlencode({'month': selected, 'primary_category': category})}", token)
             for e in endpoints]
    if any(items is None for items in lists):
        return None
    return sorted((i for items in lists for i in items), key=lambda i: i["transaction_timestamp"], reverse=True)


def render(token: str, lens: str, key: str, scope: str = "shared") -> None:
    """The whole overview for one lens and scope. `key` prefixes widget keys so each page keeps its own picks."""
    endpoints, noun = SCOPES[scope]
    current_month = datetime.datetime.now(SAO_PAULO).strftime("%Y-%m")

    # Defaults go through session state (not `default=`) so a test can
    # preset them without Streamlit warning about both.
    st.session_state.setdefault(f"{key}_window", 12)
    c1, c2 = st.columns(2, vertical_alignment="bottom")
    selected = c1.selectbox(
        "Month", shape.month_options(current_month, 12),
        format_func=shape.month_label, key=f"{key}_month",
    )
    window = c2.segmented_control(
        "Trend window", [6, 12], key=f"{key}_window",
        format_func=lambda n: f"{n} months",
    ) or 12

    # Always fetch 12 months: the 6-month view and the 3-month average both fit inside.
    data = fetch_window(endpoints, selected, token)
    if data is None:
        return

    df = shape.to_frame(data)
    months = data["months"]
    is_partial = data["is_partial"]
    as_of_day = data["as_of_day"]
    previous = shape.shift_month(selected, -1)
    selected_label = shape.month_label(selected)
    previous_title = f"{shape.month_label(previous, short=True)} (days 1–{as_of_day})" if is_partial else shape.month_label(previous, short=True)
    to_date = " to date" if is_partial else ""
    household = lens == "Household"
    explains = {
        "shared": ("Full price of each shared expense, whoever paid." if household
                   else "Your share of each shared expense."),
        "personal": "Your personal expenses, only ever shown to you.",
        "all": "Your share of shared expenses plus your personal ones.",
    }
    headline = {"shared": "Shared total" if household else "My share", "personal": "Personal", "all": "I spent"}[scope]

    st.caption(
        f"{BASIS} {explains[scope]}"
        + (f" {selected_label} is in progress, so it's compared with days 1–{as_of_day} of other months." if is_partial else "")
    )

    if df.empty:
        st.info(f"No {noun} in the 12 months up to {selected_label}. Log one to see this overview.")
        st.page_link("pages/1_Add_expense.py", label="Add an expense", icon=":material/edit_note:")
        return

    # --- KPIs ---
    total = shape.compare_total(df, selected, is_partial, lens)
    average = shape.previous_full_average(df, months, selected, lens, to_day=is_partial)
    comparison = shape.compare(df, selected, is_partial, lens)
    rising = shape.biggest_increase(comparison)

    k1, k2, k3, k4 = st.columns(4)
    delta, colour = metric_delta(total["change"], total["pct"])
    k1.metric(
        f"{headline} · {shape.month_label(selected, short=True)}{to_date}",
        format_brl(total["current"]), delta=delta, delta_color=colour, border=True,
        help=f"Against {format_brl(total['previous'])} in {previous_title}.",
    )
    if average is None:
        k2.metric("vs 3-month average", "—", border=True,
                  help=f"Needs three full months of {noun} before this month.")
    else:
        change = round(total["current"] - average, 2)
        delta, colour = metric_delta(change, change / average if average else float("nan"))
        k2.metric(
            "vs 3-month average" + (" (same days)" if is_partial else ""), format_brl(average),
            delta=delta, delta_color=colour, border=True,
            help="Average of the three months before this one" + (f", days 1–{as_of_day} only." if is_partial else "."),
        )
    k3.metric(f"{noun.capitalize()}{to_date}", shape.expense_count(df, selected), border=True,
              help=f"{shape.expense_count(df, previous)} in all of {shape.month_label(previous)}.")
    if rising is None:
        k4.metric("Biggest increase", "—", border=True, help=f"No category rose against {previous_title}.")
    else:
        row = comparison.set_index("primary_category").loc[rising]
        k4.metric("Biggest increase", rising, delta=shape.delta_text(row["change"], row["pct"]),
                  delta_color="inverse", border=True, help=f"Against {previous_title}.")

    # --- Trend ---
    st.subheader("Monthly trend")
    trend_months = months[-window:]
    totals = shape.monthly_totals(df, trend_months, lens)
    trend_average = shape.previous_full_average(df, months, selected, lens)
    st.altair_chart(charts.trend_chart(totals, selected, is_partial, trend_average), use_container_width=True)
    st.caption(
        ("Faded bar: month in progress, no projection. " if is_partial else "")
        + ("Dashed line: average of the three full months before the selected one." if trend_average is not None
           else "The 3-month average line appears once three full months of history exist.")
    )

    # --- Where is it going ---
    st.subheader("Where we're spending more" if household
                 else "Where my share is going" if scope == "shared" else "Where my money is going")
    st.caption(f"{selected_label}{to_date} by category, largest first. Grey tick: {previous_title}.")
    if comparison.empty:
        st.info(f"No {noun} in {selected_label} or {shape.month_label(previous)}.")
    else:
        left, right = st.columns([3, 2])
        left.altair_chart(charts.comparison_bars(comparison, "primary_category", previous_title), use_container_width=True)
        with right:
            st.markdown("**Biggest changes**")
            st.dataframe(changes_table(comparison, "primary_category", "Category", previous_title), hide_index=True)

    # --- Heatmap ---
    st.subheader("Category by month")
    st.caption("Darker cells are bigger months for that category.")
    st.altair_chart(charts.heatmap_chart(shape.heatmap_frame(df, trend_months, lens), trend_months), use_container_width=True)

    # --- Drill-down ---
    st.subheader("Drill down")
    categories = list(comparison["primary_category"])
    if not categories:
        st.info(f"Nothing to drill into for {selected_label}.")
    else:
        default = categories.index(rising) if rising in categories else 0
        category = st.selectbox("Category", categories, index=default, key=f"{key}_category")
        sub = shape.compare(df, selected, is_partial, lens, by="sub_category", where={"primary_category": category})
        st.altair_chart(charts.comparison_bars(sub, "sub_category", previous_title), use_container_width=True)

        items = fetch_items(endpoints, selected, category, token)
        if items:
            exp = pd.DataFrame(items)
            exp["date"] = pd.to_datetime(exp["transaction_timestamp"], utc=True).dt.tz_convert(SAO_PAULO).dt.strftime("%d/%m/%Y")
            exp["payment"] = [f"{m} ({i})" if i else (m or "") for m, i in zip(exp["payment_method"], exp["institution"])]
            exp["price"] = exp["price"].map(format_brl)
            exp["mine"] = exp["mine"].map(format_brl)
            amounts = ["price", "mine"] if household else ["mine", "price"]
            names = {"date": "Date", "sub_category": "Sub-category", "price": "Price", "mine": "My share",
                     "payment": "Payment", "paid_by": "Paid by"}
            order = ["date", "sub_category", *amounts, "payment", "paid_by"]
            st.dataframe(exp[order].rename(columns=names), hide_index=True)
        elif items is not None:
            st.caption(f"No {category} {noun} in {selected_label}.")

    # --- Fixed vs variable ---
    st.subheader("Fixed vs variable")
    split = shape.cost_type_split(df, selected, is_partial, lens)
    if split.empty:
        st.info(f"No {noun} in {selected_label} or {shape.month_label(previous)}.")
    else:
        this_title = f"{shape.month_label(selected, short=True)}{to_date}"
        left, right = st.columns([3, 2])
        left.altair_chart(charts.cost_type_chart(split, this_title, previous_title), use_container_width=True)
        table = split.assign(
            current_share=split["current_share"].map(lambda s: f"{s:.0%}"),
            previous_share=split["previous_share"].map(lambda s: f"{s:.0%}"),
        )
        right.dataframe(money_table(table, {
            "cost_type": "Cost type", "current": this_title, "current_share": "Share",
            "previous": previous_title, "previous_share": "Share before",
        }), hide_index=True)
