""""It's on me": a shared expense the payer treated, so nobody owes them for it."""
from decimal import Decimal

import database
from conftest import expenditure_payload
from etl.main import extract_allocations, extract_cashflow, extract_data

D = Decimal


def spend(client, h, who, price, **extra):
    resp = client.post("/expenditures/", headers=h[who], json=expenditure_payload(h, price=price, **extra))
    assert resp.status_code == 200, resp.text
    return resp.json()


def balances(client, h):
    report = client.get("/balances/", headers=h["a"]).json()
    return report, {m["user_id"]: (D(m["paid"]), D(m["borne"]), D(m["net"])) for m in report["members"]}


def test_a_treat_is_still_split_but_nobody_owes(client, household):
    spend(client, household, "a", "100.00", is_treat=True)
    report, by_user = balances(client, household)
    # 60/40: each counts as having paid their own share.
    assert by_user == {
        household["a_id"]: (D("60.00"), D("60.00"), D("0.00")),
        household["b_id"]: (D("40.00"), D("40.00"), D("0.00")),
    }
    assert report["transfers"] == []


def test_only_ordinary_shared_expenses_count_towards_who_owes(client, household):
    spend(client, household, "a", "100.00", is_treat=True)  # breakfast, on alice
    spend(client, household, "a", "50.00")                  # bob owes 20
    report, _ = balances(client, household)
    assert [(t["from_user_id"], D(t["amount"])) for t in report["transfers"]] == [(household["b_id"], D("20.00"))]


def test_a_treat_counts_in_both_shares_and_reads_back(client, household):
    spend(client, household, "a", "100.00", is_treat=True)
    # Bob still sees it as shared, with his 40% as his part.
    [seen] = client.get("/expenditures/", headers=household["b"]).json()
    assert seen["is_shared"] is True and seen["is_treat"] is True
    assert D(seen["my_share"]) == D("40.00")
    summary = client.get("/summary/", headers=household["b"], params={"month": "2026-10"}).json()
    assert D(summary["me"]["shared_share"]) == D("40.00")


def test_a_personal_expense_cant_be_a_treat(client, household):
    resp = client.post("/expenditures/", headers=household["a"], json=expenditure_payload(
        household, is_shared=False, is_treat=True))
    assert resp.status_code == 422


def test_drilldown_names_the_treat(client, household):
    spend(client, household, "a", "100.00", is_treat=True, transaction_timestamp="2026-10-08T12:00:00-03:00")
    spend(client, household, "a", "50.00", transaction_timestamp="2026-10-09T12:00:00-03:00")
    rows = client.get("/analytics/shared/expenses", headers=household["b"], params={"month": "2026-10"}).json()
    assert [r["paid_by"] for r in rows] == ["alice", "alice (treat)"]


def test_etl_flags_treats(client, household):
    spend(client, household, "a", "100.00", is_treat=True)
    spend(client, household, "a", "50.00")
    for df in (extract_data(database.engine), extract_allocations(database.engine), extract_cashflow(database.engine)):
        assert set(df["is_treat"]) == {True, False}
