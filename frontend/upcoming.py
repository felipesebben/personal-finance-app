"""
What's still to come this month, from the expenses already logged (GET
/expenditures/): recurring bills seen in recent months that haven't shown
up yet this month, and card installments of earlier purchases billed this
month. The analytics count an installment purchase in full in the month it
was bought, so these say what this month's cash still has to cover.

No Streamlit import, so it's unit-tested in tests/test_upcoming.py; the
daily view draws it.
"""
from __future__ import annotations

import datetime

import pandas as pd

import analytics_shaping as shape
from entries import local
from joint_shaping import ordinal
from money import format_brl

COLUMNS = ["name", "amount", "amount_brl", "share", "text", "primary_category", "cost_type", "nature"]
LOOKBACK = 3  # months searched for a recurring bill


def in_view(e: dict, view: str) -> bool:
    """Whether an expense belongs to what's shown: "shared", "personal", or "all" (both)."""
    return {"shared": bool(e.get("is_shared")), "personal": not e.get("is_shared")}.get(view, True)


def amount(e: dict, lens: str) -> float:
    """The full price for the Household lens, else my part (a personal expense's is its price)."""
    return float(e["price"] if lens == "Household" else (e.get("my_share") or 0))


def _what(e: dict) -> str:
    category = e.get("category") or {}
    return f"{category.get('primary_category', '—')} › {category.get('sub_category', '—')}"


def _frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    out = pd.DataFrame(rows).sort_values(["amount", "name"], ascending=[False, True], ignore_index=True)
    out["amount_brl"] = out["amount"].map(format_brl)
    out["share"] = out["amount"] / out["amount"].sum() if out["amount"].sum() else 0.0
    return out[COLUMNS]


def recurring_due(expenses: list[dict] | None, month: str, today: datetime.date, view: str, lens: str,
                  tz) -> pd.DataFrame:
    """
    Recurring bills (nature "Recurring") logged in the LOOKBACK months
    before `month` whose category hasn't been logged yet in `month`, each
    at its latest amount and day: name ("Housing › Electricity"), amount,
    and the text at its bar's tip, "R$ 180 · usually the 10th".
    """
    earlier = {shape.shift_month(month, -k) for k in range(1, LOOKBACK + 1)}
    seen_now, latest = set(), {}
    for e in expenses or []:
        if not in_view(e, view):
            continue
        when = local(e["transaction_timestamp"], tz)
        m = when.strftime("%Y-%m")
        if m == month:
            seen_now.add(_what(e))
        elif m in earlier and e.get("nature") == "Recurring":
            if _what(e) not in latest or when > latest[_what(e)][0]:
                latest[_what(e)] = (when, e)
    rows = []
    for name, (when, e) in latest.items():
        if name in seen_now:
            continue
        value = round(amount(e, lens), 2)
        if value <= 0:
            continue
        category = e.get("category") or {}
        rows.append({"name": name, "amount": value, "text": f"{shape.short_brl(value)} · usually the {ordinal(when.day)}",
                     "primary_category": category.get("primary_category", "—"),
                     "cost_type": category.get("cost_type", "Unknown"), "nature": "Recurring"})
    return _frame(rows)


def installments_due(expenses: list[dict] | None, month: str, view: str, lens: str, tz) -> pd.DataFrame:
    """
    Card installments of purchases from earlier months billed in `month`:
    an installment purchase is one expense at its full price, its
    current_installment billed in the month it was logged, the next ones one
    a month after. Each: name ("Home › Furniture"), the installment's amount
    (the price split evenly; the last absorbs the cents, as in the ETL) and
    the tip, "R$ 250 · 4 of 10".
    """
    target = int(month[:4]) * 12 + int(month[5:])
    rows = []
    for e in expenses or []:
        total = e.get("total_installments") or 1
        if total <= 1 or not in_view(e, view):
            continue
        when = local(e["transaction_timestamp"], tz)
        months_after = target - (when.year * 12 + when.month)
        number = (e.get("current_installment") or 1) + months_after
        if months_after <= 0 or number > total:
            continue  # bought this month (already counted) or paid off
        whole = amount(e, lens)
        each = int(whole * 100 // total) / 100  # all but the last rounded down to the cent
        value = round(whole - each * (total - 1), 2) if number == total else each
        if value <= 0:
            continue
        category = e.get("category") or {}
        rows.append({"name": f"{_what(e)} · {when:%d/%m}", "amount": value,
                     "text": f"{shape.short_brl(value)} · {number} of {total}",
                     "primary_category": category.get("primary_category", "—"),
                     "cost_type": category.get("cost_type", "Unknown"), "nature": e.get("nature") or "Normal"})
    return _frame(rows)
