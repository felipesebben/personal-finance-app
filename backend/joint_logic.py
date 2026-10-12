"""
Pure arithmetic for a joint account's spending pace and run-out estimate.
No database access, so it stays unit-testable (like split_logic).

Pace compares this month's cumulative spending, day by day, with the
"usual" month: the average of up to the last three *full* months. A month
counts as full only if the account was already being tracked on its first
day, so a month that started half-way doesn't drag the average down.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

USUAL_MONTHS = 3
CENT = Decimal("0.01")


def month_start(d: date) -> date:
    return d.replace(day=1)


def previous_month(d: date) -> date:
    first = month_start(d)
    return month_start(first - timedelta(days=1))


def days_in(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def full_months_before(today: date, tracked_since: date | None, n: int = USUAL_MONTHS) -> list[date]:
    """Up to `n` month starts before today's month, newest first, that were tracked from day 1."""
    if tracked_since is None:
        return []
    months, m = [], previous_month(today)
    while len(months) < n and m >= tracked_since:
        months.append(m)
        m = previous_month(m)
    return months


def cumulative(daily: dict[date, Decimal], first: date, days: int) -> list[Decimal]:
    """Running total of spending for days 1..days of the month starting at `first`."""
    total, out = Decimal("0"), []
    for i in range(days):
        total += daily.get(first + timedelta(days=i), Decimal("0"))
        out.append(total)
    return out


def usual_curve(daily: dict[date, Decimal], months: list[date], days: int) -> list[Decimal] | None:
    """
    The average cumulative spend by day 1..days over `months`, or None
    without any. A shorter month has finished by day 29-31, so its total
    carries on to the end.
    """
    if not months:
        return None
    curves = []
    for m in months:
        c = cumulative(daily, m, days_in(m))
        curves.append(c + [c[-1]] * (days - len(c)))
    return [(sum(c[i] for c in curves) / len(curves)).quantize(CENT, ROUND_HALF_UP) for i in range(days)]


def run_out_date(balance: Decimal | None, spent_to_day: Decimal, as_of_day: int, today: date) -> date | None:
    """
    When the money runs out at this month's pace so far, or None when that
    can't be said (no balance known, or nothing spent yet). An empty or
    overdrawn account has run out today.
    """
    if balance is None:
        return None
    if balance <= 0:
        return today
    if spent_to_day <= 0 or as_of_day <= 0:
        return None
    per_day = spent_to_day / as_of_day
    return today + timedelta(days=int(balance / per_day))
