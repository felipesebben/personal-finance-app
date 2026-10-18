"""
This month, day by day: is this month running ahead of last month and of
the usual month, by the same day, and where does the money go?

Top to bottom, from the whole month down to single days:
- one row of controls (sections/filters.py);
- the answer: a hero card (spent so far, with its running total) beside
  this month's calendar as a reference, then four equal KPI cards;
- one card per question: how the month built up; where the money goes
  (categories, then inside the picked one its sub-categories: day by day
  says little for what's bought once a month, like electricity, so it
  stops there); where the difference comes from; what went on the
  biggest days (a picked day's purchases as bars); the weekday pattern.

Charts only: no tables here (Entries is where expenses are listed). On Our
expenses it reads the shared endpoints; on My expenses (show_view=True)
"Show" picks shared, personal or both. Shaping lives in daily_shaping (and
filtering), the charts in daily_charts and analytics_charts; this module
only wires them to widgets.
"""
from __future__ import annotations

import datetime
from html import escape
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

import analytics_charts
import analytics_shaping as shape
import daily_charts as charts
import daily_shaping as daily
import filtering
import ui
from common import SAO_PAULO, get_data, md
from money import format_brl
from sections.filters import FilterRow

# source -> (daily endpoint, expense list endpoint)
ENDPOINTS = {
    "shared": ("analytics/shared/daily", "analytics/shared/expenses"),
    "personal": ("analytics/personal/daily", "analytics/personal/expenses"),
}
# My expenses' Show -> the sources behind it, and what they're called
VIEW_SOURCES = {"all": ["shared", "personal"], "personal": ["personal"], "shared": ["shared"]}
NOUNS = {"all": "expenses", "personal": "personal expenses", "shared": "shared expenses"}
MONTHS = 7  # the month and six before it: last month, the usual month and the cards' bars
TOP_CHANGES = 10
CARD_HEIGHT = 200
TOP_HEIGHT = 370   # the hero and the calendar beside it, filled by both (at least: text wraps on a phone)
HERO_SPARK = 185   # what the hero's text leaves of it
EMPTY = {
    "per_day": "Bars per month appear once there's an earlier month to compare with.",
    "last": "Appears once a whole month before this one has been logged.",
    "usual": "Appears after three whole months of history.",
}
_FAILED = object()


def _fetch(sources: list[str], month: str, token: str):
    """The daily payloads of these sources, merged with each row's source; None on failure."""
    query = urlencode({"month": month, "months": MONTHS})
    payloads = {s: get_data(f"{ENDPOINTS[s][0]}?{query}", token, default=_FAILED) for s in sources}
    if any(p is _FAILED or p is None for p in payloads.values()):
        return None
    return shape.merge_payloads(payloads)


def _card_chart(card: dict, p: dict, hist: pd.DataFrame, this_cal: pd.DataFrame):
    """The sparkline under each card, or None (the card then holds the space with a note)."""
    if card["key"] == "per_day" and len(hist) > 1:
        return charts.spark_bars(hist, "per_day", "Per day, same days", reference=p["usual_per_day"])
    if card["key"] == "last" and p["has_last"]:
        past = hist[hist["month"] != p["month"]].assign(is_selected=lambda d: d["month"] == p["previous"])
        return charts.spark_bars(past, "total", "Whole month") if not past.empty else None
    if card["key"] == "usual" and p["usual_total"] is not None:
        months = hist[hist["month"].isin(p["usual_of"])].assign(is_selected=False)
        return charts.spark_bars(months, "total", "Whole month", reference=p["usual_total"])
    if card["key"] == "allowance":
        return charts.spark_progress(p["so_far"] / p["reference"] if p["reference"] else 0.0, p["day"] / p["days"])
    if card["key"] == "days":
        return charts.spark_days(this_cal)
    return None


def _calendar_legend(top: float) -> None:
    """The calendar's legend, in HTML so it never changes the chart's size: an empty day, the green scale, today."""
    swatch = "display:inline-block;border-radius:3px;vertical-align:middle"
    st.html(
        f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:0.4rem;font-size:0.75rem;color:{ui.INK_2}">'
        f'<span style="{swatch};width:12px;height:12px;background:{charts.EMPTY_DAY};border:1px solid {ui.LINE}">'
        f'</span><span>Nothing</span><span style="width:0.5rem"></span>'
        f'<span style="{swatch};width:72px;height:8px;'
        f'background:linear-gradient(90deg,{charts.HEAT[0]},{charts.HEAT[1]})"></span>'
        f"<span>{escape(shape.short_brl(top))}+</span><span style=\"width:0.5rem\"></span>"
        f'<span style="{swatch};width:12px;height:12px;border:2px solid {ui.INK}"></span><span>Today</span></div>'
    )


def _items(sources: list[str], day: str, token: str, filters: filtering.Filters) -> list[dict] | None:
    """A day's expenses from every source, obeying the filters; None on failure."""
    lists = [get_data(f"{ENDPOINTS[s][1]}?{urlencode({'day': day})}", token, default=_FAILED) for s in sources]
    if any(items is _FAILED for items in lists):
        return None
    items = [i for items in lists if isinstance(items, list) for i in items]
    return filtering.filter_rows(pd.DataFrame(items), filters).to_dict("records") if items else []


def _top(p: dict, hero: dict, df, data, lens: str, since, this_cal, month: str) -> None:
    """The answer first: the hero card beside this month's calendar, then four equal KPI cards."""
    left, right = st.columns(2, gap="small")
    with left, ui.card("hero", min_height=TOP_HEIGHT):
        ui.kpi(hero["label"], hero["amount"], hero["lines"], hero=True,
               help="Everything counted so far this month. The line is this month's running total (green) "
                    "over last month's (grey).")
        frame = daily.running_frame(df, data, lens, since=since, with_usual=False)
        st.altair_chart(charts.spark_running(frame, daily.series_order(data), daily.days_in(month), HERO_SPARK),
                        use_container_width=True)
    with right, ui.card("calendar", min_height=TOP_HEIGHT):
        st.markdown("**Which days cost the most?**", help="Each day shaded by what was spent; hover a day for the "
                    "amount and its biggest category. The darkest green is a typical big day, so one large "
                    "payment doesn't wash the rest out.")
        top = daily.calendar_scale_max(this_cal)
        weeks = int(this_cal["week"].max()) + 1
        # The rows share what the title and the legend leave of the card.
        row_height = max(28, (TOP_HEIGHT - 120) // weeks)
        st.altair_chart(charts.calendar_chart(this_cal, top, row_height=row_height), use_container_width=True)
        _calendar_legend(top)


def _cards(p: dict, cards: list[dict], hist, this_cal) -> None:
    for col, card in zip(st.columns(4, gap="small"), cards):
        with col, ui.card(card["key"], height=CARD_HEIGHT):
            ui.kpi(card["label"], card["value"], card["lines"], help=card["help"])
            chart = _card_chart(card, p, hist, this_cal)
            if chart is None:
                ui.empty_chart(EMPTY.get(card["key"], "Nothing to draw yet."), charts.SPARK_HEIGHT)
            else:
                st.altair_chart(chart, use_container_width=True)


def _where(picked, lens: str, month: str, key: str) -> None:
    """Where is the money going? The categories, then what's inside the picked one."""
    st.subheader(f"Where is the money going in {daily.month_name(month)}?")
    mix = daily.ranked(picked, lens, "primary_category", month=month)
    if mix.empty:
        st.caption("Nothing spent yet this month.")
        return
    left, right = st.columns([1, 1], gap="medium")
    with right:
        category = st.pills("Look inside", list(mix["name"]), default=mix["name"].iloc[0],
                            key=f"{key}_daily_inside") or mix["name"].iloc[0]
    with left:
        st.altair_chart(analytics_charts.ranked_bars(mix, picked=category), use_container_width=True)
    with right:
        rows = picked[picked["primary_category"] == category]
        inside = daily.ranked(rows, lens, "sub_category", month=month)
        st.altair_chart(analytics_charts.ranked_bars(inside), use_container_width=True)


def _biggest_days(df, lens: str, month: str, sources: list[str], token: str, filters, key: str) -> None:
    """What went on the biggest days? The days, then the picked day's purchases."""
    st.subheader(f"What went on the biggest days of {daily.month_name(month)}?")
    days = daily.biggest_days(df, month, lens)
    if days.empty:
        st.caption("Nothing spent yet this month.")
        return
    labels = dict(zip(days["key"], days["name"]))
    left, right = st.columns([1, 1], gap="medium")
    with right:
        day = st.selectbox("Look inside", list(labels), format_func=labels.get, key=f"{key}_daily_day")
    with left:
        st.altair_chart(analytics_charts.ranked_bars(days, picked=labels[day], room=1.9),
                        use_container_width=True)
    with right:
        items = _items(sources, day, token, filters)
        frame = daily.day_items(items or [], lens, SAO_PAULO)
        if frame.empty:
            st.caption("Nothing among what's being counted." if items is not None else "")
        else:
            st.altair_chart(analytics_charts.ranked_bars(frame), use_container_width=True)


def render(token: str, lens: str, key: str, show_view: bool = False) -> None:
    today = datetime.datetime.now(SAO_PAULO).date()
    current = today.strftime("%Y-%m")

    row = FilterRow(f"{key}_daily", shape.month_options(current, 12), show_view=show_view)
    month = row.month
    view = row.view() or "shared"
    sources, noun = VIEW_SOURCES[view], NOUNS[view]
    data = _fetch(sources, month, token)
    if data is None:
        return
    rows = daily.rows_frame(data)
    filters = row.filters(sorted(rows["primary_category"].unique()) if not rows.empty else [])
    if rows.empty:
        st.info(f"No {noun} in {shape.month_label(month)} or the months before it yet. "
                "As you log expenses, this page compares each month with the ones before, day by day.")
        st.page_link("pages/1_Add_expense.py", label="Add an expense", icon=":material/edit_note:")
        return

    since = daily.tracked_since(rows)  # before any filter: earlier months weren't logged in full
    picked = filtering.filter_rows(rows, filters)
    if picked.empty:
        st.info("Nothing matches these filters in this window. Widen them to see more.")
        return
    df = daily.by_day(picked)
    p = daily.pace(df, data, lens, since=since)
    previous = daily.month_name(p["previous"])
    hist = daily.history(df, data, lens, since=since)
    this_cal = daily.calendar_frame(df, month, lens, today)

    _top(p, daily.headline(p, filtering.note(filters), started=daily.logging_started(rows)),
         df, data, lens, since, this_cal, month)
    _cards(p, daily.cards(p), hist, this_cal)

    # --- How the month built up ---
    with ui.card("running"):
        st.subheader("How is the month building up?")
        st.caption(f"Spent so far, day by day, against {previous} and the usual month (dashed). "
                   "Hover to compare a day.")
        st.altair_chart(
            charts.running_total_chart(daily.running_frame(df, data, lens, since=since), daily.series_order(data),
                                       daily.days_in(month), p["day"] if p["is_partial"] else None, key),
            use_container_width=True,
        )

    with ui.card("where"):
        _where(picked, lens, month, key)

    # --- Where the difference comes from ---
    if p["has_last"]:
        with ui.card("changes"):
            st.subheader("Where does the difference come from?")
            against_names = {previous: "last"}
            if p["usual_total"] is not None:
                against_names["Usual month"] = "usual"
            c1, c2, _ = st.columns([2, 2, 3])
            against_label = c1.segmented_control("Compare with", list(against_names), default=previous,
                                                 key=f"{key}_daily_against") or previous
            level = c2.segmented_control("Group by", ["Category", "Sub-category"], default="Category",
                                         key=f"{key}_daily_level") or "Category"
            against = against_names.get(against_label, "last")
            changes = daily.category_changes(picked, data, lens, against=against,
                                             level="primary_category" if level == "Category" else "sub_category",
                                             since=since)
            if changes.empty or not changes["change"].any():
                st.caption("No change by category to show.")
            else:
                st.markdown(md(daily.change_summary(changes, previous if against == "last" else "usual")))
                moved = changes[changes["change"] != 0]
                st.altair_chart(charts.changes_chart(moved.head(TOP_CHANGES)), use_container_width=True)
                same = changes.loc[changes["change"] == 0, "name"]
                notes = [f"The {TOP_CHANGES} biggest moves of {len(moved)}."] if len(moved) > TOP_CHANGES else []
                if not same.empty:
                    notes.append(f"Unchanged: {', '.join(same)}.")
                if notes:
                    st.caption(" ".join(notes))

    with ui.card("biggest"):
        _biggest_days(df, lens, month, sources, token, filters, key)

    # --- Patterns ---
    with ui.card("weekdays"):
        st.subheader("Which weekdays cost most?")
        start = rows["date"].min()  # the first day anything was logged, whatever is filtered
        profile = daily.weekday_profile(df, data, lens, today, since=start)
        if profile.empty or profile["average"].max() == 0:
            st.caption("Not enough days yet.")
        else:
            busiest = profile.loc[profile["average"].idxmax()]
            st.caption(md(f"Average per day since {start:%d %b}, quiet days included: "
                          f"{daily.WEEKDAY_NAMES[int(busiest['weekday'])]}s cost most."))
            st.altair_chart(charts.weekday_chart(profile), use_container_width=True)
