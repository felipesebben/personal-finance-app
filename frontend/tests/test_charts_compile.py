"""
Every chart compiles in Vega-Lite itself. A spec Altair builds happily can
still be one Vega-Lite rejects (e.g. a layer with an axis next to layers
without), and Streamlit then draws nothing, silently: the hero's sparkline
was blank for a while that way. vl-convert runs the real Vega-Lite.
"""
import datetime
from zoneinfo import ZoneInfo

import pytest
import vl_convert as vlc

import analytics_charts
import analytics_shaping as shape
import daily_charts
import daily_shaping as daily
from conftest import sample_payload
from test_daily_shaping import payload, row


def compiles(chart) -> None:
    vlc.vegalite_to_vega(chart.to_dict())


def daily_charts_for(partial: bool):
    p = payload([row("2026-07-02", "100.00"), row("2026-08-05", "200.00"), row("2026-09-03", "150.00"),
                 row("2026-10-04", "220.00", "Pets", "Vet"), row("2026-10-04", "40.00", sub="Delivery")],
                is_partial=partial, as_of_day=10 if partial else 31)
    rows = daily.rows_frame(p)
    df = daily.by_day(rows)
    today = datetime.date(2026, 10, 10)
    cal = daily.calendar_frame(df, "2026-10", "Household", today)
    hist = daily.history(df, p, "Household")
    mix = daily.ranked(rows, "Household", "primary_category", month="2026-10")
    days = daily.biggest_days(df, "2026-10", "Household")
    items = [{"transaction_timestamp": "2026-10-04T12:00:00Z", "primary_category": "Pets", "sub_category": "Vet",
              "price": "220.00", "mine": "132.00", "payment_method": "Pix", "institution": None, "paid_by": "Me"}]
    return [
        daily_charts.running_total_chart(daily.running_frame(df, p, "Household"), daily.series_order(p), 31,
                                         10 if partial else None, "t"),
        daily_charts.spark_running(daily.running_frame(df, p, "Household", with_usual=False),
                                   daily.series_order(p), 31),
        daily_charts.spark_bars(hist, "per_day", "Per day", reference=12.0),
        daily_charts.spark_bars(hist, "total", "Whole month"),
        daily_charts.spark_progress(0.7, 0.3),
        daily_charts.spark_days(cal),
        daily_charts.calendar_chart(cal, daily.calendar_scale_max(cal)),
        daily_charts.weekday_chart(daily.weekday_profile(df, p, "Household", today)),
        daily_charts.changes_chart(daily.category_changes(rows, p, "Household")),
        analytics_charts.ranked_bars(mix, picked=mix["name"].iloc[0]),
        analytics_charts.ranked_bars(days, picked=days["name"].iloc[0], room=1.7, reference=40.0,
                                     reference_label="average day R$ 40"),
        analytics_charts.ranked_bars(daily.day_items(items, "Household", ZoneInfo("America/Sao_Paulo"))),
    ]


@pytest.mark.parametrize("partial", [True, False])
def test_every_daily_chart_compiles(partial):
    for chart in daily_charts_for(partial):
        compiles(chart)


def test_every_monthly_chart_compiles():
    p = sample_payload("2026-10")
    df = shape.to_frame(p)
    months = p["months"]
    comp = shape.compare(df, "2026-10", True, "Household")
    for chart in (
        analytics_charts.trend_chart(shape.monthly_totals(df, months, "Household"), "2026-10", True, 2626.67),
        analytics_charts.ranked_bars(shape.ranked_comparison(comp, "primary_category"), picked="Food",
                                     previous="previous"),
        daily_charts.changes_chart(shape.as_changes(comp, "primary_category")),
        analytics_charts.heatmap_chart(shape.heatmap_frame(df, months, "Household"), months),
        analytics_charts.cost_type_chart(shape.cost_type_split(df, "2026-10", True, "Household"), "Oct 26",
                                         "Sep 26"),
        daily_charts.spark_bars(shape.month_bars(shape.monthly_totals(df, months[-6:], "Household"), "2026-10"),
                                "value", "Spent", reference=100.0),
    ):
        compiles(chart)


def test_a_broken_spec_is_caught():
    import altair as alt
    import pandas as pd
    # The hero sparkline's old baseline: a rule with a default axis under a line with none.
    frame = pd.DataFrame({"x": [1, 2], "y": [1.0, 2.0]})
    broken = alt.layer(alt.Chart(pd.DataFrame({"z": [0.0]})).mark_rule().encode(y="z:Q"),
                       alt.Chart(frame).mark_line().encode(x=alt.X("x:Q", axis=None), y=alt.Y("y:Q", axis=None)))
    with pytest.raises(Exception):
        compiles(broken)


def test_bullet_bars_and_a_partly_logged_line_compile():
    rows = daily.rows_frame(SAMPLE_BULLET)
    mix = daily.against_last_month(daily.ranked(rows, "Household", "primary_category", month="2026-10"), rows,
                                   "Household", "primary_category", "2026-10", 10)
    compiles(analytics_charts.ranked_bars(mix, picked=mix["name"].iloc[0], previous="previous"))
    started = daily.logging_started(rows)
    since = daily.tracked_since(rows)
    frame = daily.running_frame(daily.by_day(rows), SAMPLE_BULLET, "Household", since=since, started=started)
    order = daily.series_order(SAMPLE_BULLET, daily.partly_logged_from("2026-09", since, started))
    compiles(daily_charts.running_total_chart(frame, order, 31, 10, "t"))
    compiles(daily_charts.spark_running(frame, order, 31))


SAMPLE_BULLET = payload([row("2026-09-28", "300.00"), row("2026-10-02", "50.00", "Pets", "Vet")],
                        months=("2026-09", "2026-10"))
