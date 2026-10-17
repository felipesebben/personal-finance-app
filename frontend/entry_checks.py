"""
Pure helpers for the Add expense page: the duplicate warning's sentences
and the "where am I with backfilling" line. No Streamlit import, so
they're unit-tested in tests/test_entry_checks.py.
"""
from __future__ import annotations

import pandas as pd

from money import format_brl


def _local(timestamp, tz) -> pd.Timestamp:
    ts = pd.Timestamp(timestamp)
    return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert(tz)


def duplicate_lines(duplicates: list[dict], tz) -> list[str]:
    """One sentence per expense the API says this one may duplicate."""
    lines = []
    for d in duplicates:
        day = _local(d["transaction_timestamp"], tz).strftime("%d/%m/%Y")
        what = " · ".join(x for x in (format_brl(d["price"]), d.get("category"), d.get("payment_method")) if x)
        who = "You already logged this" if d.get("logged_by_me") else (
            f"{d.get('logged_by') or 'Your partner'} already logged a matching shared expense")
        lines.append(f"{who} on {day}: {what}.")
    return lines


def _describe(expense: dict, day: pd.Timestamp, logged_by: str | None = None) -> str:
    category = expense.get("category") or {}
    parts = [
        format_brl(expense["price"]),
        f"{category.get('primary_category')} › {category.get('sub_category')}" if category else None,
        f"logged by {logged_by}" if logged_by else None,
    ]
    return f"{day.day} {day:%B %Y} ({' · '.join(x for x in parts if x)})"


def _span_line(label: str, expenses: list[dict], tz, who=None) -> str | None:
    """'<label>: earliest …, latest …. By month: …', or None without any."""
    if not expenses:
        return None
    when = pd.Series([_local(e["transaction_timestamp"], tz) for e in expenses])
    first, last = int(when.values.argmin()), int(when.values.argmax())
    counts = when.dt.strftime("%Y-%m").value_counts().sort_index()
    by_month = " · ".join(f"{pd.Timestamp(month + '-01'):%b %Y} {n}" for month, n in counts.items())
    earliest = _describe(expenses[first], when[first], who(expenses[first]) if who else None)
    if first == last:
        return f"{label}: one so far, {earliest}."
    latest = _describe(expenses[last], when[last], who(expenses[last]) if who else None)
    return f"{label}: earliest {earliest}, latest {latest}. By month: {by_month}."


def backfill_lines(expenditures: list[dict], my_user_id: int | None, tz) -> list[str]:
    """
    Where logging has got to, to see where backfilling stopped: the
    earliest and latest shared expense (saying who logged each) and the
    earliest and latest of my personal ones, with counts per month. Only
    what I can see, so a partner's personal spending never appears.
    """
    def logged_by(e: dict) -> str:
        user = e.get("user") or {}
        return "you" if user.get("user_id") == my_user_id else (user.get("full_name") or "your partner")

    shared = [e for e in expenditures or [] if e.get("is_shared")]
    personal = [e for e in expenditures or []
                if not e.get("is_shared") and (e.get("user") or {}).get("user_id") == my_user_id]
    lines = [_span_line("Shared", shared, tz, who=logged_by), _span_line("Personal", personal, tz)]
    return [line for line in lines if line]
