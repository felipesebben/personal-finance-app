"""GET /balances/ — net position over shared expenses, and who owes whom."""
from decimal import Decimal

from conftest import expenditure_payload

D = Decimal


def spend(client, household, who, price, is_shared=True, when="2026-10-08T12:00:00-03:00"):
    resp = client.post("/expenditures/", headers=household[who], json=expenditure_payload(
        household, price=price, is_shared=is_shared, transaction_timestamp=when,
    ))
    assert resp.status_code == 200, resp.text


def balances(client, household, month=None):
    params = {"month": month} if month else {}
    resp = client.get("/balances/", headers=household["a"], params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def by_user(report):
    return {m["user_id"]: (D(m["paid"]), D(m["borne"]), D(m["net"])) for m in report["members"]}


def test_no_expenses_means_everyone_is_even(client, household):
    report = balances(client, household)
    assert by_user(report) == {
        household["a_id"]: (D("0"), D("0"), D("0")),
        household["b_id"]: (D("0"), D("0"), D("0")),
    }
    assert report["transfers"] == []


def test_one_shared_expense_paid_by_a(client, household):
    # 60/40 household: A pays 100, bears 60, so B owes A 40.
    spend(client, household, "a", "100.00")
    report = balances(client, household)
    assert by_user(report) == {
        household["a_id"]: (D("100.00"), D("60.00"), D("40.00")),
        household["b_id"]: (D("0"), D("40.00"), D("-40.00")),
    }
    assert [(t["from_user_id"], t["to_user_id"], D(t["amount"])) for t in report["transfers"]] == [
        (household["b_id"], household["a_id"], D("40.00")),
    ]
    assert report["transfers"][0]["from_name"] == "bob"
    assert report["transfers"][0]["to_name"] == "alice"


def test_payments_by_both_offset_each_other(client, household):
    spend(client, household, "a", "100.00")  # B owes A 40
    spend(client, household, "b", "50.00")   # A owes B 30
    report = balances(client, household)
    nets = {uid: net for uid, (_, _, net) in by_user(report).items()}
    assert nets == {household["a_id"]: D("10.00"), household["b_id"]: D("-10.00")}
    assert sum(nets.values()) == 0


def test_personal_expenses_are_left_out(client, household):
    spend(client, household, "a", "100.00")
    spend(client, household, "b", "999.99", is_shared=False)
    paid = {uid: p for uid, (p, _, _) in by_user(balances(client, household)).items()}
    # B's personal spending doesn't show up in the shared view at all
    assert paid[household["b_id"]] == D("0")


def test_month_filter(client, household):
    spend(client, household, "a", "100.00", when="2026-09-15T12:00:00-03:00")
    spend(client, household, "a", "200.00", when="2026-10-15T12:00:00-03:00")
    assert by_user(balances(client, household, "2026-09"))[household["a_id"]][0] == D("100.00")
    assert by_user(balances(client, household, "2026-10"))[household["a_id"]][0] == D("200.00")
    assert by_user(balances(client, household))[household["a_id"]][0] == D("300.00")
    assert by_user(balances(client, household, "2026-11"))[household["a_id"]][0] == D("0")


def test_month_is_sao_paulo_calendar_month(client, household):
    # 23:30 on 31 Oct in São Paulo is already 1 Nov in UTC — it belongs to October.
    spend(client, household, "a", "100.00", when="2026-10-31T23:30:00-03:00")
    assert by_user(balances(client, household, "2026-10"))[household["a_id"]][0] == D("100.00")
    assert by_user(balances(client, household, "2026-11"))[household["a_id"]][0] == D("0")


def test_snapshot_survives_a_ratio_change(client, household):
    # Allocations are snapshotted at write time: changing the ratio later
    # must not rewrite who owed what on an old expense.
    spend(client, household, "a", "100.00")
    client.put("/household_settings/", headers=household["a"], json={"settings": [
        {"user_id": household["a_id"], "share_pct": "0.5"},
        {"user_id": household["b_id"], "share_pct": "0.5"},
    ]})
    assert by_user(balances(client, household))[household["a_id"]][2] == D("40.00")


def test_invalid_month_is_a_422(client, household):
    for bad in ("2026-13", "2026-1", "october", "2026-10-01"):
        resp = client.get("/balances/", headers=household["a"], params={"month": bad})
        assert resp.status_code == 422, bad
