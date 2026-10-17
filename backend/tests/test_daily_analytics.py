"""/analytics/{shared,personal}/daily: spending per São Paulo day, with the same privacy rules as the monthly routes."""
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

import main
from conftest import expenditure_payload

D = Decimal
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


class FrozenDatetime(datetime):
    """Today is 10 Oct 2026 in São Paulo."""
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 10, 12, 0, tzinfo=SAO_PAULO).astimezone(tz)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(main, "datetime", FrozenDatetime)


def spend(client, h, who, price, when, is_shared=True, **extra):
    resp = client.post("/expenditures/", headers=h[who], json=expenditure_payload(
        h, price=price, transaction_timestamp=when, is_shared=is_shared, allow_duplicate=True, **extra))
    assert resp.status_code == 200, resp.text


def daily(client, headers, scope="shared", **params):
    resp = client.get(f"/analytics/{scope}/daily", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_rows_per_sao_paulo_day_and_category_with_both_amounts(client, household):
    spend(client, household, "a", "100.00", "2026-10-03T10:00:00-03:00")
    spend(client, household, "b", "50.00", "2026-10-03T21:00:00-03:00")
    spend(client, household, "a", "30.00", "2026-10-04T23:30:00-03:00")  # already the 5th in UTC
    data = daily(client, household["a"], month="2026-10", months=2)
    assert (data["month"], data["months"], data["is_partial"], data["as_of_day"], data["today"]) == (
        "2026-10", ["2026-09", "2026-10"], True, 10, "2026-10-10")
    assert [(r["date"], D(r["household"]), D(r["mine"]), r["count"]) for r in data["rows"]] == [
        ("2026-10-03", D("150.00"), D("90.00"), 2),  # 60% of each
        ("2026-10-04", D("30.00"), D("18.00"), 1),
    ]
    row = data["rows"][0]
    assert (row["primary_category"], row["sub_category"], row["cost_type"], row["nature"]) == (
        "Food", "Groceries", "Variable", "Normal")


def test_rows_split_by_category_cost_type_and_nature(client, household):
    tax = client.post("/categories/", headers=household["a"], json={
        "primary_category": "Transport", "sub_category": "IPVA", "cost_type": "Fixed"}).json()["category_id"]
    spend(client, household, "a", "40.00", "2026-10-03T10:00:00-03:00")
    spend(client, household, "a", "30.00", "2026-10-03T11:00:00-03:00")
    spend(client, household, "a", "900.00", "2026-10-03T12:00:00-03:00", category_id=tax, nature="Annual")
    rows = daily(client, household["a"], month="2026-10")["rows"]
    assert [(r["primary_category"], r["cost_type"], r["nature"], D(r["household"]), r["count"]) for r in rows] == [
        ("Food", "Variable", "Normal", D("70.00"), 2),
        ("Transport", "Fixed", "Annual", D("900.00"), 1),
    ]


def test_only_the_window_and_only_shared(client, household):
    spend(client, household, "a", "10.00", "2026-06-30T10:00:00-03:00")              # before a 4-month window
    spend(client, household, "a", "20.00", "2026-07-01T10:00:00-03:00")
    spend(client, household, "a", "99.00", "2026-10-02T10:00:00-03:00", is_shared=False)
    data = daily(client, household["a"], month="2026-10", months=4)
    assert data["months"] == ["2026-07", "2026-08", "2026-09", "2026-10"]
    assert [r["date"] for r in data["rows"]] == ["2026-07-01"]
    assert len(daily(client, household["a"], month="2026-10")["months"]) == 7  # the default window


def test_personal_daily_is_only_mine(client, household):
    spend(client, household, "a", "25.00", "2026-10-02T10:00:00-03:00", is_shared=False)
    spend(client, household, "b", "70.00", "2026-10-02T10:00:00-03:00", is_shared=False)  # bob's: never alice's
    spend(client, household, "a", "100.00", "2026-10-02T10:00:00-03:00")                 # shared: not personal
    [day] = daily(client, household["a"], scope="personal", month="2026-10")["rows"]
    assert (D(day["household"]), D(day["mine"]), day["count"]) == (D("25.00"), D("25.00"), 1)


def test_a_past_month_is_complete(client, household):
    data = daily(client, household["a"], month="2026-09")
    assert (data["is_partial"], data["as_of_day"]) == (False, 30)


def test_expense_lists_can_be_asked_for_one_day(client, household):
    spend(client, household, "a", "100.00", "2026-10-03T10:00:00-03:00")
    spend(client, household, "a", "40.00", "2026-10-04T23:30:00-03:00")
    rows = client.get("/analytics/shared/expenses", headers=household["b"], params={"day": "2026-10-04"}).json()
    assert [D(r["price"]) for r in rows] == [D("40.00")]
    spend(client, household, "a", "12.00", "2026-10-04T09:00:00-03:00", is_shared=False)
    mine = client.get("/analytics/personal/expenses", headers=household["a"], params={"day": "2026-10-04"}).json()
    assert [D(r["price"]) for r in mine] == [D("12.00")]
