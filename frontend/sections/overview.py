"""
Spending over time, from the whole month down to a category: four KPI
cards against earlier months, the monthly trend, whether the costs we
control are changing (day-to-day spending and bills that vary, each
against its usual month), where the money goes (categories with their
change beside them), what's inside a category, and two compact cards for
fixed costs and one-offs. Charts only, no tables.

It opens with the same one-line control row as This month
(sections/filters.py); with show_view (My expenses) it has "Show", which
picks the expenses: "shared" (/analytics/shared), "personal"
(/analytics/personal, only the caller's own) or "all" (both, i.e. my share
of shared plus my personal spending). On Our expenses it's always
"shared". `lens` picks the amount: "Household" (full prices, on Our
expenses) or "My share" (the caller's part). Each section is a card with
its question as the title. Data shaping lives in analytics_shaping (and
filtering), the Altair specs in analytics_charts and sections/where.
"""
from __future__ import annotations

import datetime
from urllib.parse import urlencode

import streamlit as st

import analytics_charts as charts
import analytics_shaping as shape
import daily_charts
import filtering
import targets as category_targets
import ui
from common import SAO_PAULO, get_data
from money import format_brl
from sections import where
from sections.filters import FilterRow

# scope -> (endpoints, what the rows are called)
SCOPES = {
    "shared": (["analytics/shared"], "shared expenses"),
    "personal": (["analytics/personal"], "personal expenses"),
    "all": (["analytics/shared", "analytics/personal"], "expenses"),
}
CARD_HEIGHT = 240  # a minimum: a card whose text wraps grows rather than clipping
COMPACT_HEIGHT = 150  # fixed costs and one-offs: text only, no chart
CONTROL_CARDS = 9  # categories drawn in "Are the costs we control changing?", biggest first


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
        with col, ui.card(f"kpi_{label[:12]}", height="stretch", min_height=CARD_HEIGHT):
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

    # --- The costs we control ---
    with ui.card(f"{key}_control"):
        _control(df, months, selected, is_partial, lens, since)

    targets = []
    if lens == "Household":  # targets are for the household's shared spending
        targets = get_data("category_targets/", token, default=[]) or []
    with ui.card(f"{key}_where"):
        category = _where(comparison, selected_label, previous_title, comparable, targets, key)
    if category:
        with ui.card(f"{key}_inside"):
            _inside(df, selected, is_partial, lens, previous_title, comparable, targets, key, category)

    # --- Fixed costs and one-offs: a compact card each ---
    fixed_col, offs_col = st.columns(2, gap="small")
    with fixed_col, ui.card(f"{key}_fixed", height="stretch", min_height=COMPACT_HEIGHT):
        _fixed(df, selected, is_partial, lens, previous_title, comparable)
    with offs_col, ui.card(f"{key}_one_offs", height="stretch", min_height=COMPACT_HEIGHT):
        _one_offs(df, selected, lens, filters)


def _control(df, months, selected, is_partial, lens, since) -> None:
    """
    Are the costs we control changing? Day-to-day spending and the bills
    that vary, one-offs left out, each category against its usual month:
    the answer in sentences, then a small KPI per category with its months.
    """
    st.subheader("Are the costs we control changing?")
    st.caption("Day-to-day spending and bills that vary (cost type Variable in Settings), one-offs left out. "
               "Each is set against its usual month, the average of up to three months logged in full"
               + (" over the same days" if is_partial else "") + ": the dashed line.")
    rows = shape.control_rows(df, months, selected, lens, is_partial, since)
    if not rows:
        st.caption("Nothing here among what's being counted: the filters may leave it out.")
        return
    ui.kpi_lines(shape.control_lines(rows))
    shown = rows[:CONTROL_CARDS]
    for start in range(0, len(shown), 3):
        for col, r in zip(st.columns(3, gap="medium"), shown[start:start + 3]):
            with col:
                if r["usual"] is None:
                    lines = [("No usual month yet", None)]
                else:
                    lines = [_delta_line(r["change"], r["pct"], "usual")]
                if r["streak"] >= 2:
                    lines.append((f"Above usual {r['streak']} months running", "more"))
                ui.kpi(r["name"], format_brl(r["current"]), lines)
                st.altair_chart(daily_charts.spark_bars(shape.month_bars(r["series"], selected), "value", r["name"],
                                                        reference=r["usual"]), use_container_width=True)
    if len(rows) > CONTROL_CARDS:
        st.caption(f"The {CONTROL_CARDS} biggest of {len(rows)}; Filters › Categories narrows it.")


def _where(comparison, selected_label, previous_title, comparable, targets: list[dict], key) -> str | None:
    """
    Where is the money going? Categories as bars (a grey tick for last
    month, a dark one for the target) with their change beside them.
    Returns the category to look inside, picked in the card below.
    """
    title, control = st.columns([3, 1], vertical_alignment="bottom")
    title.subheader(f"Where is the money going in {selected_label}?")
    if comparison.empty:
        st.caption(f"Nothing in {selected_label} or the month before.")
        return None
    bars = shape.ranked_comparison(comparison[comparison["current"] > 0], "primary_category")
    if bars.empty:
        st.caption(f"Nothing in {selected_label} yet.")
        return None
    mode = where.change_mode(control, f"{key}_change_mode") if comparable else "R$"
    if not comparable:
        bars = shape.with_share_text(bars)
    # The household's monthly targets (Settings), as a dark tick: for the whole month.
    whole = category_targets.whole(targets)
    bars = bars.assign(target=[whole.get(n, 0.0) for n in bars["name"]])
    notes = ([f"Grey tick and change: against {previous_title}."] if comparable else []) + (
        ["Dark tick: the monthly target."] if bars["target"].gt(0).any() else [])
    if notes:
        st.caption(" ".join(notes))
    names = list(bars["name"])
    category = st.session_state.get(f"{key}_inside")
    category = category if category in names else names[0]
    where.bars_and_change(bars, mode, "previous" if comparable else None, picked=category, target="target",
                          change_title=f"Change vs {previous_title}")
    return category


def _inside(df, selected, is_partial, lens, previous_title, comparable, targets, key, category) -> None:
    """What's inside a category: the picker on its own row, then its sub-categories drawn like the categories."""
    st.subheader("What's inside a category?")
    names = list(shape.compare(df, selected, is_partial, lens).query("current > 0")["primary_category"])
    if category not in names:
        names = [category] + names
    if st.session_state.get(f"{key}_inside") not in names:
        st.session_state[f"{key}_inside"] = category
    category = st.pills("Look inside", names, key=f"{key}_inside", label_visibility="collapsed") or category
    sub = shape.compare(df, selected, is_partial, lens, by="sub_category", where={"primary_category": category})
    inside = shape.ranked_comparison(sub[sub["current"] > 0], "sub_category")
    if inside.empty:
        st.caption(f"Nothing in {category} this month.")
        return
    if not comparable:
        inside = shape.with_share_text(inside)
    sub_targets = category_targets.subs(targets, category)
    inside = inside.assign(target=[sub_targets.get(n, 0.0) for n in inside["name"]])
    if inside["target"].gt(0).any():
        st.caption("Dark tick: the sub-category's own target (Settings).")
    mode = st.session_state.get(f"{key}_change_mode") or "R$"
    where.bars_and_change(inside, mode, "previous" if comparable else None, target="target",
                          change_title=f"Change vs {previous_title}")


def _fixed(df, selected, is_partial, lens, previous_title, comparable) -> None:
    """Fixed costs, compact: the month's total and which ones moved (a price rise shows here)."""
    fixed = shape.fixed_costs(df)
    total = shape.compare_total(fixed, selected, is_partial, lens)
    lines = [_delta_line(total["change"], total["pct"], previous_title)] if comparable else []
    if comparable:
        moved = shape.biggest_changes(shape.compare(fixed, selected, is_partial, lens, by="sub_category"),
                                      "sub_category")
        for _, r in moved.head(3).iterrows():
            arrow, tone = ("▲", "more") if r["change"] > 0 else ("▼", "less")
            lines.append((f"{r['sub_category']}: {arrow} {shape.signed_brl(r['change'])}", tone))
    ui.kpi("Fixed costs" + (" so far" if is_partial else ""), format_brl(total["current"]), lines,
           help="What recurs at a set price: rent, condo, internet, subscriptions, insurance. One-offs are "
                "counted apart. A bill not logged yet this month shows as a drop.")
    if fixed.empty:
        st.caption("No fixed costs among what's being counted.")


def _one_offs(df, selected, lens, filters) -> None:
    """One-offs, compact: annual and extraordinary costs this month, the biggest named."""
    if filters.without_one_offs:
        ui.kpi("One-offs", "—", [("Left out by the filters", None)])
        return
    month = shape.one_offs(df)
    month = month[month["month"] == selected]
    column = shape.lens_column(lens)
    by_sub = month.groupby("sub_category")[column].sum().sort_values(ascending=False)
    lines = [(f"{name}: {format_brl(v)}", None) for name, v in by_sub.head(3).items() if v]
    ui.kpi("One-offs", format_brl(round(float(month[column].sum()), 2)), lines or [("None this month", None)],
           help="Annual and extraordinary costs (IPVA, a vet emergency): counted apart, since they say little "
                "about how you live.")
