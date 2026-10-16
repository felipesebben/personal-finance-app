"""
The login briefing on Home: a few sentences on how this month is going,
built from numbers the API already computes. No Streamlit import, so it's
unit-tested in tests/test_briefing.py; sections/briefing.py fetches and
renders.

Every line is optional: one with nothing to say is left out.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pandas as pd

import analytics_shaping as shape
from joint_shaping import ordinal, run_out_text
from money import format_brl


def month_name(month: str) -> str:
    """'2026-10' -> 'October'."""
    return datetime.date(int(month[:4]), int(month[5:]), 1).strftime("%B")


def _versus(change: float, against: str) -> str:
    if round(change, 2) == 0:
        return f"the same as {against}"
    word = "more" if change > 0 else "less"
    arrow = "▲" if change > 0 else "▼"
    return f"{arrow} {format_brl(abs(change))} {word} than {against}"


def spending_line(label: str, df: pd.DataFrame, data: dict, lens: str, top_category: bool = False) -> str | None:
    """
    "Shared: R$ 1.840,00 so far in October, ▲ R$ 210,00 more than usual by
    the 16th. Biggest: Food." "Usual" is the average of the three previous
    full months over the same days; without three months of history it
    falls back to last month, and without that it makes no comparison.
    None when there's nothing this month or before.
    """
    if df.empty:
        return None
    month, is_partial, day = data["month"], data["is_partial"], data["as_of_day"]
    total = shape.compare_total(df, month, is_partial, lens)
    text = f"{label}: {format_brl(total['current'])} {'so far in' if is_partial else 'in'} {month_name(month)}"

    by_now = f" by the {ordinal(day)}" if is_partial else ""
    average = shape.previous_full_average(df, data["months"], month, lens, to_day=is_partial)
    if average is not None:
        text += f", {_versus(total['current'] - average, 'usual' + by_now)}"
    elif total["previous"] or (df["month"] == shape.shift_month(month, -1)).any():
        previous = month_name(shape.shift_month(month, -1))
        text += f", {_versus(total['change'], previous + by_now)}"
    text += "."

    if top_category:
        this_month = df[df["month"] == month]
        if not this_month.empty:
            biggest = this_month.groupby("primary_category")[shape.lens_column(lens)].sum().idxmax()
            text += f" Biggest: {biggest}."
    return text


def settle_line(balances: dict | None, my_user_id: int | None, month_name: str) -> str | None:
    """Who owes whom this month, from my point of view; None without a balance report."""
    if not balances or "transfers" not in balances:
        return None
    transfers = balances["transfers"]
    if not transfers:
        return f"Settle up: all square for {month_name}."
    parts = []
    for t in transfers:
        amount = format_brl(t["amount"])
        if t["to_user_id"] == my_user_id:
            parts.append(f"{t['from_name']} owes you {amount}")
        elif t["from_user_id"] == my_user_id:
            parts.append(f"you owe {t['to_name']} {amount}")
        else:
            parts.append(f"{t['from_name']} owes {t['to_name']} {amount}")
    text = "; ".join(parts)
    return f"Settle up: {text[0].upper()}{text[1:]} for {month_name}."


def joint_lines(statuses: list | None) -> list[str]:
    """One line per joint account with a known balance, named only when there are several."""
    lines = []
    known = [s for s in statuses or [] if s.get("balance") is not None]
    for status in known:
        name = "Joint account" + (f" ({status['label']})" if len(known) > 1 else "")
        left = f"{name}: {format_brl(Decimal(str(status['balance'])))} left."
        pace = run_out_text(status)
        lines.append(f"{left} {pace}" if pace else left)
    return lines
