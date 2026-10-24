"""daily_shaping: this month day by day against last month and the usual month."""
import datetime

import pytest

import daily_charts
import daily_shaping as daily
from filtering import DAY_TO_DAY, FIXED, Filters, filter_rows, note

MONTHS = ("2026-07", "2026-08", "2026-09", "2026-10")


def row(date, household, category="Food", sub="Groceries", cost_type="Variable", nature="Normal", count=1,
        mine=None):
    mine = mine if mine is not None else f"{float(household) * 0.6:.2f}"
    return {"date": date, "primary_category": category, "sub_category": sub, "cost_type": cost_type,
            "nature": nature, "household": household, "mine": mine, "count": count}


def payload(rows, month="2026-10", is_partial=True, as_of_day=10, months=MONTHS):
    return {"month": month, "months": list(months), "is_partial": is_partial, "as_of_day": as_of_day,
            "today": f"{month}-{as_of_day:02d}", "rows": rows}


SAMPLE = payload([
    row("2026-07-02", "100.00"),
    row("2026-08-05", "200.00", count=2),
    row("2026-08-20", "300.00", "Home", "Furniture"),
    row("2026-09-03", "150.00"),
    row("2026-09-15", "450.00", "Housing", "Rent", "Fixed", count=3),
    row("2026-10-01", "80.00"),
    row("2026-10-04", "220.00", "Pets", "Vet", count=2),
])


def frame(p=SAMPLE):
    return daily.to_frame(p)


def test_to_frame_and_daily_amounts_zero_fill():
    df = frame()
    assert list(df["month"].unique()) == ["2026-07", "2026-08", "2026-09", "2026-10"]
    oct_ = daily.daily_amounts(df, "2026-10", "Household")
    assert len(oct_) == 31 and oct_[1] == 80.0 and oct_[2] == 0.0 and oct_[4] == 220.0
    assert daily.daily_amounts(df, "2026-10", "My share")[4] == 132.0


def test_by_day_sums_categories_and_names_the_top_one():
    p = payload([row("2026-10-03", "40.00"), row("2026-10-03", "30.00", sub="Delivery"),
                 row("2026-10-03", "60.00", "Home", "Furniture")])
    [day] = daily.to_frame(p).to_dict("records")
    assert (day["household"], day["count"], day["top_category"]) == (130.0, 3, "Food")  # Food 70 beats Home 60


def test_filters_narrow_what_is_counted():
    rows = daily.rows_frame(payload([
        row("2026-10-01", "50.00"),
        row("2026-10-02", "900.00", "Transport", "IPVA", "Fixed", "Annual"),
        row("2026-10-03", "1500.00", "Housing", "Rent", "Fixed", "Recurring"),
    ]))
    assert filter_rows(rows, Filters(DAY_TO_DAY))["household"].sum() == 50.0
    assert filter_rows(rows, Filters(FIXED))["household"].sum() == 2400.0
    assert filter_rows(rows, Filters(without_one_offs=True))["household"].sum() == 1550.0  # no IPVA
    assert filter_rows(rows, Filters(categories=("Transport",)))["household"].sum() == 900.0
    assert len(filter_rows(rows, Filters())) == 3 and len(filter_rows(rows, None)) == 3
    assert note(Filters(DAY_TO_DAY, ("Food",), True)) == "day-to-day costs · Food · without one-offs"
    assert note(Filters()) == "" and not Filters().active


def test_pace_compares_the_same_days():
    p = daily.pace(frame(), SAMPLE, "Household")
    # October to day 10: 300. September days 1-10: 150. Usual by day 10: (100 + 200 + 150) / 3 = 150.
    assert (p["so_far"], p["last_by_day"], p["usual_by_day"]) == (300.0, 150.0, 150.0)
    assert (p["last_total"], p["usual_total"]) == (600.0, 400.0)  # (100 + 500 + 600) / 3
    assert (p["per_day"], p["last_per_day"], p["usual_per_day"]) == (30.0, 15.0, 15.0)
    assert p["usual_of"] == ["2026-07", "2026-08", "2026-09"]
    # The rest of October as usual: 300 + (400 - 150).
    assert p["heading_for"] == 550.0
    # 100 left of the usual 400, over the 21 days after the 10th.
    assert (p["reference_name"], p["days_left"], p["allowance"]) == ("usual", 21, round(100 / 21, 2))


def test_tracking_starts_with_the_unfiltered_data():
    # Filtered down to Pets, there's nothing before October; but the household was tracking since July.
    pets = daily.by_day(filter_rows(daily.rows_frame(SAMPLE), Filters(categories=("Pets",))))
    p = daily.pace(pets, SAMPLE, "Household", since="2026-07")
    assert (p["has_last"], p["last_total"], p["usual_total"]) == (True, 0.0, 0.0)
    assert not daily.pace(pets, SAMPLE, "Household")["has_last"]


def test_headline_leads_with_the_answer():
    h = daily.headline(daily.pace(frame(), SAMPLE, "Household"))
    assert (h["label"], h["amount"]) == ("Spent so far in October", "R$ 300,00")
    assert h["lines"] == [
        ("▲ R$ 150,00 (100%) more than September by the 10th", "more"),
        ("▲ R$ 150,00 (100%) more than usual by the 10th", "more"),
        ("Heading for about R$ 550,00 if the rest of October goes as usual", None),
    ]
    assert daily.headline(daily.pace(frame(), SAMPLE, "Household"), "day-to-day costs")["label"] == (
        "Spent so far in October · day-to-day costs")


def test_headline_for_a_finished_month_and_without_history():
    finished = payload([row("2026-09-03", "150.00"), row("2026-10-04", "100.00")], is_partial=False, as_of_day=31)
    h = daily.headline(daily.pace(daily.to_frame(finished), finished, "Household"))
    assert h["label"] == "Spent in October"
    assert h["lines"] == [("▼ R$ 50,00 (33%) less than September", "less")]
    first = payload([row("2026-10-04", "100.00")])
    h = daily.headline(daily.pace(daily.to_frame(first), first, "Household"))
    assert h["lines"] == [("Nothing to compare with yet. Comparisons start in November, against October.", None)]


def test_a_month_whose_logging_started_late_is_not_compared():
    # One expense on 29 September, then October: September wasn't logged in full.
    late = payload([row("2026-09-29", "449.00"), row("2026-10-02", "100.00")])
    rows = daily.rows_frame(late)
    assert daily.tracked_since(rows) == "2026-10"
    assert daily.tracked_since(daily.rows_frame(payload([row("2026-09-06", "1.00")]))) == "2026-09"
    p = daily.pace(daily.by_day(rows), late, "Household", since=daily.tracked_since(rows))
    assert not p["has_last"]
    h = daily.headline(p, started=daily.logging_started(rows))
    assert h["lines"] == [("Nothing to compare with yet. Logging started on 29 September, so comparisons start "
                           "in November, against October.", None)]
    assert "September" not in set(daily.running_frame(daily.by_day(rows), late, "Household", since="2026-10")["series"])


def test_cards_per_day_last_usual_and_allowance():
    cards = {c["key"]: c for c in daily.cards(daily.pace(frame(), SAMPLE, "Household"))}
    assert list(cards) == ["per_day", "last", "usual", "allowance"]
    assert cards["per_day"]["value"] == "R$ 30,00"
    assert cards["per_day"]["lines"][0] == ("▲ R$ 15,00 (100%) more than usual", "more")
    assert cards["last"]["label"] == "Last month · September" and cards["last"]["value"] == "R$ 600,00"
    assert cards["last"]["lines"][0] == ("R$ 150,00 of it by the 10th", None)
    assert cards["usual"]["lines"][0] == ("The average of July–September", None)
    assert cards["allowance"]["label"] == "To stay within the usual month"
    assert cards["allowance"]["value"] == "R$ 4,76 a day"
    assert cards["allowance"]["lines"][1] == ("75% of the usual month spent, 32% of the month gone", "more")


def test_cards_when_already_past_the_usual_month():
    over = payload(SAMPLE["rows"] + [row("2026-10-05", "500.00")])
    card = daily.cards(daily.pace(daily.to_frame(over), over, "Household"))[-1]
    assert (card["label"], card["value"]) == ("Past the usual month", "R$ 400,00")


def test_cards_for_a_finished_month_count_days():
    finished = payload(SAMPLE["rows"], is_partial=False, as_of_day=31)
    card = daily.cards(daily.pace(frame(finished), finished, "Household"))[-1]
    assert (card["key"], card["value"]) == ("days", "2 of 31")


def test_history_compares_each_month_over_the_same_days():
    hist = daily.history(frame(), SAMPLE, "Household").set_index("month")
    assert list(hist.index) == list(MONTHS)
    assert hist.loc["2026-09", "total"] == 600.0 and hist.loc["2026-09", "to_day"] == 150.0
    assert hist.loc["2026-10", "per_day"] == 30.0 and hist.loc["2026-10", "is_selected"]


def test_usual_needs_three_months_of_history():
    short = payload([row("2026-09-03", "150.00"), row("2026-10-01", "80.00")])
    assert daily.usual_cumulative(daily.to_frame(short), short, "Household") is None
    usual = daily.usual_cumulative(frame(), SAMPLE, "Household")
    assert len(usual) == 31 and usual[31] == 400.0  # September's 30 days carry on to the 31st


def test_category_changes_say_where_the_difference_comes_from():
    rows = daily.rows_frame(SAMPLE)
    changes = daily.category_changes(rows, SAMPLE, "Household")
    # By the 10th: October has Food 80 and Pets 220; September had Food 150.
    assert list(zip(changes["name"], changes["change"])) == [("Pets", 220.0), ("Food", -70.0)]
    assert list(changes["change_brl"]) == ["▲ +R$ 220,00", "▼ -R$ 70,00"]
    assert daily.change_summary(changes, "September") == (
        "▲ R$ 150,00 (100%) more than September by the same day. Biggest moves: Pets ▲ R$ 220,00, "
        "Food ▼ R$ 70,00.")
    usual = daily.category_changes(rows, SAMPLE, "Household", against="usual")
    # Usual Food by the 10th: (100 (Jul 2nd) + 200 (Aug 5th) + 150 (Sep 3rd)) / 3 = 150.
    assert dict(zip(usual["name"], usual["then"])) == {"Pets": 0.0, "Food": 150.0}
    sub = daily.category_changes(rows, SAMPLE, "Household", level="sub_category")
    assert set(sub["name"]) == {"Pets › Vet", "Food › Groceries"}


def test_running_frame_series():
    out = daily.running_frame(frame(), SAMPLE, "Household")
    assert daily.series_order(SAMPLE) == ["October (so far)", "September", daily.USUAL]
    by = out.groupby("series")["day"].max().to_dict()
    assert by == {"October (so far)": 10, "September": 30, daily.USUAL: 31}
    assert out[(out["series"] == "October (so far)") & (out["day"] == 10)]["amount_brl"].item() == "R$ 300,00"
    assert daily.USUAL not in set(daily.running_frame(frame(), SAMPLE, "Household", with_usual=False)["series"])


def test_calendar_layout_states_and_future_days():
    cal = daily.calendar_frame(frame(), "2026-10", "Household", datetime.date(2026, 10, 10))
    first = cal.iloc[0]
    # 1 Oct 2026 is a Thursday: column 3 of the first row.
    assert (first["weekday"], first["week"], first["weekday_name"], first["amount"]) == (3, 0, "Thu", 80.0)
    assert cal.set_index("day").loc[10, "state"] == "today"
    future = cal.set_index("day").loc[11]
    assert (future["state"], future["amount"], future["count"]) == ("future", 0.0, 0)
    assert cal.set_index("day").loc[4, "top_category"] == "Pets"
    assert cal["week"].max() == 4


def test_weekday_profile_counts_quiet_days():
    one = payload([row("2026-10-05", "70.00")])  # a Monday
    profile = daily.weekday_profile(daily.to_frame(one), one, "Household", datetime.date(2026, 10, 18))
    # From the 5th to the 18th: two Mondays, one with 70 and one with nothing.
    mon = profile.set_index("weekday_name").loc["Mon"]
    assert (mon["average"], mon["days"]) == (35.0, 2)
    assert profile.set_index("weekday_name").loc["Tue", "average"] == 0.0


def test_biggest_days_biggest_first_with_their_top_category():
    top = daily.biggest_days(frame(), "2026-10", "Household")
    assert list(top["key"]) == ["2026-10-04", "2026-10-01"]
    assert list(top["name"]) == ["Sun 4 Oct", "Thu 1 Oct"]
    assert list(top["text"]) == ["R$ 220 · Pets", "R$ 80 · Food"]
    assert round(top["share"].sum(), 6) == 1.0  # of the month so far
    assert list(daily.biggest_days(frame(), "2026-10", "Household", n=1)["key"]) == ["2026-10-04"]


def test_ranked_shares_a_month_by_category_and_a_day_by_item():
    rows = daily.rows_frame(payload([
        row("2026-10-01", "60.00"), row("2026-10-01", "20.00", sub="Delivery"),
        row("2026-10-04", "220.00", "Pets", "Vet"), row("2026-09-04", "999.00", "Pets", "Vet"),
    ]))
    mix = daily.ranked(rows, "Household", "primary_category", month="2026-10")
    assert list(mix["key"]) == ["Pets", "Food"]  # September's vet bill isn't this month
    assert list(mix["text"]) == ["R$ 220 · 73%", "R$ 80 · 27%"]  # the value at each bar's tip
    day = daily.ranked(rows, "My share", "item", date="2026-10-01")
    assert list(day["name"]) == ["Food › Groceries", "Food › Delivery"]
    assert list(day["amount"]) == [36.0, 12.0]
    assert daily.ranked(rows, "Household", "primary_category", month="2026-11").empty


def test_day_items_are_a_days_purchases_biggest_first():
    from zoneinfo import ZoneInfo
    items = [
        {"transaction_timestamp": "2026-10-05T12:30:00Z", "primary_category": "Food", "sub_category": "Groceries",
         "price": "100.00", "mine": "60.00", "payment_method": "Pix", "institution": "Nubank", "paid_by": "Her"},
        {"transaction_timestamp": "2026-10-05T18:00:00Z", "primary_category": "Pets", "sub_category": "Food",
         "price": "300.00", "mine": "180.00", "payment_method": "Cash", "institution": None, "paid_by": "Me"},
        {"transaction_timestamp": "2026-10-05T12:30:00Z", "primary_category": "Food", "sub_category": "Groceries",
         "price": "100.00", "mine": "60.00", "payment_method": "Pix", "institution": "Nubank", "paid_by": "Her"},
    ]
    frame = daily.day_items(items, "Household", ZoneInfo("America/Sao_Paulo"))
    # "Food" alone would read as the Food category: the pets' food keeps its category.
    assert list(frame["name"]) == ["Pets › Food · 15:00", "Groceries · 09:30", "Groceries · 09:30 (2)"]
    assert list(frame["text"]) == ["R$ 300 · 60%", "R$ 100 · 20%", "R$ 100 · 20%"]
    assert frame["detail"].iloc[1] == "Pix · Nubank, paid by Her"
    assert list(daily.day_items(items, "My share", ZoneInfo("UTC"))["amount"]) == [180.0, 60.0, 60.0]
    assert daily.day_items([], "Household", ZoneInfo("UTC")).empty


def test_empty_payload_is_handled():
    empty = payload([])
    df = daily.to_frame(empty)
    assert df.empty and daily.rows_frame(empty).empty
    assert daily.weekday_profile(df, empty, "Household", datetime.date(2026, 10, 10)).empty
    assert daily.biggest_days(df, "2026-10", "Household").empty
    assert daily.ranked(daily.rows_frame(empty), "Household", "primary_category", month="2026-10").empty
    assert daily.category_changes(daily.rows_frame(empty), empty, "Household").empty


@pytest.mark.parametrize("partial", [True, False])
def test_chart_specs_build(partial):
    p = payload([row("2026-09-03", "150.00"), row("2026-10-04", "220.00", "Pets", "Vet")],
                is_partial=partial, as_of_day=10 if partial else 31)
    df = daily.to_frame(p)
    daily_charts.running_total_chart(daily.running_frame(df, p, "Household"), daily.series_order(p), 31,
                                     10 if partial else None, "t").to_dict()
    daily_charts.spark_running(daily.running_frame(df, p, "Household", with_usual=False),
                               daily.series_order(p), 31).to_dict()
    hist = daily.history(df, p, "Household")
    daily_charts.spark_bars(hist, "per_day", "Per day", reference=12.0).to_dict()
    daily_charts.spark_progress(0.7, 0.3).to_dict()
    cal = daily.calendar_frame(df, "2026-10", "Household", datetime.date(2026, 10, 10))
    daily_charts.spark_days(cal).to_dict()
    daily_charts.weekday_chart(daily.weekday_profile(df, p, "Household", datetime.date(2026, 10, 10))).to_dict()
    daily_charts.changes_chart(daily.category_changes(daily.rows_frame(p), p, "Household")).to_dict()
    assert daily_charts.spark_days(cal).to_dict()["config"]["background"] == "transparent"


def test_calendar_scale_ignores_one_huge_day():
    cal = daily.calendar_frame(frame(), "2026-10", "Household", datetime.date(2026, 10, 31))
    big = cal.assign(amount=[1900.0 if d == 5 else (50.0 if d % 2 else 0.0) for d in cal["day"]])
    assert daily.calendar_scale_max(big) == 50.0  # the 90th percentile of spending days, not the 1.900
    assert daily.calendar_scale_max(cal.assign(amount=0.0)) == 1.0



# --- a partly logged last month: shown for context, never a verdict -----------

PARTLY = payload([row("2026-09-28", "300.00"), row("2026-09-30", "100.00"),
                  row("2026-10-02", "50.00"), row("2026-10-05", "70.00")], months=("2026-09", "2026-10"))


def test_partly_logged_from_only_for_a_month_logging_began_late_in():
    started = datetime.date(2026, 9, 28)
    assert daily.partly_logged_from("2026-09", "2026-10", started) == 28
    assert daily.partly_logged_from("2026-09", "2026-09", datetime.date(2026, 9, 3)) is None  # logged in full
    assert daily.partly_logged_from("2026-08", "2026-10", started) is None  # before logging began


def test_a_partly_logged_last_month_is_drawn_and_named_but_not_compared():
    rows = daily.rows_frame(PARTLY)
    df, since, started = daily.by_day(rows), daily.tracked_since(rows), daily.logging_started(rows)
    p = daily.pace(df, PARTLY, "Household", since=since, started=started)
    assert (p["has_last"], p["last_partly_from"], p["last_total"]) == (False, 28, 400.0)
    head = daily.headline(p, started=started)
    texts = [t for t, _ in head["lines"]]
    assert texts[0] == "September: R$ 400,00, logged from the 28th only"
    assert texts[1] == "Comparisons start in November, against October."
    assert all(tone is None for _, tone in head["lines"])  # no ▲/▼ against a partial month
    last = next(c for c in daily.cards(p) if c["key"] == "last")
    assert last["value"] == "R$ 400,00" and "Logged only from the 28th" in last["lines"][0][0]
    # The running total draws it, named for what it is.
    order = daily.series_order(PARTLY, p["last_partly_from"])
    frame = daily.running_frame(df, PARTLY, "Household", since=since, started=started)
    assert order[1] == "September (from the 28th)"
    assert frame[frame["series"] == order[1]]["amount"].max() == 400.0
    # Without `started` it stays out, as before.
    assert order[1] not in set(daily.running_frame(df, PARTLY, "Household", since=since)["series"])


def test_against_last_month_adds_a_tick_by_the_same_day():
    rows = daily.rows_frame(SAMPLE)
    mix = daily.ranked(rows, "Household", "primary_category", month="2026-10")
    bullet = daily.against_last_month(mix, rows, "Household", "primary_category", "2026-10", 10)
    # By the 10th of September: groceries on the 3rd (150); the rent on the 15th isn't counted yet.
    assert dict(zip(bullet["name"], bullet["previous"])) == {"Pets": 0.0, "Food": 150.0}
    assert bullet.loc[bullet["name"] == "Food", "previous_brl"].iloc[0] == "R$ 150,00"
    # With the tick there, the tip says the change: Food 80 against 150, Pets new.
    assert list(bullet["text"]) == ["R$ 220 · new", "R$ 80 · ▼ 47%"]
