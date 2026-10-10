"""GET /analytics/shared and /analytics/shared/expenses — shared expenses only, two lenses."""
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

import main
from conftest import expenditure_payload, signup_and_login, splits_for

D = Decimal
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


class FrozenDatetime(datetime):
    """datetime whose now() is 2026-10-10 12:00 in São Paulo, so 'today' is fixed."""
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 10, 12, 0, tzinfo=SAO_PAULO).astimezone(tz)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(main, "datetime", FrozenDatetime)


def spend(client, household, who, price, is_shared=True, when="2026-10-08T12:00:00-03:00", **extra):
    payload = expenditure_payload(household, price=price, is_shared=is_shared, transaction_timestamp=when, **extra)
    resp = client.post("/expenditures/", headers=household[who], json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def analytics(client, headers, **params):
    resp = client.get("/analytics/shared", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def expenses(client, headers, **params):
    resp = client.get("/analytics/shared/expenses", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def total(rows, field, month=None):
    return sum((D(r[field]) for r in rows if month is None or r["month"] == month), D("0"))


def add_category(client, household, primary, sub, cost_type="Variable"):
    resp = client.post("/categories/", headers=household["a"], json={
        "primary_category": primary, "sub_category": sub, "cost_type": cost_type,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["category_id"]


def test_empty_window(client, household):
    a = analytics(client, household["a"], month="2026-10", months=3)
    assert a == {
        "month": "2026-10", "months": ["2026-08", "2026-09", "2026-10"],
        "is_partial": True, "as_of_day": 10, "rows": [],
    }


def test_totals_are_shared_prices_and_my_share_rows(client, household):
    spend(client, household, "a", "100.00")
    spend(client, household, "b", "50.00")
    spend(client, household, "a", "20.00", is_shared=False)  # my own personal: excluded too
    for who in ("a", "b"):
        rows = analytics(client, household[who], month="2026-10")["rows"]
        assert total(rows, "household") == D("150.00")
        assert sum(r["count"] for r in rows) == 2
    # Alice bears 60% of 100 and 60% of 50.
    rows_a = analytics(client, household["a"], month="2026-10")["rows"]
    assert total(rows_a, "mine") == D("90.00")
    rows_b = analytics(client, household["b"], month="2026-10")["rows"]
    assert total(rows_b, "mine") == D("60.00")


def test_mine_matches_split_table(client, household):
    spend(client, household, "a", "33.33")
    spend(client, household, "b", "10.01")
    expected = D("0")
    for e in expenses(client, household["a"], month="2026-10"):
        rows = splits_for(e["expenditure_id"])
        mine = next(r for r in rows if r["user_id"] == household["a_id"])
        assert D(e["mine"]) == mine["share_amount"]
        expected += mine["share_amount"]
    assert total(analytics(client, household["a"], month="2026-10")["rows"], "mine") == expected


def test_partners_personal_spending_never_changes_my_view(client, household):
    spend(client, household, "a", "100.00")
    before = analytics(client, household["a"], month="2026-10")
    before_list = expenses(client, household["a"], month="2026-10")
    spend(client, household, "b", "999.99", is_shared=False)
    assert analytics(client, household["a"], month="2026-10") == before
    assert expenses(client, household["a"], month="2026-10") == before_list


def test_outsider_sees_nothing(client, household):
    spend(client, household, "a", "100.00")
    spend(client, household, "b", "50.00")
    _, carol = signup_and_login(client, "carol")
    a = analytics(client, carol, month="2026-10")
    assert a["rows"] == [] and len(a["months"]) == 12
    assert expenses(client, carol, month="2026-10") == []


def test_expense_i_paid_but_put_on_my_partner(client, household):
    # Bob paid, but a manual split puts it all on Alice. It's still household
    # spending Bob can see in the Tracker, so it counts in his Household lens,
    # with nothing in his "mine".
    spend(client, household, "b", "80.00", shares=[{"user_id": household["a_id"], "share_pct": "1"}])
    assert total(analytics(client, household["a"], month="2026-10")["rows"], "mine") == D("80.00")
    bob = analytics(client, household["b"], month="2026-10")["rows"]
    assert total(bob, "household") == D("80.00")
    assert total(bob, "mine") == D("0.00")
    assert total(bob, "mine_to_day") == D("0.00")
    [listed] = expenses(client, household["b"], month="2026-10")
    assert D(listed["price"]) == D("80.00") and D(listed["mine"]) == D("0") and D(listed["share_pct"]) == D("0")


def test_month_is_sao_paulo_calendar_month(client, household):
    # 01:00 UTC on 1 Oct is 22:00 on 30 Sep in São Paulo.
    spend(client, household, "a", "100.00", when="2026-10-01T01:00:00Z")
    rows = analytics(client, household["a"], month="2026-10")["rows"]
    assert [r["month"] for r in rows] == ["2026-09"]
    assert expenses(client, household["a"], month="2026-10") == []
    assert len(expenses(client, household["a"], month="2026-09")) == 1


def test_to_day_cuts_other_months_at_todays_day(client, household):
    # Today is frozen at 10 Oct, so every month is compared over days 1..10.
    spend(client, household, "a", "100.00", when="2026-09-10T23:00:00-03:00")  # day 10: counts
    spend(client, household, "a", "50.00", when="2026-09-11T00:30:00-03:00")   # day 11: doesn't
    spend(client, household, "a", "30.00", when="2026-10-09T12:00:00-03:00")
    a = analytics(client, household["a"], month="2026-10")
    assert a["is_partial"] is True and a["as_of_day"] == 10
    assert total(a["rows"], "household", "2026-09") == D("150.00")
    assert total(a["rows"], "household_to_day", "2026-09") == D("100.00")
    assert total(a["rows"], "mine_to_day", "2026-09") == D("60.00")
    assert total(a["rows"], "household_to_day", "2026-10") == D("30.00")


def test_past_month_is_complete(client, household):
    spend(client, household, "a", "50.00", when="2026-09-30T20:00:00-03:00")
    a = analytics(client, household["a"], month="2026-09")
    assert a["is_partial"] is False and a["as_of_day"] == 30
    assert total(a["rows"], "household_to_day") == total(a["rows"], "household") == D("50.00")
    assert analytics(client, household["a"], month="2027-02")["as_of_day"] == 28


def test_window_ends_at_month_and_crosses_years(client, household):
    spend(client, household, "a", "10.00", when="2026-07-15T12:00:00-03:00")  # outside a 3-month window
    spend(client, household, "a", "20.00", when="2026-08-15T12:00:00-03:00")
    spend(client, household, "a", "40.00", when="2026-11-15T12:00:00-03:00")  # after the window
    a = analytics(client, household["a"], month="2026-10", months=3)
    assert a["months"] == ["2026-08", "2026-09", "2026-10"]
    assert {r["month"] for r in a["rows"]} == {"2026-08"}  # empty months simply have no rows
    assert total(a["rows"], "household") == D("20.00")
    assert analytics(client, household["a"], month="2027-01", months=3)["months"] == ["2026-11", "2026-12", "2027-01"]
    assert len(analytics(client, household["a"])["months"]) == 12


def test_defaults_to_current_month(client, household):
    a = analytics(client, household["a"])
    assert a["month"] == "2026-10" and a["months"][-1] == "2026-10"


def test_rows_split_by_category(client, household):
    rent = add_category(client, household, "Housing", "Rent", "Fixed")
    spend(client, household, "a", "1000.00", category_id=rent)
    spend(client, household, "a", "100.00")
    spend(client, household, "b", "40.00")
    rows = analytics(client, household["a"], month="2026-10")["rows"]
    by = {(r["primary_category"], r["sub_category"], r["cost_type"]): (D(r["household"]), D(r["mine"]), r["count"]) for r in rows}
    assert by == {
        ("Housing", "Rent", "Fixed"): (D("1000.00"), D("600.00"), 1),
        ("Food", "Groceries", "Variable"): (D("140.00"), D("84.00"), 2),
    }


def test_expenses_route_lists_and_filters_by_category(client, household):
    rent = add_category(client, household, "Housing", "Rent", "Fixed")
    spend(client, household, "b", "1000.00", category_id=rent, when="2026-10-05T12:00:00-03:00")
    spend(client, household, "a", "100.00", when="2026-10-07T12:00:00-03:00")
    spend(client, household, "a", "5.00", is_shared=False)
    everything = expenses(client, household["a"], month="2026-10")
    assert [D(e["price"]) for e in everything] == [D("100.00"), D("1000.00")]  # newest first
    food = expenses(client, household["a"], month="2026-10", primary_category="Food")
    assert len(food) == 1
    e = food[0]
    assert e["primary_category"] == "Food" and e["sub_category"] == "Groceries"
    assert e["paid_by"] == "alice" and e["payment_method"] == "Pix"
    assert D(e["price"]) == D("100.00") and D(e["mine"]) == D("60.00") and D(e["share_pct"]) == D("0.6")
    assert e["total_installments"] == 1 and e["nature"] == "Normal"
    housing = expenses(client, household["b"], month="2026-10", primary_category="Housing")
    assert [(e["paid_by"], D(e["mine"])) for e in housing] == [("bob", D("400.00"))]
    assert expenses(client, household["a"], month="2026-10", primary_category="Travel") == []


@pytest.mark.parametrize("path", ["/analytics/shared", "/analytics/shared/expenses"])
def test_invalid_month_is_a_422(client, household, path):
    for bad in ("2026-13", "2026-1", "october"):
        assert client.get(path, headers=household["a"], params={"month": bad}).status_code == 422


def test_months_out_of_range_is_a_422(client, household):
    for bad in (0, 25):
        assert client.get("/analytics/shared", headers=household["a"], params={"months": bad}).status_code == 422
