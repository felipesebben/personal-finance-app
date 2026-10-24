"""The named comparisons on This month, the two line charts' frames, and the in-app notices."""
import datetime

import pandas as pd

import daily_charts
import daily_shaping as daily
import notices
from analytics_shaping import shift_month
from test_charts_compile import compiles
from test_daily_shaping import payload, row


def year_of_data(as_of_day=10):
    """Fourteen months of R$ 100 groceries (a 13-month window) on the 1st and R$ 1.000 rent on the 5th, October 2026 in progress."""
    months = [shift_month("2026-10", -k) for k in range(13, -1, -1)]
    rows = []
    for m in months:
        rows.append(row(f"{m}-01", "100.00"))
        rows.append(row(f"{m}-05", "1000.00", "Housing", "Rent", "Fixed"))
    return payload(rows, months=months[1:], as_of_day=as_of_day)


def test_each_comparison_needs_its_months_logged_in_full():
    p = year_of_data()
    df = daily.by_day(daily.rows_frame(p))
    assert daily.baseline_months(df, p, "last", "2025-09") == ["2026-09"]
    assert daily.baseline_months(df, p, "usual", "2025-09") == ["2026-09", "2026-08", "2026-07"]
    assert len(daily.baseline_months(df, p, "year", "2025-09")) == 12
    assert daily.baseline_months(df, p, "last_year", "2025-09") == ["2025-10"]
    # Logging began in March 2026: no year yet, no same month last year.
    assert daily.baseline_months(df, p, "year", "2026-03") == []
    assert daily.baseline_months(df, p, "last_year", "2026-03") == []
    assert daily.comparison_options(df, p, "2026-03") == {"September": "last", "Usual month": "usual"}
    assert list(daily.comparison_options(df, p, "2025-09").values()) == ["last", "usual", "year", "last_year"]


def test_the_days_chart_draws_every_comparison_that_has_data_and_the_target_pace():
    p = year_of_data()
    df = daily.by_day(daily.rows_frame(p))
    frame, order, roles = daily.track_frame(df, p, "Household", since="2025-09", target=3100.0)
    assert roles == ["this", "last", "usual", "year", "last_year", "target"]
    assert order == ["October so far", "September", "Usual month", "12-month average", "Same month last year",
                     "Target"]
    target = frame[frame["series"] == "Target"].set_index("day")["amount"]
    assert (target.loc[1], target.loc[31]) == (100.0, 3100.0)  # a steady pace to the whole month's target
    this = frame[frame["series"] == "October so far"]
    assert this["day"].max() == 10 and this["amount"].max() == 1100.0
    compiles(daily_charts.running_total_chart(frame, order, 31, 10, "t", roles=roles))


def test_the_months_chart_and_its_references():
    p = year_of_data()
    df = daily.by_day(daily.rows_frame(p))
    months = daily.months_frame(df, p, "Household", since="2025-09")
    assert len(months) == 13 and months["is_partial"].iloc[-1]  # the 13-month window and months["amount"].iloc[-1] == 1100.0
    refs = daily.month_references(df, p, "Household", since="2025-09", target=3000.0)
    assert refs == [("12-month average", 1100.0), ("Target", 3000.0)]
    assert daily.month_references(df, p, "Household", since="2026-03") == []
    compiles(daily_charts.months_chart(months, refs))


def test_what_drove_it_day_to_day_or_fixed():
    p = payload([row("2026-09-02", "100.00"), row("2026-09-03", "1000.00", "Housing", "Rent", "Fixed"),
                 row("2026-10-02", "300.00"), row("2026-10-03", "900.00", "Housing", "Rent", "Fixed")],
                months=("2026-09", "2026-10"))
    rows = daily.rows_frame(p)
    assert daily.cause_lines(rows, p, "Household", "last", since="2026-09") == [
        ("Day-to-day ▲ R$ 200,00", "more"), ("Fixed ▼ R$ 100,00", "less")]


def test_target_total_follows_the_filters():
    rows = daily.rows_frame(payload([row("2026-10-02", "10.00")]))  # only Food left after the filters
    targets = {"Food": 3000.0, "Pets": 800.0}
    assert daily.target_total(targets, rows, narrowed=False) == 3800.0
    assert daily.target_total(targets, rows, narrowed=True) == 3000.0
    assert daily.target_total({}, rows, narrowed=False) == 0.0


def test_the_hero_sparkline_keeps_this_month_and_last_and_compiles():
    p = year_of_data()
    df = daily.by_day(daily.rows_frame(p))
    frame, order, roles = daily.track_frame(df, p, "Household", target=3000.0)
    assert {"this", "last"} <= set(roles) and len(roles) > 2  # the big chart has more than the gist
    spark = daily_charts.hero_spark(frame, order, roles, 31)
    compiles(spark)
    kept = {v for v in spark.to_dict()["layer"][0]["encoding"]["color"]["scale"]["domain"]}
    assert kept == {name for name, role in zip(order, roles) if role in ("this", "last")}


def test_no_sparkline_without_spending():
    frame = pd.DataFrame({"day": [1, 2], "series": ["October so far"] * 2, "amount": [0.0, 0.0],
                          "amount_brl": ["R$ 0,00"] * 2})
    assert daily_charts.hero_spark(frame, ["October so far"], ["this"], 31) is None


def test_notices_put_what_is_over_first_then_near_then_late_bills():
    due = pd.DataFrame({"name": ["Health › Boxing", "Housing › Internet"], "amount": [800.0, 99.9], "day": [9, 25]})
    lines = notices.notices({"Food": 3500.0, "Pets": 1000.0, "Home": 500.0},
                            {"Food": 3900.0, "Pets": 950.0, "Home": 100.0}, due, day=23, days=31)
    assert lines == [
        ("Food is past its monthly target: R$ 3.900,00 of R$ 3.500,00.", "more"),
        ("Pets is at 95% of its monthly target with 8 days to go.", None),
        ("Boxing (R$ 800,00) usually comes by the 9th and isn't logged yet.", None),  # the 25th hasn't come
    ]
    assert notices.notices({}, {}, due.iloc[0:0], day=5, days=31) == []
