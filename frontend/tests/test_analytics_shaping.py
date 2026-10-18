import math

import pytest

import analytics_charts as charts
import analytics_shaping as shape
from conftest import empty_payload, sample_payload


@pytest.fixture
def df():
    return shape.to_frame(sample_payload())


@pytest.fixture
def months():
    return sample_payload()["months"]


# --- months --------------------------------------------------------------

def test_shift_month_crosses_years():
    assert shape.shift_month("2026-01", -1) == "2025-12"
    assert shape.shift_month("2025-12", 1) == "2026-01"
    assert shape.shift_month("2026-10", -12) == "2025-10"


def test_month_options_newest_first():
    options = shape.month_options("2026-02", 4)
    assert options == ["2026-02", "2026-01", "2025-12", "2025-11"]


def test_month_label():
    assert shape.month_label("2026-10") == "Oct 2026"
    assert shape.month_label("2026-01", short=True) == "Jan 26"


# --- frame and totals ----------------------------------------------------

def test_to_frame_parses_amounts():
    frame = shape.to_frame(sample_payload())
    assert frame["household"].dtype == float and frame["count"].dtype == int
    assert frame["household"].sum() == pytest.approx(10250.0)


def test_to_frame_empty_is_typed():
    frame = shape.to_frame(empty_payload())
    assert frame.empty and list(frame.columns) == shape.ROW_COLUMNS
    assert shape.to_frame(None).empty


def test_monthly_totals_zero_fill_in_window_order(df, months):
    totals = shape.monthly_totals(df, months, "Household")
    assert list(totals.index) == months
    assert totals["2025-11"] == 0.0 and totals["2026-06"] == 0.0
    assert totals["2026-09"] == 2980.0 and totals["2026-10"] == 2370.0
    assert shape.monthly_totals(df, months, "My share")["2026-10"] == 1422.0
    assert shape.monthly_totals(df, months, "Household", to_day=True)["2026-09"] == 2150.0


def test_monthly_totals_of_nothing_are_zeros(months):
    totals = shape.monthly_totals(shape.to_frame(empty_payload()), months, "Household")
    assert list(totals.index) == months and (totals == 0).all()


def test_expense_count(df):
    assert shape.expense_count(df, "2026-10") == 6
    assert shape.expense_count(df, "2026-01") == 0


# --- comparisons ---------------------------------------------------------

def test_partial_month_compares_with_same_days_of_previous(df):
    comp = shape.compare(df, "2026-10", True, "Household")
    assert list(comp["primary_category"]) == ["Housing", "Food"]  # largest first
    food = comp.set_index("primary_category").loc["Food"]
    assert (food["current"], food["previous"], food["change"]) == (370.0, 150.0, 220.0)
    assert food["pct"] == pytest.approx(220 / 150)
    # Leisure: 80 in September, but nothing in its first ten days, nor in October.
    assert "Leisure" not in set(comp["primary_category"])


def test_complete_month_compares_with_whole_previous_month(df):
    comp = shape.compare(df, "2026-10", False, "Household").set_index("primary_category")
    assert comp.loc["Food", "previous"] == 900.0
    assert comp.loc["Leisure", "current"] == 0.0 and comp.loc["Leisure", "pct"] == -1.0


def test_new_category_has_no_pct():
    payload = sample_payload()
    payload["rows"].append({
        "month": "2026-10", "primary_category": "Travel", "sub_category": "Flights", "cost_type": "Variable",
        "household": "500.00", "mine": "300.00", "count": 1, "household_to_day": "500.00", "mine_to_day": "300.00",
    })
    comp = shape.compare(shape.to_frame(payload), "2026-10", True, "Household").set_index("primary_category")
    assert math.isnan(comp.loc["Travel", "pct"])
    assert shape.biggest_increase(comp.reset_index()) == "Travel"


def test_compare_by_sub_category_with_filter(df):
    sub = shape.compare(df, "2026-10", True, "My share", by="sub_category", where={"primary_category": "Food"})
    assert list(sub["sub_category"]) == ["Groceries", "Restaurants"]
    assert list(sub["current"]) == [150.0, 72.0]
    assert list(sub["previous"]) == [90.0, 0.0]


def test_compare_total(df):
    total = shape.compare_total(df, "2026-10", True, "Household")
    assert total == {"current": 2370.0, "previous": 2150.0, "change": 220.0, "pct": pytest.approx(220 / 2150)}
    empty = shape.compare_total(shape.to_frame(empty_payload()), "2026-10", True, "Household")
    assert empty["current"] == 0.0 and math.isnan(empty["pct"])


def test_previous_full_average(df, months):
    assert shape.previous_full_average(df, months, "2026-10", "Household") == pytest.approx(2626.67)
    assert shape.previous_full_average(df, months, "2026-10", "Household", to_day=True) == 2150.0
    # September would need June, before the first month with any data.
    assert shape.previous_full_average(df, months, "2026-09", "Household") is None
    # Months outside the window can't be averaged.
    assert shape.previous_full_average(df, months[-3:], "2026-10", "Household") is None
    assert shape.previous_full_average(shape.to_frame(empty_payload()), months, "2026-10", "Household") is None


def test_biggest_increase_and_changes(df):
    rising = shape.compare(df, "2026-10", True, "Household")
    assert shape.biggest_increase(rising) == "Food"
    assert list(shape.biggest_changes(rising)["primary_category"]) == ["Food"]  # Housing didn't change

    falling = shape.compare(df, "2026-10", False, "Household")
    assert shape.biggest_increase(falling) is None
    assert list(shape.biggest_changes(falling)["primary_category"]) == ["Food", "Leisure"]
    assert shape.biggest_increase(falling.iloc[0:0]) is None


def test_heatmap_frame_is_zero_filled(df, months):
    long = shape.heatmap_frame(df, months, "Household")
    assert len(long) == 3 * 12
    assert list(dict.fromkeys(long["primary_category"])) == ["Housing", "Food", "Leisure"]
    cell = long[(long["primary_category"] == "Leisure") & (long["month"] == "2026-10")]
    assert cell["amount"].item() == 0.0
    assert shape.heatmap_frame(shape.to_frame(empty_payload()), months, "Household").empty


def test_cost_type_split_shares(df):
    split = shape.cost_type_split(df, "2026-10", True, "Household").set_index("cost_type")
    assert split.loc["Fixed", "current"] == 2000.0 and split.loc["Variable", "previous"] == 150.0
    assert split["current_share"].sum() == pytest.approx(1.0)
    assert split.loc["Fixed", "current_share"] == pytest.approx(2000 / 2370)


# --- text ----------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [(12.5, "+R$ 12,50"), (-3, "-R$ 3,00"), (0, "R$ 0,00"), (1234.5, "+R$ 1.234,50")])
def test_signed_brl(value, expected):
    assert shape.signed_brl(value) == expected


def test_pct_and_delta_text():
    assert shape.pct_text(0.125) == "+12,5%"
    assert shape.pct_text(-0.5) == "-50,0%"
    assert shape.pct_text(float("nan")) == "new"
    assert shape.delta_text(220, 220 / 150) == "+R$ 220,00 (+146,7%)"
    assert shape.delta_text(50, float("nan")) == "+R$ 50,00 (new)"


@pytest.mark.parametrize("value, expected", [
    (0, "R$ 0"), (812.4, "R$ 812"), (1234, "R$ 1,2 mil"), (25000, "R$ 25,0 mil"), (1_500_000, "R$ 1,5 mi"), (-2000, "-R$ 2,0 mil"),
])
def test_short_brl(value, expected):
    assert shape.short_brl(value) == expected


# --- charts build valid Vega-Lite ----------------------------------------

def test_charts_build(df, months):
    totals = shape.monthly_totals(df, months, "Household")
    comp = shape.compare(df, "2026-10", True, "Household")
    for chart in (
        charts.trend_chart(totals, "2026-10", True, 2626.67),
        charts.trend_chart(totals, "2026-10", False, None),
        charts.ranked_bars(shape.ranked_comparison(comp, "primary_category"), picked="Food", previous="previous"),
        charts.ranked_bars(shape.ranked_comparison(comp.iloc[0:0], "primary_category")),
        charts.heatmap_chart(shape.heatmap_frame(df, months, "Household"), months),
        charts.cost_type_chart(shape.cost_type_split(df, "2026-10", True, "Household"), "Oct 26", "Sep 26"),
    ):
        spec = chart.to_dict()
        assert "layer" in spec or "mark" in spec or "facet" in spec
        assert spec["config"]["background"] == "transparent"  # charts sit on their card's white


def test_ranked_comparison_says_the_move_at_the_tip(df):
    comp = shape.compare(df, "2026-10", True, "Household")
    bars = shape.ranked_comparison(comp, "primary_category").set_index("name")
    assert bars.loc["Food", "text"].startswith("R$ ") and "▲" in bars.loc["Food", "text"]
    assert (bars["amount"] == comp.set_index("primary_category")["current"]).all()


def test_as_changes_drops_the_unchanged_and_points_the_arrows(df):
    changes = shape.as_changes(shape.compare(df, "2026-10", True, "Household"), "primary_category")
    assert (changes["change"] != 0).all()
    assert set(changes["direction"]) <= {"more", "less"}
    assert all(t.startswith(("▲ +", "▼ ")) for t in changes["change_brl"])


def test_month_bars_and_counts(df, months):
    bars = shape.month_bars(shape.monthly_totals(df, months, "Household"), "2026-10")
    assert list(bars["is_selected"]) == [m == "2026-10" for m in months]
    assert bars["label"].iloc[-1] == "Oct"
    counts = shape.monthly_counts(df, months)
    assert list(counts.index) == months and counts.dtype.kind == "i"




# --- months logged in full ----------------------------------------------------

def test_tracked_since_and_partly_logged_from():
    assert shape.tracked_since("2026-09-26") == "2026-10"  # began late in September
    assert shape.tracked_since("2026-09-05") == "2026-09"  # early enough to count
    assert shape.tracked_since(None) is None
    assert shape.partly_logged_from("2026-09", "2026-09-26") == 26
    assert shape.partly_logged_from("2026-09", "2026-09-05") is None
    assert shape.partly_logged_from("2026-08", "2026-09-26") is None
    assert [shape.ordinal(n) for n in (1, 2, 3, 11, 22, 26)] == ["1st", "2nd", "3rd", "11th", "22nd", "26th"]


def test_merged_payloads_start_with_the_earliest_first_date():
    a = {"month": "2026-10", "rows": [], "first_date": "2026-09-26"}
    b = {"month": "2026-10", "rows": [], "first_date": "2026-08-02"}
    assert shape.merge_payloads({"shared": a, "personal": b})["first_date"] == "2026-08-02"
    assert shape.merge_payloads({"shared": {"month": "2026-10", "rows": []}})["first_date"] is None


def test_the_three_month_average_waits_for_months_logged_in_full(df, months):
    assert shape.previous_full_average(df, months, "2026-10", "Household") is not None
    assert shape.previous_full_average(df, months, "2026-10", "Household", since="2026-08") is None


def test_share_text_when_there_is_no_fair_comparison(df):
    bars = shape.with_share_text(shape.ranked_comparison(shape.compare(df, "2026-10", True, "Household"),
                                                         "primary_category"))
    assert all("%" in t and "▲" not in t and "new" not in t for t in bars["text"])
