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
import calendar_html
import analytics_shaping as shape
import daily_charts as charts
import daily_shaping as daily
import filtering
import notices
import ui
import upcoming
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
MONTHS = 13  # the month and twelve before: last month, usual, the 12-month average, the same month last year
TOP_CHANGES = 10
CARD_HEIGHT = 200
TOP_HEIGHT = 352  # the hero and the calendar beside it, so the top row lines up
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


def _card_chart(card: dict, p: dict, hist: pd.DataFrame, this_cal: pd.DataFrame, last_cal: pd.DataFrame):
    """The sparkline under each card, or None (the card then holds the space with a note)."""
    if card["key"] == "per_day" and len(hist) > 1:
        return charts.spark_bars(hist, "per_day", "Per day, same days", reference=p["usual_per_day"])
    if card["key"] == "last" and not p["has_last"] and p["last_partly_from"]:
        return charts.spark_days(last_cal)
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


def _items(sources: list[str], day: str, token: str, filters: filtering.Filters) -> list[dict] | None:
    """A day's expenses from every source, obeying the filters; None on failure."""
    lists = [get_data(f"{ENDPOINTS[s][1]}?{urlencode({'day': day})}", token, default=_FAILED) for s in sources]
    if any(items is _FAILED for items in lists):
        return None
    items = [i for items in lists if isinstance(items, list) for i in items]
    return filtering.filter_rows(pd.DataFrame(items), filters).to_dict("records") if items else []


def _top(hero: dict, spark, this_cal, p: dict, top_category: str | None) -> None:
    """
    The answer first: the hero KPI with a sparkline of the month so far
    against last month (the gist; "Are we on track?" below has every
    comparison), and beside it this month's calendar as its own small card
    (where we are in the month, which days cost most; hover a day). On a
    phone the calendar drops below the hero.
    """
    left, right = st.columns([2, 1], gap="small")
    with left, ui.card("hero", min_height=TOP_HEIGHT):
        ui.kpi(hero["label"], hero["amount"], hero["lines"], hero=True,
               help="Everything counted so far this month, against the same days of earlier months.")
        if spark is not None:
            st.altair_chart(spark, use_container_width=True)
    with right, ui.card("calendar", min_height=TOP_HEIGHT):
        where = f"day {p['day']} of {p['days']}" if p["is_partial"] else f"all {p['days']} days"
        st.html(f'<div class="hf-kpi-label">{escape(daily.month_name(p["month"]))} · {where}</div>')
        st.html(calendar_html.calendar_html(this_cal, daily.calendar_scale_max(this_cal)))
        st.html('<div class="hf-cal-note">' + escape((f"Mostly {top_category}. " if top_category else "")
                                                      + "Darker days cost more; hover a day.") + "</div>")


def _cards(p: dict, cards: list[dict], hist, this_cal, last_cal) -> None:
    for col, card in zip(st.columns(4, gap="small"), cards):
        with col, ui.card(card["key"], height=CARD_HEIGHT):
            ui.kpi(card["label"], card["value"], card["lines"], help=card["help"])
            chart = _card_chart(card, p, hist, this_cal, last_cal)
            if chart is None:
                ui.empty_chart(EMPTY.get(card["key"], "Nothing to draw yet."), charts.SPARK_HEIGHT)
            else:
                st.altair_chart(chart, use_container_width=True)


def _targets(token: str, lens: str) -> dict[str, float]:
    """The household's monthly targets by category; only for the Household lens (they're for shared spending)."""
    if lens != "Household":
        return {}
    rows = get_data("category_targets/", token, default=[])
    return {t["primary_category"]: float(t["amount"]) for t in rows or [] if isinstance(t, dict)}


def _due(token: str, month: str, view: str, lens: str, filters: filtering.Filters):
    """Recurring bills not logged yet and card installments billed this month, as the filters keep them."""
    expenses = get_data("expenditures", token) or []
    bills = filtering.filter_rows(upcoming.recurring_due(expenses, month, datetime.datetime.now(SAO_PAULO).date(),
                                                        view, lens, SAO_PAULO), filters)
    cards = filtering.filter_rows(upcoming.installments_due(expenses, month, view, lens, SAO_PAULO), filters)
    return bills, cards


def _still_to_come(bills, cards) -> None:
    """
    What's still to come this month: recurring bills not logged yet, and
    card installments of earlier purchases billed this month. Only drawn
    when there's something, and only for the month in progress.
    """
    if bills.empty and cards.empty:
        return
    with ui.card("upcoming"):
        st.subheader("What's still to come this month?")
        parts = []
        if not bills.empty:
            parts.append(f"about {format_brl(bills['amount'].sum())} in bills not logged yet")
        if not cards.empty:
            parts.append(f"{format_brl(cards['amount'].sum())} in card installments of earlier purchases")
        st.caption(md("Still to come: " + " and ".join(parts) + ". Bills are recurring expenses from the last "
                      f"{upcoming.LOOKBACK} months, at their latest amount."))
        left, right = st.columns(2, gap="medium")
        if not bills.empty:
            with left:
                st.markdown("**Bills not logged yet**")
                st.altair_chart(analytics_charts.ranked_bars(bills, room=1.9), use_container_width=True)
        if not cards.empty:
            with right if not bills.empty else left:
                st.markdown("**Card installments billed this month**")
                st.altair_chart(analytics_charts.ranked_bars(cards, room=1.7), use_container_width=True)


def _where(picked, lens: str, month: str, p: dict, key: str, targets: dict[str, float]) -> None:
    """Where is the money going? The categories, then what's inside the picked one, each against last month."""
    st.subheader(f"Where is the money going in {daily.month_name(month)}?")
    mix = daily.ranked(picked, lens, "primary_category", month=month)
    if mix.empty:
        st.caption("Nothing spent yet this month.")
        return
    # Last month by the same day as a grey tick, once it was logged in full (a partial month would mislead).
    tick = "previous" if p["has_last"] else None
    notes = []
    if tick:
        by = f" by the {daily.ordinal(p['day'])}" if p["is_partial"] else ""
        notes.append(f"Grey tick: {daily.month_name(p['previous'])}{by}.")
        mix = daily.against_last_month(mix, picked, lens, "primary_category", month, p["day"])
    # The household's monthly targets (Settings), as a dark tick: for the whole month.
    mix = mix.assign(target=[targets.get(n, 0.0) for n in mix["name"]])
    if mix["target"].gt(0).any():
        notes.append("Dark tick: the monthly target.")
    if notes:
        st.caption(" ".join(notes))
    left, right = st.columns([1, 1], gap="medium")
    with right:
        category = st.pills("Look inside", list(mix["name"]), default=mix["name"].iloc[0],
                            key=f"{key}_daily_inside") or mix["name"].iloc[0]
    with left:
        st.altair_chart(analytics_charts.ranked_bars(mix, picked=category, previous=tick, target="target"),
                        use_container_width=True)
    with right:
        rows = picked[picked["primary_category"] == category]
        inside = daily.ranked(rows, lens, "sub_category", month=month)
        if tick:
            inside = daily.against_last_month(inside, rows, lens, "sub_category", month, p["day"])
        st.altair_chart(analytics_charts.ranked_bars(inside, previous=tick), use_container_width=True)


def _biggest_days(df, lens: str, month: str, p: dict, sources: list[str], token: str, filters, key: str) -> None:
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
        # How far above a normal day each one is: the month's average day, quiet days included.
        average = round(p["so_far"] / p["day"], 2) if p["day"] else None
        st.altair_chart(analytics_charts.ranked_bars(days, picked=labels[day], room=1.9, reference=average,
                                                     reference_label=f"average day {shape.short_brl(average or 0)}"),
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
    started = daily.logging_started(rows)
    p = daily.pace(df, data, lens, since=since, started=started)
    previous = daily.month_name(p["previous"])
    hist = daily.history(df, data, lens, since=since)
    this_cal = daily.calendar_frame(df, month, lens, today)

    targets = _targets(token, lens)
    target = daily.target_total(targets, picked, filters.active)
    month_rows = picked[picked["month"] == month]
    spent = month_rows.groupby("primary_category")[shape.lens_column(lens)].sum().to_dict()
    top_category = max(spent, key=spent.get) if spent else None

    bills = cards = None
    if p["is_partial"]:
        bills, cards = _due(token, month, view, lens, filters)
        # In-app notices, never pushed: past or near a target, a recurring bill late.
        ui.notices(notices.notices({c: v for c, v in targets.items() if c in spent or not filters.active}, spent,
                                   bills, p["day"], p["days"]))

    track = daily.track_frame(df, data, lens, since=since, started=started, target=target)
    spark = charts.hero_spark(*track, daily.days_in(month))
    _top(daily.headline(p, filtering.note(filters), started=started), spark, this_cal, p, top_category)
    _cards(p, daily.cards(p), hist, this_cal, daily.calendar_frame(df, p["previous"], lens, today))
    if p["is_partial"]:
        _still_to_come(bills, cards)

    # --- Are we on track this month? (days) ---
    with ui.card("track"):
        st.subheader("Are we on track this month?")
        frame, order, roles = track
        named = [f"the {daily.BASELINES[r][0].lower()}" if r != "last" else n for n, r in zip(order[1:], roles[1:])]
        named = [", ".join(named[:-1]) + " and " + named[-1]] if len(named) > 1 else named
        partly = (f" {previous} was logged from the {daily.ordinal(p['last_partly_from'])} only, so its line starts "
                  "late." if p["last_partly_from"] else "")
        st.caption((f"Spent so far, day by day, against {', '.join(named)}." if named
                    else "Spent so far, day by day. Comparisons appear as whole months are logged.")
                   + partly + (" The target line is its steady pace through the month." if target > 0 else "")
                   + " Hover to compare a day.")
        st.altair_chart(charts.running_total_chart(frame, order, daily.days_in(month),
                                                   p["day"] if p["is_partial"] else None, key, roles=roles),
                        use_container_width=True)

    # --- Where are we heading? (months) ---
    months = daily.months_frame(df, data, lens, since=since)
    if len(months) >= 2:
        with ui.card("heading"):
            st.subheader("Where are we heading?")
            refs = daily.month_references(df, data, lens, since=since, target=target)
            st.caption("Each month's total" + (" (this one so far: a hollow dot, never projected)"
                                               if p["is_partial"] else "")
                       + (", against " + " and ".join(f"the {n.lower()}" for n, _ in refs) if refs else "")
                       + ". The 12-month average and the same month last year appear once there's a year logged.")
            st.altair_chart(charts.months_chart(months, refs), use_container_width=True)

    with ui.card("where"):
        _where(picked, lens, month, p, key, targets)

    # --- Where the difference comes from ---
    if p["has_last"]:
        with ui.card("changes"):
            st.subheader("Where does the difference come from?")
            against_names = daily.comparison_options(df, data, since=since) or {previous: "last"}
            c1, c2 = st.columns([3, 2])
            first = next(iter(against_names))
            against_label = c1.segmented_control("Compare with", list(against_names), default=first,
                                                 key=f"{key}_daily_against") or first
            level = c2.segmented_control("Group by", ["Category", "Sub-category"], default="Category",
                                         key=f"{key}_daily_level") or "Category"
            against = against_names.get(against_label, "last")
            changes = daily.category_changes(picked, data, lens, against=against,
                                             level="primary_category" if level == "Category" else "sub_category",
                                             since=since)
            if changes.empty or not changes["change"].any():
                st.caption("No change by category to show.")
            else:
                st.markdown(md(daily.change_summary(changes, previous if against == "last"
                                                    else against_label.lower())))
                # What drove it: behaviour (day-to-day) or fixed costs.
                ui.kpi_lines(daily.cause_lines(picked, data, lens, against, since=since))
                moved = changes[changes["change"] != 0]
                st.altair_chart(charts.changes_chart(moved.head(TOP_CHANGES)), use_container_width=True)
                same = changes.loc[changes["change"] == 0, "name"]
                notes = [f"The {TOP_CHANGES} biggest moves of {len(moved)}."] if len(moved) > TOP_CHANGES else []
                if not same.empty:
                    notes.append(f"Unchanged: {', '.join(same)}.")
                if notes:
                    st.caption(" ".join(notes))

    with ui.card("biggest"):
        _biggest_days(df, lens, month, p, sources, token, filters, key)

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
