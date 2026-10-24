"""This month's calendar as HTML (frontend/calendar_html.py)."""
import datetime

import pandas as pd

import calendar_html
import daily_shaping as daily
from daily_charts import EMPTY_DAY, HEAT


def calendar(amounts: dict, today=datetime.date(2026, 10, 23)):
    rows = []
    for d in range(1, 32):
        date = datetime.date(2026, 10, d)
        state = "future" if date > today else "today" if date == today else "past"
        amount = 0.0 if state == "future" else amounts.get(d, 0.0)
        rows.append({"day": d, "weekday": date.weekday(), "state": state, "amount": amount,
                     "amount_brl": f"R$ {amount:.2f}", "count": 1 if amount else 0,
                     "top_category": "Food" if amount else "", "label": f"{date:%a} {d} October"})
    return pd.DataFrame(rows)


def test_shade_goes_from_the_lightest_green_to_brand_green():
    assert calendar_html.shade(0, 100) == EMPTY_DAY
    assert calendar_html.shade(1e-9, 100) == HEAT[0]
    assert calendar_html.shade(100, 100) == HEAT[1].lower()
    assert calendar_html.shade(5000, 100) == HEAT[1].lower()  # past the scale stays brand green


def test_the_first_starts_in_its_weekday_column_and_today_is_marked():
    html = calendar_html.calendar_html(calendar({1: 50.0, 23: 300.0}), top=200.0)
    # 1 October 2026 is a Thursday: the fourth column.
    assert 'class="hf-cal-day hf-past" style="grid-column:4;' in html
    assert html.count('class="hf-cal-day') == 31
    assert html.count("hf-today") == 1 and html.count("hf-future") == 8
    assert html.count('class="hf-cal-head"') == 7


def test_dark_days_get_white_numbers_and_hover_text():
    html = calendar_html.calendar_html(calendar({23: 300.0, 2: 10.0}), top=200.0)
    assert "color:#ffffff" in html  # the 23rd, past the scale
    assert 'title="Fri 23 October · R$ 300.00 · 1 expense · mostly Food"' in html
    assert 'title="Sat 31 October"' in html  # days to come: just the date


def test_hover_text_is_escaped():
    cal = calendar({5: 10.0})
    cal.loc[cal["day"] == 5, "top_category"] = 'Food & "drinks"'
    assert "mostly Food &amp; &quot;drinks&quot;" in calendar_html.calendar_html(cal, 100.0)


def test_works_on_the_real_calendar_frame():
    from test_comparisons import year_of_data
    p = year_of_data()
    cal = daily.calendar_frame(daily.by_day(daily.rows_frame(p)), "2026-10", "Household", datetime.date(2026, 10, 10))
    html = calendar_html.calendar_html(cal, daily.calendar_scale_max(cal))
    assert html.count('class="hf-cal-day') == 31 and html.count("hf-today") == 1
