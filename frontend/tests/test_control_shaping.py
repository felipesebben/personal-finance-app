"""analytics_shaping: what we control (and fixed costs, one-offs), against the usual month."""
import math

import pandas as pd

import analytics_charts as charts
import analytics_shaping as shape

MONTHS = ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]


def row(month, category, amount, cost_type="Variable", nature="Normal", to_day=None):
    to_day = amount if to_day is None else to_day
    return {"month": month, "primary_category": category, "sub_category": "x", "cost_type": cost_type,
            "nature": nature, "household": amount, "mine": amount, "household_to_day": to_day,
            "mine_to_day": to_day, "count": 1, "source": ""}


def frame(rows):
    return shape.to_frame({"rows": rows})


def test_what_we_control_is_variable_without_one_offs():
    df = frame([row("2026-10", "Food", 100), row("2026-10", "Housing", 900, cost_type="Fixed"),
                row("2026-10", "Housing", 120), row("2026-10", "Transport", 3000, nature="Extraordinary")])
    assert set(shape.controllable(df)["household"]) == {100, 120}
    assert list(shape.fixed_costs(df)["household"]) == [900]
    assert list(shape.one_offs(df)["household"]) == [3000]


def test_usual_is_the_average_of_up_to_three_full_months():
    totals = pd.Series([50.0, 100.0, 200.0, 300.0, 999.0], index=MONTHS)
    assert shape.usual_before(totals, "2026-11", since="2026-07") == 200.0   # Aug–Oct
    assert shape.usual_before(totals, "2026-11", since="2026-10") == 300.0   # only October logged in full
    assert shape.usual_before(totals, "2026-10", since="2026-10") is None


def test_a_category_above_usual_two_months_running_is_flagged():
    rows = [row(m, "Food", a) for m, a in zip(MONTHS, [100, 100, 100, 150, 200])]
    rows += [row(m, "Pets", a) for m, a in zip(MONTHS, [300, 300, 300, 300, 290])]
    rows.append(row("2026-11", "Housing", 5000, cost_type="Fixed"))  # not something we control
    out = shape.control_rows(frame(rows), MONTHS, "2026-11", "Household", False, since="2026-07")
    assert [r["name"] for r in out] == ["Pets", "Food"]
    food = out[1]
    assert food["usual"] == round((100 + 100 + 150) / 3, 2) and food["streak"] == 2
    assert out[0]["streak"] == 0
    lines = shape.control_lines(out)
    assert lines[0] == ("Above usual for two months or more: Food.", "more")
    assert lines[1][0].startswith("Where you could save: Food R$ 83,33 above usual")


def test_a_month_in_progress_is_compared_over_the_same_days():
    rows = [row("2026-10", "Food", 300, to_day=100), row("2026-11", "Food", 105)]
    [food] = shape.control_rows(frame(rows), MONTHS, "2026-11", "Household", True, since="2026-10")
    assert food["usual"] == 100.0 and food["change"] == 5.0 and food["streak"] == 0
    assert shape.control_lines([food]) == [("Everything you control is within 10% of usual.", "less")]


def test_without_a_whole_month_there_is_no_usual_yet():
    [food] = shape.control_rows(frame([row("2026-11", "Food", 105)]), MONTHS, "2026-11", "Household", True,
                                since="2026-11")
    assert food["usual"] is None and math.isnan(food["pct"])
    assert shape.control_lines([food])[0][0].startswith("The usual month appears")


def test_change_frame_in_reais_or_percent():
    bars = pd.DataFrame({"name": ["Food", "Pets", "Gifts"], "amount": [150.0, 80.0, 40.0],
                         "previous": [100.0, 100.0, 0.0]})
    money = charts.change_frame(bars)
    assert list(money["value"]) == [50.0, -20.0, 40.0]
    assert list(money["direction"]) == ["more", "less", "more"]
    pct = charts.change_frame(bars, "%")
    assert list(pct["value"]) == [0.5, -0.2, 0.0]
    assert list(pct["label"]) == ["▲ 50%", "▼ 20%", "new"]
