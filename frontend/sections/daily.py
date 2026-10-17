"""
This month, day by day: is this month running ahead of last month and of
the usual month, by the same day, and where does the difference come
from? Filters first (what to count), then the answer (a hero card with its
running total) beside four equal cards, then one card per question, from
the whole month down to single days: how the month built up, where the
money goes (tap a category for what's inside), where the difference comes
from, which days cost most (calendars), what went on the biggest days (tap
a day for what was bought), and the weekday pattern.

On Our expenses it reads the shared endpoints; on My expenses
(show_view=True) a "Show" control picks shared, personal or both.

Shaping lives in daily_shaping (and filtering), the charts in
daily_charts; this module only wires them to widgets.
"""
from __future__ import annotations

import datetime
from html import escape
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

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
CARD_HEIGHT = 250
HERO_HEIGHT = 2 * CARD_HEIGHT + 16  # two cards and the gap between them
HERO_SPARK = 250
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
    """One legend for both calendars: the grey of an empty day, the green scale and today's outline."""
    swatch = "display:inline-block;border-radius:3px;vertical-align:middle"
    st.html(
        f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:0.45rem;font-size:0.8rem;color:{ui.INK_2}">'
        f'<span style="{swatch};width:14px;height:14px;background:{charts.EMPTY_DAY};border:1px solid {ui.LINE}">'
        f'</span><span>Nothing spent</span><span style="width:0.8rem"></span>'
        f"<span>{escape(format_brl(0))}</span>"
        f'<span style="{swatch};width:150px;height:10px;'
        f'background:linear-gradient(90deg,{charts.HEAT[0]},{charts.HEAT[1]})"></span>'
        f"<span>{escape(format_brl(top))} or more</span>"
        f'<span style="width:0.8rem"></span><span style="{swatch};width:14px;height:14px;border:2px solid {ui.INK}">'
        f"</span><span>Today</span></div>"
    )


def _expenses(sources: list[str], query: dict, token: str, lens: str, filters: filtering.Filters,
              with_date: bool) -> None:
    """The expenses behind a picked bar (a day, or a category's month), obeying the filters."""
    lists = [get_data(f"{ENDPOINTS[s][1]}?{urlencode(query)}", token, default=_FAILED) for s in sources]
    if any(items is _FAILED for items in lists):
        return
    items = [i for items in lists if isinstance(items, list) for i in items]
    exp = filtering.filter_rows(pd.DataFrame(items), filters) if items else pd.DataFrame()
    if exp.empty:
        st.caption("No expenses" + (" among what's being counted." if items else "."))
        return
    exp = exp.sort_values("transaction_timestamp", ascending=not with_date).copy()
    when = pd.to_datetime(exp["transaction_timestamp"], utc=True).dt.tz_convert(SAO_PAULO)
    exp["when"] = when.dt.strftime("%a %d %b · %H:%M" if with_date else "%H:%M")
    exp["what"] = exp["primary_category"] + " › " + exp["sub_category"]
    exp["payment"] = [f"{m} · {i}" if i else (m or "") for m, i in zip(exp["payment_method"], exp["institution"])]
    for col in ("price", "mine"):
        exp[col] = exp[col].map(format_brl)
    amounts = ["price", "mine"] if lens == "Household" else ["mine", "price"]
    names = {"when": "When", "what": "What", "price": "Price", "mine": "My share", "payment": "Paid with",
             "paid_by": "Paid by"}
    st.dataframe(exp[["when", "what", *amounts, "payment", "paid_by"]].rename(columns=names),
                 hide_index=True, width="stretch")


def _pick_chart(frame: pd.DataFrame, name: str, widget_key: str) -> str | None:
    """
    Draw a ranked clickable bar chart and return the picked bar's key (the
    biggest until one is tapped). The widget key carries the bars on show,
    so a filter that changes them starts afresh on the biggest.
    """
    default = frame["key"].iloc[0] if not frame.empty else None
    stamp = abs(hash(tuple(frame["key"]))) % 10**8
    event = st.altair_chart(charts.pick_bars(frame, name, default), use_container_width=True,
                            on_select="rerun", selection_mode=name, key=f"{widget_key}_{stamp}")
    clicked = event.get("selection", {}).get(name) if event else None
    return daily.picked_key(frame, clicked)


def _numbers(p: dict, hero: dict, cards: list[dict], df, data, lens: str, since, hist, this_cal, month: str) -> None:
    """The hero card on the left, four equal cards in a 2 x 2 grid on the right."""
    left, right = st.columns([2, 3], gap="medium")
    with left, ui.card("hero", height=HERO_HEIGHT):
        ui.kpi(hero["label"], hero["amount"], hero["lines"], hero=True,
               help="Everything counted so far this month. The chart is this month's running total (green) "
                    "over last month's (grey).")
        frame = daily.running_frame(df, data, lens, since=since, with_usual=False)
        st.altair_chart(charts.spark_running(frame, daily.series_order(data), daily.days_in(month), HERO_SPARK),
                        use_container_width=True)
    with right:
        cols = [*st.columns(2), *st.columns(2)]
        for col, card in zip(cols, cards):
            with col, ui.card(card["key"], height=CARD_HEIGHT):
                ui.kpi(card["label"], card["value"], card["lines"], help=card["help"])
                chart = _card_chart(card, p, hist, this_cal)
                if chart is None:
                    ui.empty_chart(EMPTY.get(card["key"], "Nothing to draw yet."), charts.SPARK_HEIGHT)
                else:
                    st.altair_chart(chart, use_container_width=True)
    st.caption("▲ more, ▼ less than the comparison, always over the same days of each month. In the bars, green "
               "is the month in question and grey the others; a dashed line is the usual. Tap ⓘ for what each "
               "card means, or hover a chart for its numbers.")


def render(token: str, lens: str, key: str, show_view: bool = False) -> None:
    today = datetime.datetime.now(SAO_PAULO).date()
    current = today.strftime("%Y-%m")

    pick_col, _ = st.columns([1, 2])
    month = pick_col.selectbox("Month", shape.month_options(current, 12), format_func=shape.month_label,
                               key=f"{key}_daily_month")
    row = FilterRow(f"{key}_daily", show_view=show_view)
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

    _numbers(p, daily.headline(p, filtering.note(filters), started=daily.logging_started(rows)),
             daily.cards(p), df, data, lens, since, hist, this_cal, month)

    # --- How the month built up ---
    with ui.card("running"):
        st.subheader("How is the month building up?")
        st.caption(f"Running total, day by day. {previous} is complete; the dashed line is the usual month "
                   "(once there are three months to average). Hover anywhere to compare that day.")
        st.altair_chart(
            charts.running_total_chart(daily.running_frame(df, data, lens, since=since), daily.series_order(data),
                                       daily.days_in(month), p["day"] if p["is_partial"] else None, key),
            use_container_width=True,
        )

    # --- Where the money goes ---
    with ui.card("where"):
        st.subheader(f"Where is the money going in {daily.month_name(month)}?")
        mix = daily.ranked(picked, lens, "primary_category", month=month)
        if mix.empty:
            st.caption("Nothing spent yet this month.")
        else:
            st.caption("Each category's share of the month so far. Tap a category to see what's inside it.")
            left, right = st.columns(2, gap="medium")
            with left:
                category = _pick_chart(mix, "category", f"{key}_daily_category")
            with right:
                share = mix.set_index("key").loc[category]
                st.markdown(md(f"**Inside {category}: {share['amount_brl']}** ({share['share']:.0%} of the month)"))
                inside = daily.ranked(picked[picked["primary_category"] == category], lens, "sub_category",
                                      month=month)
                st.altair_chart(charts.breakdown_bars(inside), use_container_width=True)
                with st.expander(f"The expenses in {category}"):
                    _expenses(sources, {"month": month, "primary_category": category}, token, lens, filters,
                              with_date=True)

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
                notes.append("Hover a bar for both amounts.")
                st.caption(" ".join(notes))

    # --- Which days cost most ---
    with ui.card("calendar"):
        st.subheader("Which days cost the most?")
        st.caption("Each day shaded by what was spent: the darker the green, the more. Both months share one "
                   "scale, whose darkest shade is a typical big day, so one large payment doesn't wash out the "
                   "rest; hover a day for the exact amount and its biggest category.")
        last_cal = daily.calendar_frame(df, p["previous"], lens, today)
        top = daily.calendar_scale_max(this_cal, last_cal)
        c1, c2 = st.columns(2)
        c1.altair_chart(charts.calendar_chart(this_cal, top, shape.month_label(month)), use_container_width=False)
        c2.altair_chart(charts.calendar_chart(last_cal, top, shape.month_label(p["previous"])),
                        use_container_width=False)
        _calendar_legend(top)


    # --- The biggest days ---
    with ui.card("biggest"):
        st.subheader(f"What went on the biggest days of {daily.month_name(month)}?")
        days = daily.biggest_days(df, month, lens)
        if days.empty:
            st.caption("Nothing spent yet this month.")
        else:
            st.caption("The month's biggest days, each with its biggest category. Tap a day to see what was bought.")
            left, right = st.columns(2, gap="medium")
            with left:
                day = _pick_chart(days, "day", f"{key}_daily_day")
            with right:
                chosen = days.set_index("key").loc[day]
                when = datetime.date.fromisoformat(day)
                st.markdown(md(f"**{daily.WEEKDAY_NAMES[when.weekday()]} {when.day} {when:%B}: "
                               f"{chosen['amount_brl']}** ({chosen['share']:.0%} of the month)"))
                st.altair_chart(charts.breakdown_bars(daily.ranked(picked, lens, "item", date=day)),
                                use_container_width=True)
                _expenses(sources, {"day": day}, token, lens, filters, with_date=False)
        with st.expander("Every day's numbers"):
            this = daily.daily_amounts(df, month, lens)
            last = daily.daily_amounts(df, p["previous"], lens)
            table = pd.DataFrame({"Day": this.index})
            table[daily.month_name(month)] = [format_brl(v) if (not p["is_partial"] or d <= p["day"]) else ""
                                              for d, v in this.items()]
            table[previous] = [format_brl(last.get(d, 0.0)) if d in last.index else "" for d in this.index]
            st.dataframe(table, hide_index=True, width="stretch")

    # --- Patterns ---
    with ui.card("weekdays"):
        st.subheader("Which weekdays cost most?")
        start = rows["date"].min()  # the first day anything was logged, whatever is filtered
        profile = daily.weekday_profile(df, data, lens, today, since=start)
        if profile.empty or profile["average"].max() == 0:
            st.caption("Not enough days yet.")
        else:
            busiest = profile.loc[profile["average"].idxmax()]
            st.caption(md(f"Average spent per weekday since {start:%d %b %Y}, quiet days included. "
                          f"{daily.WEEKDAY_NAMES[int(busiest['weekday'])]}s cost most: "
                          f"{busiest['average_brl']} on average."))
            st.altair_chart(charts.weekday_chart(profile), use_container_width=True)
