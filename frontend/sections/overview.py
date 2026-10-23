"""
Spending over time, from the whole month down to a category: four KPI
cards against earlier months, the monthly trend, where the money goes
(categories against last month, and inside the picked one its
sub-categories), where the difference comes from, a category x month
heatmap (how each category moved), and fixed vs day-to-day. Charts only,
no tables.

It opens with the same one-line control row as This month
(sections/filters.py); with show_view (My expenses) it has "Show", which
picks the expenses: "shared" (/analytics/shared), "personal"
(/analytics/personal, only the caller's own) or "all" (both, i.e. my share
of shared plus my personal spending). On Our expenses it's always
"shared". `lens` picks the amount: "Household" (full prices, on Our
expenses) or "My share" (the caller's part). Each section is a card with
its question as the title. Data shaping lives in analytics_shaping (and
filtering), the Altair specs in analytics_charts.
"""
from __future__ import annotations

import datetime
from urllib.parse import urlencode

import streamlit as st

import analytics_charts as charts
import analytics_shaping as shape
import daily_charts
import filtering
import ui
from common import SAO_PAULO, get_data, md
from money import format_brl
from sections.filters import FilterRow

# scope -> (endpoints, what the rows are called)
SCOPES = {
    "shared": (["analytics/shared"], "shared expenses"),
    "personal": (["analytics/personal"], "personal expenses"),
    "all": (["analytics/shared", "analytics/personal"], "expenses"),
}
CARD_HEIGHT = 230


_FAILED = object()


def fetch(endpoint: str, token: str):
    """GET from the API (cached); None, with a message, on failure."""
    result = get_data(endpoint, token, default=_FAILED)
    return None if result is _FAILED else result


def fetch_window(endpoints: list[str], selected: str, token: str, basis: str = "bought"):
    """
    One /analytics payload, or several merged (same window, rows added
    together); None on failure. `basis` "billed" counts installments in
    their billing months.
    """
    query = urlencode({"month": selected, "months": 12, "basis": basis})
    payloads = {e: fetch(f"{e}?{query}", token) for e in endpoints}
    if any(p is None for p in payloads.values()):
        return None
    return shape.merge_payloads(payloads)


def _delta_line(change: float, pct: float, against: str) -> tuple[str, str | None]:
    """'▲ R$ 120,00 (+12,0%) vs Sep', toned for ui.kpi; spending up is "more" (orange)."""
    if round(change, 2) == 0:
        return f"Same as {against}", None
    arrow = "▲" if change > 0 else "▼"
    return f"{arrow} {shape.delta_text(change, pct)} vs {against}", "more" if change > 0 else "less"


def _kpis(df, months, selected, is_partial, lens, headline, noun, previous_title, comparison, rising,
          since, partly) -> None:
    """
    Four equal cards, each a number, its comparison and its sparkbars over
    the last six months. A ▲/▼ only against a month logged in full: a
    partly logged one (`partly`, the day logging began) is named instead.
    """
    previous = shape.shift_month(selected, -1)
    comparable = since is not None and since <= previous
    total = shape.compare_total(df, selected, is_partial, lens)
    average = shape.previous_full_average(df, months, selected, lens, to_day=is_partial, since=since)
    shown = months[-6:]
    totals = shape.monthly_totals(df, shown, lens)
    to_date = " so far" if is_partial else ""
    cards = []

    if comparable:
        first_line = _delta_line(total["change"], total["pct"], previous_title)
    elif partly:
        whole = float(shape.monthly_totals(df, [previous], lens).iloc[0])
        first_line = (f"{shape.month_label(previous, short=True)}: {format_brl(whole)}, logged from the "
                      f"{shape.ordinal(partly)} only", None)
    else:
        first_line = ("Compared once a whole month has been logged", None)
    cards.append((f"{headline}{to_date}", format_brl(total["current"]), [first_line],
                  daily_charts.spark_bars(shape.month_bars(totals, selected), "value", "Spent"),
                  "Everything counted in the month" + (", up to today." if is_partial else ".")))
    if average is None:
        cards.append(("3-month average", "—", [(f"Needs three full months of {noun} first.", None)], None,
                      "The average of the three months before this one, over the same days."))
    else:
        change = round(total["current"] - average, 2)
        usual = [m for m in months if m < selected][-3:]
        cards.append(("3-month average" + (" (same days)" if is_partial else ""), format_brl(average),
                      [_delta_line(change, change / average if average else float("nan"), "it")],
                      daily_charts.spark_bars(shape.month_bars(shape.monthly_totals(df, usual, lens, is_partial), ""),
                                              "value", "Spent", reference=average),
                      "The average of the three months before this one, over the same days."))
    counts = shape.monthly_counts(df, shown)
    before = int(counts.get(shape.shift_month(selected, -1), 0))
    cards.append((f"{noun.capitalize()}{to_date}", str(shape.expense_count(df, selected)),
                  [(f"{before} in all of {shape.month_label(previous)}"
                    + (f" (from the {shape.ordinal(partly)})" if partly else ""), None)],
                  daily_charts.spark_bars(shape.month_bars(counts, selected, money=False), "value", "Expenses"),
                  "How many expenses were logged."))
    if not comparable:
        cards.append(("Biggest increase", "—", [("Compared once a whole month has been logged.", None)], None,
                      "The category that rose most in reais against last month."))
    elif rising is None:
        cards.append(("Biggest increase", "—", [(f"Nothing rose against {previous_title}.", None)], None,
                      "The category that rose most in reais against last month."))
    else:
        row = comparison.set_index("primary_category").loc[rising]
        series = shape.monthly_totals(df[df["primary_category"] == rising], shown, lens)
        cards.append(("Biggest increase", rising, [_delta_line(row["change"], row["pct"], previous_title)],
                      daily_charts.spark_bars(shape.month_bars(series, selected), "value", rising),
                      "The category that rose most in reais against last month."))

    for col, (label, value, lines, chart, help_text) in zip(st.columns(4, gap="small"), cards):
        with col, ui.card(f"kpi_{label[:12]}", height=CARD_HEIGHT):
            ui.kpi(label, value, lines, help=help_text)
            if chart is None:
                ui.empty_chart("Appears once there's history to compare with.", daily_charts.SPARK_HEIGHT)
            else:
                st.altair_chart(chart, use_container_width=True)


def render(token: str, lens: str, key: str, show_view: bool = False) -> None:
    """The whole overview for one lens. `key` prefixes widget keys so each page keeps its own picks."""
    current_month = datetime.datetime.now(SAO_PAULO).strftime("%Y-%m")
    row = FilterRow(key, shape.month_options(current_month, 12), show_view=show_view, installments=True)
    selected = row.month
    scope = row.view() or "shared"
    endpoints, noun = SCOPES[scope]

    # Always fetch 12 months: the 6-month view and the 3-month average both fit inside.
    basis = row.basis()
    data = fetch_window(endpoints, selected, token, basis)
    if data is None:
        return

    everything = shape.to_frame(data)
    filters = row.filters(sorted(everything["primary_category"].unique()))
    df = filtering.filter_rows(everything, filters)
    months = data["months"]
    is_partial = data["is_partial"]
    as_of_day = data["as_of_day"]
    previous = shape.shift_month(selected, -1)
    selected_label = shape.month_label(selected)
    previous_title = f"{shape.month_label(previous, short=True)} (days 1–{as_of_day})" if is_partial \
        else shape.month_label(previous, short=True)
    household = lens == "Household"
    headline = {"shared": "Shared total" if household else "My share", "personal": "Personal",
                "all": "I spent"}[scope]

    if everything.empty:
        st.info(f"No {noun} in the 12 months up to {selected_label}. Log one to see this overview.")
        st.page_link("pages/1_Add_expense.py", label="Add an expense", icon=":material/edit_note:")
        return
    if df.empty:
        st.info("Nothing matches these filters in the 12 months. Widen them to see more.")
        return

    # A ▲/▼ only against a month logged in full; one logged in part is named, not compared.
    first_date = data.get("first_date")
    # Without first_date (an older API), the data's own first month, as This month does.
    since = shape.tracked_since(first_date) or (everything["month"].min() if not everything.empty else None)
    comparable = since is not None and since <= previous
    partly = shape.partly_logged_from(previous, first_date)
    partly_month = first_date[:7] if first_date and shape.partly_logged_from(first_date[:7], first_date) else None

    if basis == "billed":
        st.caption("Installments are counted in the month they're billed (Filters).")

    comparison = shape.compare(df, selected, is_partial, lens)
    rising = shape.biggest_increase(comparison) if comparable else None
    _kpis(df, months, selected, is_partial, lens, headline, noun, previous_title, comparison, rising, since, partly)

    # --- Trend ---
    with ui.card(f"{key}_trend"):
        title, control = st.columns([3, 1], vertical_alignment="bottom")
        title.subheader("How does each month compare?")
        st.session_state.setdefault(f"{key}_window", 12)
        window = control.segmented_control("Months", [6, 12], key=f"{key}_window",
                                           format_func=lambda n: f"{n} months") or 12
        trend_months = months[-window:]
        totals = shape.monthly_totals(df, trend_months, lens)
        trend_average = shape.previous_full_average(df, months, selected, lens, since=since)
        st.altair_chart(charts.trend_chart(totals, selected, is_partial, trend_average,
                                           partly_month if partly_month in trend_months else None),
                        use_container_width=True)
        notes = ["The faded month is still going: shown so far, never projected."] if is_partial else []
        if partly_month in trend_months:
            notes.append(f"* {shape.month_label(partly_month)} was logged from the "
                         f"{shape.ordinal(int(first_date[8:10]))} only.")
        if notes:
            st.caption(" ".join(notes))

    with ui.card(f"{key}_where"):
        targets = {}
        if lens == "Household":  # targets are for the household's shared spending
            rows = get_data("category_targets/", token, default=[])
            targets = {t["primary_category"]: float(t["amount"]) for t in rows or [] if isinstance(t, dict)}
        _where(df, comparison, selected, selected_label, previous_title, is_partial, lens, key, comparable, targets)

    changes = shape.as_changes(comparison, "primary_category")
    if comparable and not changes.empty:
        with ui.card(f"{key}_changes"):
            st.subheader("Where does the difference come from?")
            st.caption(f"Each category against {previous_title}.")
            st.altair_chart(daily_charts.changes_chart(changes.head(10)), use_container_width=True)

    with ui.card(f"{key}_heatmap"):
        st.subheader("Which categories are growing over the months?")
        st.caption("Darker is a bigger month for that category.")
        st.altair_chart(charts.heatmap_chart(shape.heatmap_frame(df, trend_months, lens), trend_months),
                        use_container_width=True)

    with ui.card(f"{key}_fixed"):
        _fixed_vs_variable(df, selected, is_partial, lens, previous, previous_title, noun, selected_label)


def _where(df, comparison, selected, selected_label, previous_title, is_partial, lens, key, comparable,
           targets: dict[str, float]) -> None:
    """
    Where is the money going? Categories against last month (a grey tick
    and the change at the tip, when last month was logged in full; shares
    otherwise), and what's inside the picked one.
    """
    st.subheader(f"Where is the money going in {selected_label}?")
    if comparison.empty:
        st.caption(f"Nothing in {selected_label} or the month before.")
        return
    bars = shape.ranked_comparison(comparison[comparison["current"] > 0], "primary_category")
    if bars.empty:
        st.caption(f"Nothing in {selected_label} yet.")
        return
    tick = "previous" if comparable else None
    if not comparable:
        bars = shape.with_share_text(bars)
    # The household's monthly targets (Settings), as a dark tick: for the whole month.
    bars = bars.assign(target=[targets.get(n, 0.0) for n in bars["name"]])
    notes = ([f"Grey tick: {previous_title}."] if comparable else []) + (
        ["Dark tick: the monthly target."] if bars["target"].gt(0).any() else [])
    if notes:
        st.caption(" ".join(notes))
    left, right = st.columns([1, 1], gap="medium")
    with right:
        category = st.pills("Look inside", list(bars["name"]), default=bars["name"].iloc[0],
                            key=f"{key}_inside") or bars["name"].iloc[0]
    with left:
        st.altair_chart(charts.ranked_bars(bars, picked=category, previous=tick, room=1.7, target="target"),
                        use_container_width=True)
    with right:
        sub = shape.compare(df, selected, is_partial, lens, by="sub_category", where={"primary_category": category})
        inside = shape.ranked_comparison(sub[sub["current"] > 0], "sub_category")
        if not inside.empty:
            if not comparable:
                inside = shape.with_share_text(inside)
            st.altair_chart(charts.ranked_bars(inside, previous=tick, room=1.7), use_container_width=True)


def _fixed_vs_variable(df, selected, is_partial, lens, previous, previous_title, noun, selected_label) -> None:
    st.subheader("How much is fixed, how much is day-to-day?")
    split = shape.cost_type_split(df, selected, is_partial, lens)
    if split.empty:
        st.caption(f"No {noun} in {selected_label} or {shape.month_label(previous)}.")
        return
    this_title = f"{shape.month_label(selected, short=True)}{' so far' if is_partial else ''}"
    names = {"Fixed": "Fixed", "Variable": "Day-to-day"}
    st.caption(md(" · ".join(f"{names.get(t, t)}: {format_brl(c)} ({s:.0%})"
                             for t, c, s in zip(split["cost_type"], split["current"], split["current_share"])
                             if c)))
    st.altair_chart(charts.cost_type_chart(split, this_title, previous_title), use_container_width=True)
