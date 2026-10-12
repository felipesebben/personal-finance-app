"""joint_logic: the usual month, the pace curves and the run-out estimate."""
from datetime import date
from decimal import Decimal

from joint_logic import cumulative, full_months_before, run_out_date, usual_curve

D = Decimal


def test_a_month_counts_only_when_tracked_from_its_first_day():
    today = date(2026, 12, 5)
    assert full_months_before(today, date(2026, 10, 11)) == [date(2026, 11, 1)]
    assert full_months_before(today, date(2026, 10, 1)) == [date(2026, 11, 1), date(2026, 10, 1)]
    assert full_months_before(date(2026, 11, 5), date(2026, 10, 11)) == []  # not enough history yet
    assert full_months_before(today, None) == []


def test_at_most_three_months_and_across_new_year():
    assert full_months_before(date(2027, 2, 1), date(2025, 1, 1)) == [
        date(2027, 1, 1), date(2026, 12, 1), date(2026, 11, 1),
    ]


def test_cumulative_fills_days_without_spending():
    daily = {date(2026, 10, 2): D("10"), date(2026, 10, 4): D("5")}
    assert cumulative(daily, date(2026, 10, 1), 5) == [D("0"), D("10"), D("10"), D("15"), D("15")]


def test_usual_averages_and_carries_a_short_month_to_the_end():
    daily = {date(2026, 9, 30): D("30"), date(2026, 8, 31): D("10")}
    # A 31-day month: September (30 days) has finished by day 31.
    curve = usual_curve(daily, [date(2026, 9, 1), date(2026, 8, 1)], 31)
    assert curve[28] == D("0.00")
    assert curve[29] == D("15.00")      # (30 + 0) / 2
    assert curve[30] == D("20.00")      # (30 + 10) / 2
    assert usual_curve(daily, [], 31) is None


def test_run_out_at_this_months_pace():
    today = date(2026, 10, 10)
    # R$ 500 in 10 days = R$ 50/day; R$ 400 left lasts 8 more days.
    assert run_out_date(D("400"), D("500"), 10, today) == date(2026, 10, 18)
    assert run_out_date(D("0"), D("500"), 10, today) == today
    assert run_out_date(D("-20"), D("500"), 10, today) == today
    assert run_out_date(D("400"), D("0"), 10, today) is None   # nothing spent: no pace yet
    assert run_out_date(None, D("500"), 10, today) is None      # balance unknown
