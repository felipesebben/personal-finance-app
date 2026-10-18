"""
Shaping /analytics/{shared,personal}/daily for the "This month" view: how
this month is going day by day against last month and the usual month,
and where a difference comes from.

No Streamlit import, so it's unit-tested in tests/test_daily_shaping.py;
sections/daily.py wires it to widgets and daily_charts draws it.
Amounts are floats for Altair; every displayed amount goes through
format_brl.

The API sends one row per day x category x cost type x nature, so the page
can narrow what it counts (filtering.py: day-to-day costs only, without
one-offs like IPVA, some categories) before anything is added up:
`rows_frame` reads them, filtering.filter_rows narrows them, `by_day` sums
them per day.

Two comparisons, both "by the same day" while a month is in progress:
- last month, read in full (it's finished), and
- the usual month: the average of the three months before, once the
  data reaches back that far (zero months count as zero, as in the
  monthly view's 3-month average).
"""
from __future__ import annotations

import calendar
import datetime

import pandas as pd

import analytics_shaping as shape
from joint_shaping import ordinal
from money import format_brl

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
USUAL = "Usual (3-month average)"

ROW_COLUMNS = ["date", "month", "day", "primary_category", "sub_category", "cost_type", "nature",
               "household", "mine", "count", "source"]
DAY_COLUMNS = ["date", "month", "day", "household", "mine", "count", "top_category"]


def month_name(month: str) -> str:
    """'2026-10' -> 'October'."""
    return datetime.date(int(month[:4]), int(month[5:]), 1).strftime("%B")


def short_month(month: str) -> str:
    """'2026-10' -> 'Oct'."""
    return datetime.date(int(month[:4]), int(month[5:]), 1).strftime("%b")


def days_in(month: str) -> int:
    return calendar.monthrange(int(month[:4]), int(month[5:]))[1]


# --- rows, filters and days -----------------------------------------------

def rows_frame(payload: dict | None) -> pd.DataFrame:
    """
    The API's rows: one per day x category x cost type x nature. `source`
    says which endpoint a row came from when payloads are merged ("shared"
    or "personal"), else "".
    """
    if not payload or not payload.get("rows"):
        return pd.DataFrame(columns=ROW_COLUMNS)
    df = pd.DataFrame(payload["rows"])
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.strftime("%Y-%m")
    df["day"] = df["date"].dt.day
    for col in ("household", "mine"):
        df[col] = pd.to_numeric(df[col]).astype(float)
    df["count"] = df["count"].astype(int)
    if "source" not in df:
        df["source"] = ""
    return df[ROW_COLUMNS]


def by_day(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per day with spending: date, month, day, household, mine, count and its top category."""
    if rows.empty:
        return pd.DataFrame(columns=DAY_COLUMNS)
    per_category = rows.groupby(["date", "primary_category"], as_index=False)["household"].sum()
    # Most spent wins; a tie goes to the alphabetically first category.
    top = (per_category.sort_values(["date", "household", "primary_category"], ascending=[True, False, True])
           .drop_duplicates("date").set_index("date")["primary_category"])
    days = rows.groupby(["date", "month", "day"], as_index=False)[["household", "mine", "count"]].sum()
    days["top_category"] = days["date"].map(top)
    return days[DAY_COLUMNS].sort_values("date").reset_index(drop=True)


def to_frame(payload: dict | None) -> pd.DataFrame:
    """Everything in the payload, per day (no filter)."""
    return by_day(rows_frame(payload))


TRACKED_BY_DAY = 7  # a month counts as logged in full when logging had started by its 7th


def tracked_since(rows: pd.DataFrame) -> str | None:
    """
    The first month logged in full, from the rows before any filter: the
    first expense's month when it falls in that month's first week (a
    quiet first few days are normal), else the month after. Earlier months
    are left out of every comparison, so a month whose logging started on
    the 29th doesn't read as a cheap month.
    """
    if rows.empty:
        return None
    first = rows["date"].min()
    month = first.strftime("%Y-%m")
    return month if first.day <= TRACKED_BY_DAY else shape.shift_month(month, 1)


def logging_started(rows: pd.DataFrame) -> datetime.date | None:
    return None if rows.empty else rows["date"].min().date()


def daily_amounts(df: pd.DataFrame, month: str, lens: str) -> pd.Series:
    """Spending on each day 1..n of `month`, zero where nothing was spent."""
    days = pd.RangeIndex(1, days_in(month) + 1, name="day")
    if df.empty:
        return pd.Series(0.0, index=days)
    col = shape.lens_column(lens)
    this = df[df["month"] == month].groupby("day")[col].sum()
    return this.reindex(days, fill_value=0.0).astype(float)


def _cumulative_to(df: pd.DataFrame, month: str, lens: str, day: int) -> float:
    """Spent in `month` from the 1st to `day` (its last day, if shorter)."""
    amounts = daily_amounts(df, month, lens)
    return round(float(amounts.loc[:min(day, len(amounts))].sum()), 2)


# --- the comparisons --------------------------------------------------------

def usual_months(df: pd.DataFrame, data: dict, n: int = 3, since: str | None = None,
                 month: str | None = None) -> list[str]:
    """
    The n months before `month` (the selected one by default), when the
    window and the tracking (`since`, else the data) both reach back that
    far; else [].
    """
    month = month or data["month"]
    since = since or (None if df.empty else df["month"].min())
    wanted = [shape.shift_month(month, -k) for k in range(1, n + 1)]
    if since is None or any(m not in data["months"] for m in wanted) or min(wanted) < since:
        return []
    return wanted


def usual_cumulative(df: pd.DataFrame, data: dict, lens: str, since: str | None = None) -> pd.Series | None:
    """
    The usual month's running total by day 1..n of the selected month: the
    average of the three months before. A shorter month has finished by its
    last day, so its total carries on. None without enough history.
    """
    months = usual_months(df, data, since=since)
    if not months:
        return None
    n = days_in(data["month"])
    curves = []
    for m in months:
        c = daily_amounts(df, m, lens).cumsum()
        curves.append(c.reindex(pd.RangeIndex(1, n + 1, name="day")).ffill().fillna(0.0))
    return sum(curves) / len(curves)


def history(df: pd.DataFrame, data: dict, lens: str, since: str | None = None) -> pd.DataFrame:
    """
    Every tracked month of the window, oldest first: its whole total, what
    it had spent by the selected day (`to_day`) and that as a daily average
    (`per_day`). The selected month's total is what it has so far.
    """
    month, day = data["month"], data["as_of_day"]
    since = since or (None if df.empty else df["month"].min())
    rows = []
    for m in data["months"]:
        if since is None or m < since:
            continue
        amounts = daily_amounts(df, m, lens)
        to_day = _cumulative_to(df, m, lens, day)
        rows.append({"month": m, "label": short_month(m), "total": round(float(amounts.loc[:day].sum())
                                                                            if m == month else amounts.sum(), 2),
                     "to_day": to_day, "per_day": round(to_day / min(day, len(amounts)), 2),
                     "is_selected": m == month})
    out = pd.DataFrame(rows, columns=["month", "label", "total", "to_day", "per_day", "is_selected"])
    for col in ("total", "to_day", "per_day"):
        out[f"{col}_brl"] = out[col].map(format_brl)
    return out


def pace(df: pd.DataFrame, data: dict, lens: str, since: str | None = None) -> dict:
    """
    The numbers behind the headline and the cards: spent so far (to `day`),
    the same days of last month and of the usual month, whole-month and
    per-day figures, and what's left to spend per day to stay within the
    usual month (or last month, before there's a usual month). `since` is
    the first tracked month (rows before filtering); the data's own first
    month otherwise.
    """
    month, day = data["month"], data["as_of_day"]
    since = since or (None if df.empty else df["month"].min())
    previous = shape.shift_month(month, -1)
    n = days_in(month)
    this = daily_amounts(df, month, lens)
    last = daily_amounts(df, previous, lens)
    usual = usual_cumulative(df, data, lens, since=since)
    usual_of = usual_months(df, data, since=since)
    so_far = round(float(this.loc[:day].sum()), 2)
    has_last = since is not None and since <= previous
    last_total = round(float(last.sum()), 2)
    usual_total = None if usual is None else round(float(usual.iloc[-1]), 2)
    usual_by_day = None if usual is None else round(float(usual.loc[day]), 2)

    # Last month against its own usual (the three months before it), to say whether it was unusual.
    last_usual_of = usual_months(df, data, since=since, month=previous)
    last_usual = (round(sum(float(daily_amounts(df, m, lens).sum()) for m in last_usual_of) / 3, 2)
                  if last_usual_of else None)

    # What's left per day to end at the reference: the usual month, else last month.
    if usual_total is not None:
        reference, reference_name = usual_total, "usual"
    elif has_last:
        reference, reference_name = last_total, month_name(previous)
    else:
        reference, reference_name = None, None
    days_left = n - day if data["is_partial"] else 0
    return {
        "month": month, "previous": previous, "day": day, "days": n, "is_partial": data["is_partial"],
        "since": since,
        "so_far": so_far,
        "last_by_day": round(float(last.loc[:min(day, len(last))].sum()), 2),
        "last_total": last_total,
        "last_usual": last_usual,
        "has_last": has_last,
        "usual_by_day": usual_by_day,
        "usual_total": usual_total,
        "usual_of": sorted(usual_of),
        # The rest of the month as usual: what's spent so far plus the usual month's remaining days.
        "heading_for": (round(so_far + usual_total - usual_by_day, 2)
                        if usual_total is not None and data["is_partial"] else None),
        "per_day": round(so_far / day, 2) if day else 0.0,
        "last_per_day": round(float(last.loc[:min(day, len(last))].sum()) / min(day, len(last)), 2),
        "usual_per_day": None if usual_by_day is None else round(usual_by_day / day, 2),
        "days_with_spending": int((this.loc[:day] > 0).sum()),
        "days_left": days_left,
        "reference": reference,
        "reference_name": reference_name,
        "allowance": (round((reference - so_far) / days_left, 2)
                      if reference is not None and days_left and so_far < reference else None),
    }


def _versus(change: float, previous: float, against: str) -> tuple[str, str | None]:
    """('▲ R$ 150,00 (12%) more than September', 'more'); the tone colours the line."""
    if round(change, 2) == 0:
        return f"The same as {against}", None
    word, arrow = ("more", "▲") if change > 0 else ("less", "▼")
    pct = f" ({abs(change) / previous:.0%})" if previous else ""
    return f"{arrow} {format_brl(abs(change))}{pct} {word} than {against}", word


def headline(p: dict, focus: str = "", started: datetime.date | None = None) -> dict:
    """
    The hero card, leading with the answer: label ("Spent so far in
    October"), amount, and lines of (text, tone) where tone is "more",
    "less" or None, e.g. "▲ R$ 210,00 (13%) more than September by the
    17th". `focus` (filtering.note) is added to the label when something is
    filtered out; `started` (logging_started) explains a missing comparison.
    """
    name, previous = month_name(p["month"]), month_name(p["previous"])
    label = f"Spent so far in {name}" if p["is_partial"] else f"Spent in {name}"
    if focus:
        label += f" · {focus}"
    by = f" by the {ordinal(p['day'])}" if p["is_partial"] else ""
    lines = []
    if p["has_last"]:
        lines.append(_versus(p["so_far"] - p["last_by_day"], p["last_by_day"], f"{previous}{by}"))
    if p["usual_by_day"] is not None:
        lines.append(_versus(p["so_far"] - p["usual_by_day"], p["usual_by_day"], f"usual{by}"))
    if p["heading_for"] is not None:
        lines.append((f"Heading for about {format_brl(p['heading_for'])} if the rest of {name} goes as usual", None))
    if not lines:
        start = f"Logging started on {started.day} {started:%B}, so c" if started else "C"
        first = (f"in {month_name(shape.shift_month(p['since'], 1))}, against {month_name(p['since'])}"
                 if p.get("since") else "once a whole month has been logged")
        lines.append((f"Nothing to compare with yet. {start}omparisons start {first}.", None))
    return {"label": label, "amount": format_brl(p["so_far"]), "lines": lines}


# --- the four cards -----------------------------------------------------------

def cards(p: dict) -> list[dict]:
    """
    The cards under the headline, each {key, label, value, lines, help}:
    per day, last month, the usual month and what's left per day (or, for
    a finished month, days with spending). Lines are (text, tone) as in
    headline(); each card's sparkline comes from history() in the section.
    """
    previous = month_name(p["previous"])
    by = f"by the {ordinal(p['day'])}" if p["is_partial"] else "over the month"
    out = []

    lines = []
    if p["usual_per_day"] is not None:
        lines.append(_versus(p["per_day"] - p["usual_per_day"], p["usual_per_day"], "usual"))
    if p["has_last"]:
        lines.append((f"{previous}: {format_brl(p['last_per_day'])} a day {by}", None))
    out.append({"key": "per_day", "label": "Per day so far" if p["is_partial"] else "Per day",
                "value": format_brl(p["per_day"]), "lines": lines,
                "help": "The average spent per day this month, against the same days of earlier months. "
                        "The bars are each month's average over the same days."})

    lines = []
    if p["has_last"]:
        if p["is_partial"]:
            lines.append((f"{format_brl(p['last_by_day'])} of it {by}", None))
        if p["last_usual"] is not None:
            lines.append(_versus(p["last_total"] - p["last_usual"], p["last_usual"], "its usual"))
    out.append({"key": "last", "label": f"Last month · {previous}",
                "value": format_brl(p["last_total"]) if p["has_last"] else "—",
                "lines": lines or [("Not logged in full, so not compared.", None)],
                "help": f"All of {previous}, finished. \"Its usual\" is the average of the three months before it. "
                        "The bars are each month's total."})

    if p["usual_total"] is not None:
        months = p["usual_of"]
        span = f"{month_name(months[0])}–{month_name(months[-1])}"
        lines = [(f"The average of {span}", None)]
        if p["is_partial"]:
            lines.append((f"{format_brl(p['usual_by_day'])} of it {by}", None))
        value = format_brl(p["usual_total"])
    else:
        lines, value = [("Needs three months of history.", None)], "—"
    out.append({"key": "usual", "label": "Usual month", "value": value, "lines": lines,
                "help": "The average of the three months before this one: what a normal month costs. "
                        "The bars are those three months, the line their average."})

    if p["is_partial"] and p["reference"] is not None and p["days_left"]:
        ref = "the usual month" if p["reference_name"] == "usual" else p["reference_name"]
        spent_share, time_share = p["so_far"] / p["reference"] if p["reference"] else 0.0, p["day"] / p["days"]
        spent = f"{spent_share:.0%}" if spent_share < 2 else f"{spent_share:.1f}×".replace(".", ",")
        pace_line = (f"{spent} of {ref} spent, {time_share:.0%} of the month gone",
                     "more" if spent_share > time_share + 0.005 else "less" if spent_share < time_share - 0.005 else None)
        if p["allowance"] is not None:
            out.append({"key": "allowance", "label": f"To stay within {ref}",
                        "value": f"{format_brl(p['allowance'])} a day",
                        "lines": [(f"For the {p['days_left']} days after today", None), pace_line],
                        "help": f"What's left of {ref} ({format_brl(p['reference'])}) divided by the days left. "
                                "The bar is how much of it is spent; the tick, how much of the month has gone."})
        else:
            out.append({"key": "allowance", "label": f"Past {ref}",
                        "value": format_brl(p["so_far"] - p["reference"]),
                        "lines": [(f"▲ over {ref}, with {p['days_left']} days to go", "more"), pace_line],
                        "help": f"Spent so far beyond {ref} ({format_brl(p['reference'])})."})
    else:
        out.append({"key": "days", "label": "Days with spending", "value": f"{p['days_with_spending']} of {p['day']}",
                    "lines": [("Days with at least one expense", None)],
                    "help": "The bars are each day's spending."})
    return out


# --- where the difference comes from -----------------------------------------

def category_changes(rows: pd.DataFrame, data: dict, lens: str, against: str = "last",
                     level: str = "primary_category", since: str | None = None) -> pd.DataFrame:
    """
    This month so far against last month (`against="last"`) or the usual
    month (`"usual"`) by the same day, per category (or "Primary ›
    sub" with level="sub_category"): name, now, then, change and their
    text, biggest move first. Rows that are zero on both sides are dropped.
    """
    columns = ["name", "now", "then", "change", "now_brl", "then_brl", "change_brl", "direction"]
    if rows.empty:
        return pd.DataFrame(columns=columns)
    month, day = data["month"], data["as_of_day"]
    col = shape.lens_column(lens)
    names = rows["primary_category"] if level == "primary_category" else (
        rows["primary_category"] + " › " + rows["sub_category"])
    frame = rows.assign(name=names)
    if against == "usual":
        months = usual_months(by_day(rows), data, since=since)
        if not months:
            return pd.DataFrame(columns=columns)
    else:
        months = [shape.shift_month(month, -1)]

    def to_day(m):
        cut = min(day, days_in(m))
        sub = frame[(frame["month"] == m) & (frame["day"] <= cut)]
        return sub.groupby("name")[col].sum()

    now = to_day(month)
    # Summed per name across the months (a category missing from one counts as zero), then averaged.
    then = pd.concat([to_day(m) for m in months]).groupby(level=0).sum() / len(months)
    out = pd.concat([now.rename("now"), then.rename("then")], axis=1).fillna(0.0).astype(float).round(2)
    out = out[(out["now"] != 0) | (out["then"] != 0)].reset_index().rename(columns={"index": "name"})
    out["change"] = (out["now"] - out["then"]).round(2)
    out = out.reindex(out["change"].abs().sort_values(ascending=False, kind="stable").index).reset_index(drop=True)
    out["now_brl"] = out["now"].map(format_brl)
    out["then_brl"] = out["then"].map(format_brl)
    out["change_brl"] = [("▲ +" if c > 0 else "▼ " if c < 0 else "") + format_brl(c) for c in out["change"]]
    out["direction"] = ["more" if c > 0 else "less" if c < 0 else "same" for c in out["change"]]
    return out[columns]


def change_summary(changes: pd.DataFrame, against: str, n: int = 3) -> str:
    """'▲ R$ 420,00 more than September by the same day. Biggest moves: Food ▲ R$ 300,00, Pets ▲ R$ 180,00.'"""
    if changes.empty:
        return "Nothing to compare yet."
    total = round(float(changes["change"].sum()), 2)
    text, _ = _versus(total, float(changes["then"].sum()), f"{against} by the same day")
    moves = changes[changes["change"] != 0].head(n)
    if moves.empty:
        return f"{text}, in every category."
    listed = ", ".join(f"{name} {'▲' if c > 0 else '▼'} {format_brl(abs(c))}"
                       for name, c in zip(moves["name"], moves["change"]))
    return f"{text}. Biggest moves: {listed}."


# --- the running total and the calendars --------------------------------------

def running_frame(df: pd.DataFrame, data: dict, lens: str, since: str | None = None,
                  with_usual: bool = True) -> pd.DataFrame:
    """
    The running-total chart's long frame (day, series, amount, amount_brl):
    this month up to today, last month in full, and the usual month when
    there's enough history (and `with_usual`).
    """
    month, day = data["month"], data["as_of_day"]
    since = since or (None if df.empty else df["month"].min())
    previous = shape.shift_month(month, -1)
    this_label, last_label, _ = series_order(data)
    rows = []
    this = daily_amounts(df, month, lens).cumsum().loc[:day]
    rows += [(d, this_label, v) for d, v in this.items()]
    if since is not None and since <= previous:
        last = daily_amounts(df, previous, lens).cumsum()
        rows += [(d, last_label, v) for d, v in last.items()]
    usual = usual_cumulative(df, data, lens, since=since) if with_usual else None
    if usual is not None:
        rows += [(d, USUAL, v) for d, v in usual.items()]
    out = pd.DataFrame(rows, columns=["day", "series", "amount"])
    out["amount"] = out["amount"].astype(float).round(2)
    out["amount_brl"] = out["amount"].map(format_brl)
    return out


def series_order(data: dict) -> list[str]:
    """Legend and colour order: this month, last month, usual."""
    month = data["month"]
    return [f"{month_name(month)}{' (so far)' if data['is_partial'] else ''}",
            month_name(shape.shift_month(month, -1)), USUAL]


def calendar_scale_max(*calendars: pd.DataFrame, quantile: float = 0.9) -> float:
    """
    Where the calendar's darkest green starts: a typical big day (the 90th
    percentile of days with spending, across the calendars shown), so one
    large payment doesn't wash every other day out to the palest shade.
    """
    amounts = pd.concat([c["amount"] for c in calendars]) if calendars else pd.Series(dtype=float)
    spent = amounts[amounts > 0]
    return round(float(spent.quantile(quantile)), 2) if not spent.empty else 1.0


def calendar_frame(df: pd.DataFrame, month: str, lens: str, today: datetime.date) -> pd.DataFrame:
    """
    One row per day of `month`, laid out as a calendar: `week` (row, from
    0) and `weekday` (0 = Monday). `state` is past, today or future;
    future days carry no amount.
    """
    year, mon = int(month[:4]), int(month[5:])
    first = datetime.date(year, mon, 1)
    offset = first.weekday()
    amounts = daily_amounts(df, month, lens)
    this = df[df["month"] == month].set_index("day") if not df.empty else pd.DataFrame()
    rows = []
    for d in range(1, days_in(month) + 1):
        date = datetime.date(year, mon, d)
        state = "future" if date > today else "today" if date == today else "past"
        amount = 0.0 if state == "future" else float(amounts.loc[d])
        count = int(this.loc[d, "count"]) if d in this.index and state != "future" else 0
        top = this.loc[d, "top_category"] if d in this.index and state != "future" else ""
        rows.append({
            "date": date.isoformat(), "day": d, "week": (offset + d - 1) // 7, "weekday": date.weekday(),
            "weekday_name": WEEKDAYS[date.weekday()], "amount": round(amount, 2), "amount_brl": format_brl(amount),
            "count": count, "top_category": top, "state": state,
            "label": f"{WEEKDAY_NAMES[date.weekday()]} {d} {date:%B}",
        })
    return pd.DataFrame(rows)


# --- patterns -----------------------------------------------------------------

def weekday_profile(df: pd.DataFrame, data: dict, lens: str, today: datetime.date,
                    since: datetime.date | None = None) -> pd.DataFrame:
    """
    Average spending per weekday, over every day from `since` (the first
    day with spending, by default) up to today, days with nothing counting
    as zero, so a weekday that's usually quiet reads as quiet. Empty
    without data.
    """
    if df.empty:
        return pd.DataFrame(columns=["weekday", "weekday_name", "average", "average_brl", "days"])
    col = shape.lens_column(lens)
    last_month = data["month"]
    end = min(today, datetime.date(int(last_month[:4]), int(last_month[5:]), days_in(last_month)))
    start = pd.Timestamp(since) if since is not None else df["date"].min()
    days = pd.date_range(start, pd.Timestamp(end), freq="D")
    totals = df.groupby("date")[col].sum().reindex(days, fill_value=0.0)
    frame = pd.DataFrame({"weekday": totals.index.weekday, "amount": totals.values})
    grouped = frame.groupby("weekday")["amount"].agg(["mean", "size"]).reindex(range(7), fill_value=0)
    out = pd.DataFrame({
        "weekday": range(7), "weekday_name": WEEKDAYS,
        "average": grouped["mean"].astype(float).round(2).values, "days": grouped["size"].astype(int).values,
    })
    out["average_brl"] = out["average"].map(format_brl)
    return out


# --- where the money goes ------------------------------------------------------

RANKED_COLUMNS = ["key", "name", "amount", "amount_brl", "share", "text"]


def tip_text(amount: float, share: float) -> str:
    """What a bar says at its tip: 'R$ 4.135 · 59%'."""
    return f"{shape.short_brl(amount)} · {share:.0%}"


def ranked(rows: pd.DataFrame, lens: str, by: str, month: str | None = None,
           date: str | None = None) -> pd.DataFrame:
    """
    What was spent per `by` (primary_category, sub_category, or "item" =
    "Primary › sub") in `month` or on `date` (YYYY-MM-DD), biggest first (a
    tie goes to the name): key (= name), amount, its share of the total and
    the text at the bar's tip, "R$ 1.234 · 32%". Empty when nothing was spent.
    """
    if rows.empty:
        return pd.DataFrame(columns=RANKED_COLUMNS)
    col = shape.lens_column(lens)
    sub = rows.assign(item=rows["primary_category"] + " › " + rows["sub_category"]) if by == "item" else rows
    if month is not None:
        sub = sub[sub["month"] == month]
    if date is not None:
        sub = sub[sub["date"] == pd.Timestamp(date)]
    totals = sub.groupby(by)[col].sum().round(2)
    totals = totals[totals > 0]
    if totals.empty:
        return pd.DataFrame(columns=RANKED_COLUMNS)
    out = totals.rename("amount").rename_axis("name").reset_index()
    out = out.sort_values(["amount", "name"], ascending=[False, True], ignore_index=True)
    out["key"] = out["name"]
    out["share"] = out["amount"] / out["amount"].sum()
    out["amount_brl"] = out["amount"].map(format_brl)
    out["text"] = [tip_text(a, s) for a, s in zip(out["amount"], out["share"])]
    return out[RANKED_COLUMNS]


def biggest_days(df: pd.DataFrame, month: str, lens: str, n: int = 8) -> pd.DataFrame:
    """
    The month's n biggest days, biggest first (a tie goes to the earlier
    day): key (YYYY-MM-DD), name ("Fri 10 Oct"), amount, its share of the
    month so far, the day's top category, and the text at the bar's tip,
    "R$ 812 · Food" (its biggest category), short enough for a phone.
    """
    columns = [*RANKED_COLUMNS, "top_category", "count"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    col = shape.lens_column(lens)
    month_rows = df[(df["month"] == month) & (df[col] > 0)]
    if month_rows.empty:
        return pd.DataFrame(columns=columns)
    total = float(month_rows[col].sum())
    this = month_rows.sort_values([col, "date"], ascending=[False, True]).head(n)
    out = pd.DataFrame({
        "key": [d.date().isoformat() for d in this["date"]],
        "name": [f"{WEEKDAYS[d.weekday()]} {d.day} {d:%b}" for d in this["date"]],
        "amount": this[col].round(2).values,
        "top_category": this["top_category"].values,
        "count": this["count"].astype(int).values,
    })
    out["share"] = out["amount"] / total
    out["amount_brl"] = out["amount"].map(format_brl)
    out["text"] = [f"{shape.short_brl(a)} · {c}" for a, c in zip(out["amount"], out["top_category"])]
    return out[columns]


def day_items(items: list[dict], lens: str, tz) -> pd.DataFrame:
    """
    A day's expenses (an /analytics/.../expenses list, already filtered) as
    bars, biggest first: name ("Groceries · 14:30", unique), amount, share
    of the day, the text at the tip, and who paid and how for the tooltip.
    """
    columns = ["key", "name", "amount", "amount_brl", "share", "text", "detail"]
    if not items:
        return pd.DataFrame(columns=columns)
    col = "price" if lens == "Household" else "mine"
    frame = pd.DataFrame(items)
    frame["amount"] = pd.to_numeric(frame[col]).astype(float).round(2)
    frame = frame[frame["amount"] > 0]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    when = pd.to_datetime(frame["transaction_timestamp"], utc=True).dt.tz_convert(tz).dt.strftime("%H:%M")
    # A sub-category named like a category ("Pets › Food") keeps its category, so it isn't read as Food.
    clash = set(frame["primary_category"])
    what = [f"{c} › {sub}" if sub in clash and sub != c else sub
            for c, sub in zip(frame["primary_category"], frame["sub_category"])]
    frame["name"] = pd.Series(what, index=frame.index) + " · " + when
    frame = frame.sort_values(["amount", "name"], ascending=[False, True], ignore_index=True)
    # Two purchases of the same thing at the same minute still need their own bar.
    frame["name"] = frame["name"] + frame.groupby("name").cumcount().map(lambda i: f" ({i + 1})" if i else "")
    frame["key"] = frame["name"]
    frame["share"] = frame["amount"] / frame["amount"].sum()
    frame["amount_brl"] = frame["amount"].map(format_brl)
    frame["text"] = [tip_text(a, s) for a, s in zip(frame["amount"], frame["share"])]
    paid = [f"{m} · {i}" if i else (m or "") for m, i in zip(frame.get("payment_method", ""), frame.get("institution", ""))]
    frame["detail"] = [f"{p}, paid by {who}" if who else p for p, who in zip(paid, frame.get("paid_by", ""))]
    return frame[columns]
