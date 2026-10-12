"""
Pure helpers for the Tracker's Joint account tab: turn one /joint/status
item into a chart frame and the sentences around it. No Streamlit import,
so they're unit-tested in tests/test_joint_shaping.py.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pandas as pd

from money import format_brl

THIS_MONTH = "This month"
USUAL = "Usual (last 3 full months)"


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def pace_frame(status: dict) -> pd.DataFrame:
    """Long frame for the cumulative chart: day, series, amount (float), amount_brl."""
    rows = []
    for d in status["days"]:
        for series, key in ((THIS_MONTH, "this_month"), (USUAL, "usual")):
            if d.get(key) is not None:
                rows.append({"day": d["day"], "series": series, "amount": float(Decimal(str(d[key]))),
                             "amount_brl": format_brl(d[key])})
    return pd.DataFrame(rows, columns=["day", "series", "amount", "amount_brl"])


def pace_gap(status: dict) -> Decimal | None:
    """This month so far minus the usual month by the same day, or None without history."""
    if status.get("usual_to_day") is None:
        return None
    return Decimal(str(status["spent_to_day"])) - Decimal(str(status["usual_to_day"]))


def pace_sentence(status: dict) -> str:
    day = ordinal(status["as_of_day"])
    spent = format_brl(status["spent_to_day"])
    gap = pace_gap(status)
    if gap is None:
        return (f"By the {day} you've spent {spent}. Not enough history yet: the usual pace needs at least "
                "one full month of spending on this account.")
    usual = format_brl(status["usual_to_day"])
    if gap > 0:
        return f"By the {day} you've spent {spent}, ▲ {format_brl(gap)} more than usual by now ({usual})."
    if gap < 0:
        return f"By the {day} you've spent {spent}, ▼ {format_brl(-gap)} less than usual by now ({usual})."
    return f"By the {day} you've spent {spent}, right on the usual pace."


def run_out_text(status: dict) -> str | None:
    """'Lasts until 20 December at this pace', or None when it can't be said."""
    if status.get("balance") is None:
        return None
    if Decimal(str(status["balance"])) <= 0:
        return "The account is empty."
    if not status.get("runs_out_on"):
        return "Nothing spent yet this month, so there's no pace to go by."
    runs_out = datetime.date.fromisoformat(status["runs_out_on"])
    year, month = map(int, status["month"].split("-"))
    if (runs_out.year, runs_out.month) > (year, month):
        return "At this pace the money lasts past the end of the month."
    return f"At this pace the money lasts until {runs_out.day} {runs_out.strftime('%B')}."


def counted_from_text(status: dict, tz) -> str:
    if status.get("balance") is None:
        return "Enter the balance your bank shows to start."
    if status.get("counted_from"):
        when = pd.Timestamp(status["counted_from"]).tz_convert(tz)
        return f"From the balance you entered on {when:%d/%m/%Y}, plus deposits, minus spending since."
    return "From your first deposit, minus spending since. Enter the bank's balance to correct it."
