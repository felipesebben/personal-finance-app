"""Joint accounts: expenses paid from a pot both people fund never make anyone owe."""
from decimal import Decimal

import pytest

import database
from conftest import expenditure_payload
from etl.main import extract_allocations, extract_cashflow, extract_data

D = Decimal


@pytest.fixture
def joint(client, household):
    resp = client.post("/payment_methods/", headers=household["a"], json={
        "method_name": "Debit", "institution": "Nubank Conjunta", "is_joint": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_joint"] is True
    return {**household, "joint_id": resp.json()["payment_method_id"]}


def spend(client, h, who, price, joint=False, **extra):
    if joint:
        extra["payment_method_id"] = h["joint_id"]
    resp = client.post("/expenditures/", headers=h[who], json=expenditure_payload(h, price=price, **extra))
    assert resp.status_code == 200, resp.text
    return resp.json()


def members(client, h):
    report = client.get("/balances/", headers=h["a"]).json()
    return report, {
        m["user_id"]: (D(m["paid"]), D(m["borne"]), D(m["net"])) for m in report["members"]
    }


def test_methods_are_personal_unless_marked(client, joint):
    listed = {m["method_name"]: m["is_joint"] for m in client.get("/payment_methods/", headers=joint["a"]).json()}
    assert listed == {"Pix": False, "Debit": True}


def test_joint_expense_leaves_nobody_owing(client, joint):
    spend(client, joint, "a", "500.00", joint=True)
    report, by_user = members(client, joint)
    # 60/40: each paid exactly what they bear.
    assert by_user == {
        joint["a_id"]: (D("300.00"), D("300.00"), D("0.00")),
        joint["b_id"]: (D("200.00"), D("200.00"), D("0.00")),
    }
    assert report["transfers"] == []


def test_only_personal_payments_count_towards_who_owes(client, joint):
    spend(client, joint, "a", "500.00", joint=True)
    spend(client, joint, "b", "100.00")  # B's own Pix: A owes B 60
    report, by_user = members(client, joint)
    assert by_user[joint["a_id"]][2] == D("-60.00")
    assert by_user[joint["b_id"]][2] == D("60.00")
    assert [(t["from_user_id"], D(t["amount"])) for t in report["transfers"]] == [(joint["a_id"], D("60.00"))]


def test_marking_a_method_joint_later_clears_what_it_paid(client, household):
    spend(client, household, "a", "100.00")  # on Pix: B owes A 40
    client.patch(f"/payment_methods/{household['payment_method_id']}", headers=household["a"], json={"is_joint": True})
    report, _ = members(client, household)
    assert report["transfers"] == []


def test_custom_split_on_a_joint_expense_still_nets_to_zero(client, joint):
    spend(client, joint, "a", "100.00", joint=True, shares=[
        {"user_id": joint["a_id"], "share_pct": "0.5"},
        {"user_id": joint["b_id"], "share_pct": "0.5"},
    ])
    _, by_user = members(client, joint)
    assert {uid: net for uid, (_, _, net) in by_user.items()} == {joint["a_id"]: D("0"), joint["b_id"]: D("0")}


def test_analytics_drilldown_says_joint_account(client, joint):
    spend(client, joint, "a", "500.00", joint=True, transaction_timestamp="2026-10-08T12:00:00-03:00")
    spend(client, joint, "a", "100.00", transaction_timestamp="2026-10-09T12:00:00-03:00")
    rows = client.get("/analytics/shared/expenses", headers=joint["b"], params={"month": "2026-10"}).json()
    assert [r["paid_by"] for r in rows] == ["alice", "Joint account"]


def test_etl_flags_what_the_joint_account_paid(client, joint):
    spend(client, joint, "a", "500.00", joint=True)
    spend(client, joint, "a", "100.00")
    for df in (extract_data(database.engine), extract_allocations(database.engine), extract_cashflow(database.engine)):
        flags = df.groupby("paid_from_joint").size().to_dict()
        assert set(flags) == {True, False}
