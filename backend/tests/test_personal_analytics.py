"""/analytics/personal: only ever the caller's own personal expenses, shaped like /analytics/shared."""
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


def spend(client, h, who, price, when, is_shared=False, **extra):
    resp = client.post("/expenditures/", headers=h[who], json=expenditure_payload(
        h, price=price, is_shared=is_shared, transaction_timestamp=when, **extra))
    assert resp.status_code == 200, resp.text


def personal(client, headers, **params):
    resp = client.get("/analytics/personal", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_only_my_personal_expenses(client, household):
    spend(client, household, "a", "30.00", "2026-10-05T10:00:00-03:00")                  # mine, personal
    spend(client, household, "a", "100.00", "2026-10-05T10:00:00-03:00", is_shared=True)  # shared: not here
    spend(client, household, "b", "70.00", "2026-10-05T10:00:00-03:00")                  # bob's personal: never
    data = personal(client, household["a"], month="2026-10", months=3)
    assert data["months"] == ["2026-08", "2026-09", "2026-10"]
    assert [(r["month"], D(r["household"]), D(r["mine"]), r["count"]) for r in data["rows"]] == [
        ("2026-10", D("30.00"), D("30.00"), 1),
    ]
    # And bob sees only his own.
    assert [D(r["mine"]) for r in personal(client, household["b"], month="2026-10")["rows"]] == [D("70.00")]


def test_month_in_progress_is_compared_by_days(client, household):
    spend(client, household, "a", "20.00", "2026-09-05T10:00:00-03:00")  # day 5: within days 1..10
    spend(client, household, "a", "80.00", "2026-09-25T10:00:00-03:00")  # day 25: after
    data = personal(client, household["a"], month="2026-10", months=2)
    assert (data["is_partial"], data["as_of_day"]) == (True, 10)
    [sept] = data["rows"]
    assert (D(sept["mine"]), D(sept["mine_to_day"])) == (D("100.00"), D("20.00"))


def test_a_custom_split_that_leaves_the_payer_alone_is_personal(client, household):
    # 100% on the payer: nobody else holds a share, so it's personal.
    spend(client, household, "a", "40.00", "2026-10-05T10:00:00-03:00", is_shared=True, shares=[
        {"user_id": household["a_id"], "share_pct": "1"},
    ])
    assert [D(r["mine"]) for r in personal(client, household["a"], month="2026-10")["rows"]] == [D("40.00")]


def test_expenses_drilldown_lists_mine_newest_first(client, household):
    spend(client, household, "a", "10.00", "2026-10-02T10:00:00-03:00")
    spend(client, household, "a", "25.00", "2026-10-04T10:00:00-03:00")
    spend(client, household, "b", "99.00", "2026-10-03T10:00:00-03:00")
    resp = client.get("/analytics/personal/expenses", headers=household["a"],
                      params={"month": "2026-10", "primary_category": "Food"})
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert [(D(r["price"]), D(r["mine"]), D(r["share_pct"]), r["paid_by"]) for r in rows] == [
        (D("25.00"), D("25.00"), D("1"), "alice"),
        (D("10.00"), D("10.00"), D("1"), "alice"),
    ]
    assert client.get("/analytics/personal/expenses", headers=household["a"],
                      params={"month": "2026-10", "primary_category": "Home"}).json() == []
