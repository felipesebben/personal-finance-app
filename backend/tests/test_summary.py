"""GET /summary/ — the logged-in user's month, by category and cost type."""
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from conftest import expenditure_payload

D = Decimal


def spend(client, household, who, price, is_shared=True, when="2026-10-08T12:00:00-03:00", category_id=None):
    payload = expenditure_payload(household, price=price, is_shared=is_shared, transaction_timestamp=when)
    if category_id:
        payload["category_id"] = category_id
    resp = client.post("/expenditures/", headers=household[who], json=payload)
    assert resp.status_code == 200, resp.text


def summary(client, household, who="a", month="2026-10"):
    params = {"month": month} if month else {}
    resp = client.get("/summary/", headers=household[who], params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def amounts(items):
    return [(i["label"], D(i["amount"])) for i in items]


def test_empty_month(client, household):
    s = summary(client, household)
    assert s["month"] == "2026-10" and s["previous_month"] == "2026-09"
    assert {k: D(v) for k, v in s["me"].items()} == {
        "total": 0, "previous_total": 0, "shared_share": 0, "personal": 0,
    }
    assert s["by_category"] == [] and s["by_cost_type"] == []


def test_my_total_is_my_share_plus_my_personal(client, household):
    spend(client, household, "a", "100.00")                  # A bears 60
    spend(client, household, "b", "50.00")                   # A bears 30
    spend(client, household, "a", "20.00", is_shared=False)  # A bears 20
    me = summary(client, household, "a")["me"]
    assert D(me["shared_share"]) == D("90.00")
    assert D(me["personal"]) == D("20.00")
    assert D(me["total"]) == D("110.00")


def test_other_persons_personal_spending_stays_private(client, household):
    spend(client, household, "b", "999.99", is_shared=False)
    s = summary(client, household, "a")
    assert D(s["me"]["total"]) == 0
    assert D(s["household_shared"]["total"]) == 0
    assert s["by_category"] == []


def test_household_shared_total_counts_full_price(client, household):
    spend(client, household, "a", "100.00")
    spend(client, household, "b", "50.00")
    spend(client, household, "a", "20.00", is_shared=False)
    for who in ("a", "b"):
        assert D(summary(client, household, who)["household_shared"]["total"]) == D("150.00")


def test_previous_month_comparison(client, household):
    spend(client, household, "a", "100.00", when="2026-09-10T12:00:00-03:00")  # A bears 60 in Sep
    spend(client, household, "a", "50.00", when="2026-10-10T12:00:00-03:00")   # A bears 30 in Oct
    s = summary(client, household, "a", "2026-10")
    assert D(s["me"]["total"]) == D("30.00")
    assert D(s["me"]["previous_total"]) == D("60.00")
    assert D(s["household_shared"]["previous_total"]) == D("100.00")


def test_january_compares_with_previous_december(client, household):
    spend(client, household, "a", "100.00", when="2026-12-15T12:00:00-03:00")
    s = summary(client, household, "a", "2027-01")
    assert s["previous_month"] == "2026-12"
    assert D(s["me"]["previous_total"]) == D("60.00")


def test_month_is_sao_paulo_calendar_month(client, household):
    # 23:30 on 31 Oct in São Paulo is 1 Nov in UTC; it belongs to October.
    spend(client, household, "a", "100.00", when="2026-10-31T23:30:00-03:00")
    assert D(summary(client, household, "a", "2026-10")["me"]["total"]) == D("60.00")
    assert D(summary(client, household, "a", "2026-11")["me"]["total"]) == 0


def test_breakdowns_are_ranked(client, household):
    rent = client.post("/categories/", headers=household["a"], json={
        "primary_category": "Housing", "sub_category": "Rent", "cost_type": "Fixed",
    }).json()["category_id"]
    spend(client, household, "a", "1000.00", category_id=rent)  # A bears 600, Fixed
    spend(client, household, "a", "100.00")                     # A bears 60, Food/Variable
    spend(client, household, "a", "40.00", is_shared=False)     # A bears 40, Food/Variable
    s = summary(client, household, "a")
    assert amounts(s["by_category"]) == [("Housing", D("600.00")), ("Food", D("100.00"))]
    assert amounts(s["by_cost_type"]) == [("Fixed", D("600.00")), ("Variable", D("100.00"))]
    # breakdowns add up to the total
    assert sum(a for _, a in amounts(s["by_category"])) == D(s["me"]["total"])


def test_defaults_to_current_sao_paulo_month(client, household):
    s = summary(client, household, month=None)
    assert s["month"] == datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m")


def test_invalid_month_is_a_422(client, household):
    for bad in ("2026-13", "2026-1", "october"):
        assert client.get("/summary/", headers=household["a"], params={"month": bad}).status_code == 422
