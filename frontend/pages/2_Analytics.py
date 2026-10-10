import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

import analytics_charts as charts
import analytics_shaping as shape
from config import API_BASE_URL
from money import format_brl

# 1. Force Wide Mode (important for Tableau)
st.set_page_config(page_title="Analytics", layout="wide")

st.title("📈 Financial Analytics")

overview_tab, tableau_tab = st.tabs(["Overview", "Tableau"])

# --- Tableau: the long-term analytics home, unchanged ---
with tableau_tab:
    # Tableau Link
    base_url = "https://10ax.online.tableau.com/t/felipetabdev/views/ExpendituresControlCenter/Dashboard1"
    params= "?:embed=yes&:showVizHome=no&:toolbar=top&:tabs=no"
    final_url = base_url + params

    # Embed the code
    html_code = f"""
        <div style="
            display: flex;
            justify-content: center;
            width: 100%;
        ">
            <iframe
                src="{final_url}"
                width="1000"
                height="1100"
                style="border: none; overflow: hidden;"
            ></iframe>
        </div>
    """

    # Render
    components.html(html_code, height=1150,scrolling=True)


# --- Overview: shared expenses, in-app ---

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
BASIS = "Shared expenses only · purchase month · São Paulo time."


@st.cache_data(ttl=60)
def fetch(endpoint: str, token: str):
    """GET from the API; None (with a message) on failure. Keyed on the token, like the Tracker."""
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}", headers={"Authorization": f"Bearer {token}"})
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


with overview_tab:
    token = st.session_state.get("access_token")
    if not token:
        st.error("You are not logged in.")
        st.info("Please go to the **Home** page to log in.")
        st.stop()

    current_month = datetime.datetime.now(SAO_PAULO).strftime("%Y-%m")

    # --- Controls ---
    # Defaults go through session state (not `default=`) so a test or a
    # later page can preset them without Streamlit warning about both.
    st.session_state.setdefault("analytics_lens", "Household")
    st.session_state.setdefault("analytics_window", 12)
    c1, c2, c3 = st.columns([2, 2, 2], vertical_alignment="bottom")
    selected = c1.selectbox(
        "Month", shape.month_options(current_month, 12),
        format_func=shape.month_label, key="analytics_month",
    )
    lens = c2.segmented_control(
        "Lens", list(shape.LENSES), key="analytics_lens",
        help="Household: the full price of shared expenses. My share: the part of each that is yours.",
    ) or "Household"
    window = c3.segmented_control(
        "Trend window", [6, 12], key="analytics_window",
        format_func=lambda n: f"{n} months",
    ) or 12

    # Always fetch 12 months: the 6-month view and the 3-month average both fit inside.
    data = fetch(f"analytics/shared?{urlencode({'month': selected, 'months': 12})}", token)
    if data is None:
        st.stop()

    df = shape.to_frame(data)
    months = data["months"]
    is_partial = data["is_partial"]
    as_of_day = data["as_of_day"]
    previous = shape.shift_month(selected, -1)
    selected_label = shape.month_label(selected)
    previous_title = f"{shape.month_label(previous, short=True)} (days 1–{as_of_day})" if is_partial else shape.month_label(previous, short=True)
    to_date = " to date" if is_partial else ""

    st.caption(
        f"{BASIS} {lens}: "
        + ("full price of each shared expense." if lens == "Household" else "your share of each shared expense.")
        + (f" {selected_label} is in progress, so it's compared with days 1–{as_of_day} of other months." if is_partial else "")
    )

    if df.empty:
        st.info(f"No shared expenses in the 12 months up to {selected_label}. Log one in the Tracker to see this overview.")
        st.page_link("pages/1_Tracker.py", label="Go to the Tracker", icon="📝")
        st.stop()

    # --- KPIs ---
    total = shape.compare_total(df, selected, is_partial, lens)
    average = shape.previous_full_average(df, months, selected, lens, to_day=is_partial)
    comparison = shape.compare(df, selected, is_partial, lens)
    rising = shape.biggest_increase(comparison)

    k1, k2, k3, k4 = st.columns(4)
    delta, colour = metric_delta(total["change"], total["pct"])
    k1.metric(
        f"{lens} · {shape.month_label(selected, short=True)}{to_date}", format_brl(total["current"]),
        delta=delta, delta_color=colour, border=True,
        help=f"Against {format_brl(total['previous'])} in {previous_title}.",
    )
    if average is None:
        k2.metric("vs 3-month average", "—", border=True,
                  help="Needs three full months of shared expenses before this month.")
    else:
        change = round(total["current"] - average, 2)
        delta, colour = metric_delta(change, change / average if average else float("nan"))
        k2.metric(
            "vs 3-month average" + (" (same days)" if is_partial else ""), format_brl(average),
            delta=delta, delta_color=colour, border=True,
            help="Average of the three months before this one" + (f", days 1–{as_of_day} only." if is_partial else "."),
        )
    k3.metric(f"Shared expenses{to_date}", shape.expense_count(df, selected), border=True,
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

    # --- Where are we spending more ---
    st.subheader("Where are we spending more")
    st.caption(f"{selected_label}{to_date} by category, largest first. Grey tick: {previous_title}.")
    if comparison.empty:
        st.info(f"No shared expenses in {selected_label} or {shape.month_label(previous)}.")
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
        category = st.selectbox("Category", categories, index=default, key="analytics_category")
        sub = shape.compare(df, selected, is_partial, lens, by="sub_category", where={"primary_category": category})
        st.altair_chart(charts.comparison_bars(sub, "sub_category", previous_title), use_container_width=True)

        items = fetch(f"analytics/shared/expenses?{urlencode({'month': selected, 'primary_category': category})}", token)
        if items:
            exp = pd.DataFrame(items)
            exp["date"] = pd.to_datetime(exp["transaction_timestamp"], utc=True).dt.tz_convert(SAO_PAULO).dt.strftime("%d/%m/%Y")
            exp["payment"] = [f"{m} ({i})" if i else (m or "") for m, i in zip(exp["payment_method"], exp["institution"])]
            exp["price"] = exp["price"].map(format_brl)
            exp["mine"] = exp["mine"].map(format_brl)
            amounts = ["price", "mine"] if lens == "Household" else ["mine", "price"]
            names = {"date": "Date", "sub_category": "Sub-category", "price": "Price", "mine": "My share",
                     "payment": "Payment", "paid_by": "Paid by"}
            order = ["date", "sub_category", *amounts, "payment", "paid_by"]
            st.dataframe(exp[order].rename(columns=names), hide_index=True)
        elif items is not None:
            st.caption(f"No shared {category} expenses in {selected_label}.")

    # --- Fixed vs variable ---
    st.subheader("Fixed vs variable")
    split = shape.cost_type_split(df, selected, is_partial, lens)
    if split.empty:
        st.info(f"No shared expenses in {selected_label} or {shape.month_label(previous)}.")
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
