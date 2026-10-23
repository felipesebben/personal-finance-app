"""
The monthly recap you review together: a month in a few sentences — the
total and how it compares, what drove the change (day-to-day or fixed, and
the biggest moves), and the targets — before settling up.

Built from /analytics/shared rows (analytics_shaping.to_frame) for the
household's shared spending at full price. Pure: no Streamlit, tested in
tests/test_recap_shaping.py. Comparisons follow the app's rule: a ▲/▼ only
against months logged in full (analytics_shaping.tracked_since).
"""
from __future__ import annotations

import datetime
import math

import pandas as pd

import analytics_shaping as shape
from money import format_brl

COST_NAMES = {"Variable": "day-to-day", "Fixed": "fixed"}


def _moved(change: float, against: str, previous: float | None = None) -> tuple[str, str | None]:
    """'▲ R$ 1.858,23 (36%) more than September', toned for ui.kpi."""
    if round(change, 2) == 0:
        return f"The same as {against}", None
    word, arrow, tone = ("more", "▲", "more") if change > 0 else ("less", "▼", "less")
    pct = f" ({abs(change) / previous:.0%})" if previous else ""
    return f"{arrow} {format_brl(abs(change))}{pct} {word} than {against}", tone


def month_recap(df: pd.DataFrame, months: list[str], month: str, is_partial: bool, first_date: str | None,
                targets: dict[str, float] | None = None, lens: str = "Household") -> dict:
    """
    {label, total, lines, causes, moves, targets}: each a list of
    (text, tone) lines, tone "more", "less" or None.

    - lines: the total against last month and the usual month (the three
      before), or why there's no comparison yet;
    - causes: the change split into day-to-day and fixed costs;
    - moves: the three categories that moved most;
    - targets: each targeted category, over or within, worst first.
    """
    previous = shape.shift_month(month, -1)
    since = shape.tracked_since(first_date) or (df["month"].min() if not df.empty else None)
    comparable = since is not None and since <= previous
    total = shape.compare_total(df, month, is_partial, lens)
    previous_name = datetime.date(int(previous[:4]), int(previous[5:]), 1).strftime("%B")
    by_day = " by the same day" if is_partial else ""

    lines = []
    if comparable:
        lines.append(_moved(total["change"], f"{previous_name}{by_day}", total["previous"]))
        usual = shape.previous_full_average(df, months, month, lens, to_day=is_partial, since=since)
        if usual is not None:
            lines.append(_moved(round(total["current"] - usual, 2), f"the usual month{by_day}", usual))
    else:
        partly = shape.partly_logged_from(previous, first_date)
        lines.append((f"{previous_name} was logged from the {shape.ordinal(partly)} only, so not compared yet."
                      if partly else "Nothing to compare with yet: the first whole month logged comes first.", None))

    causes, moves = [], []
    if comparable:
        split = shape.compare(df, month, is_partial, lens, by="cost_type")
        for _, row in split.sort_values("change", key=abs, ascending=False).iterrows():
            if round(row["change"], 2) == 0:
                continue
            name = COST_NAMES.get(row["cost_type"], row["cost_type"].lower())
            arrow = "▲" if row["change"] > 0 else "▼"
            causes.append((f"{name.capitalize()}: {arrow} {format_brl(abs(row['change']))}, "
                           f"now {format_brl(row['current'])}", "more" if row["change"] > 0 else "less"))
        changes = shape.biggest_changes(shape.compare(df, month, is_partial, lens), "primary_category").head(3)
        for _, row in changes.iterrows():
            arrow = "▲" if row["change"] > 0 else "▼"
            pct = "" if math.isnan(row["pct"]) else f" ({abs(row['pct']):.0%})"
            moves.append((f"{row['primary_category']} {arrow} {format_brl(abs(row['change']))}{pct}",
                          "more" if row["change"] > 0 else "less"))

    targeted = []
    spent = df[df["month"] == month].groupby("primary_category")[shape.lens_column(lens)].sum()
    for name, target in (targets or {}).items():
        if target <= 0:
            continue
        value = float(spent.get(name, 0.0))
        targeted.append((value / target, name, value, target))
    target_lines = []
    for ratio, name, value, target in sorted(targeted, reverse=True):
        if ratio > 1:
            target_lines.append((f"{name}: {format_brl(value)} of {format_brl(target)}, "
                                 f"▲ {format_brl(value - target)} over", "more"))
        else:
            target_lines.append((f"{name}: {format_brl(value)} of {format_brl(target)} ({ratio:.0%})", None))

    return {
        "label": f"{shape.month_label(month)}{' so far' if is_partial else ''}",
        "total": format_brl(total["current"]),
        "lines": lines,
        "causes": causes,
        "moves": moves,
        "targets": target_lines,
    }
