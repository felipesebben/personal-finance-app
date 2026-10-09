"""Settlements: recording paybacks, and how they feed into /balances/."""
from decimal import Decimal

from conftest import expenditure_payload, signup_and_login

D = Decimal


def spend(client, household, who, price, when="2026-10-08T12:00:00-03:00"):
    resp = client.post("/expenditures/", headers=household[who], json=expenditure_payload(
        household, price=price, transaction_timestamp=when,
    ))
    assert resp.status_code == 200, resp.text


def pay(client, household, who, frm, to, amount, month="2026-10", when="2026-11-03T09:00:00-03:00", note=None):
    body = {
        "settled_at": when, "from_user_id": household[f"{frm}_id"],
        "to_user_id": household[f"{to}_id"], "amount": amount, "note": note,
    }
    if month:
        body["month"] = month
    return client.post("/settlements/", headers=household[who], json=body)


def nets(client, household, month=None):
    params = {"month": month} if month else {}
    report = client.get("/balances/", headers=household["a"], params=params).json()
    return {m["user_id"]: D(m["net"]) for m in report["members"]}, report["transfers"]


# --- effect on balances -----------------------------------------------------

def test_full_payback_squares_the_month(client, household):
    spend(client, household, "a", "100.00")          # B owes A 40
    assert pay(client, household, "b", "b", "a", "40.00").status_code == 200
    n, transfers = nets(client, household, "2026-10")
    assert n == {household["a_id"]: 0, household["b_id"]: 0}
    assert transfers == []


def test_partial_payback_leaves_the_rest(client, household):
    spend(client, household, "a", "100.00")          # B owes A 40
    pay(client, household, "b", "b", "a", "15.00")
    n, transfers = nets(client, household, "2026-10")
    assert n == {household["a_id"]: D("25.00"), household["b_id"]: D("-25.00")}
    assert D(transfers[0]["amount"]) == D("25.00")


def test_overpayment_flips_the_direction(client, household):
    spend(client, household, "a", "100.00")          # B owes A 40
    pay(client, household, "b", "b", "a", "50.00")
    _, transfers = nets(client, household, "2026-10")
    assert [(t["from_user_id"], t["to_user_id"], D(t["amount"])) for t in transfers] == [
        (household["a_id"], household["b_id"], D("10.00")),
    ]


def test_settlement_counts_against_its_month_not_its_payment_date(client, household):
    # October's balance paid on 3 November squares October, and leaves November alone.
    spend(client, household, "a", "100.00", when="2026-10-08T12:00:00-03:00")
    pay(client, household, "b", "b", "a", "40.00", month="2026-10", when="2026-11-03T09:00:00-03:00")
    assert nets(client, household, "2026-10")[1] == []
    assert nets(client, household, "2026-11")[0] == {household["a_id"]: 0, household["b_id"]: 0}


def test_settlement_without_month_only_counts_all_time(client, household):
    spend(client, household, "a", "100.00")
    pay(client, household, "b", "b", "a", "40.00", month=None)
    assert nets(client, household, "2026-10")[0][household["a_id"]] == D("40.00")
    assert nets(client, household)[1] == []


def test_all_time_includes_every_settlement(client, household):
    spend(client, household, "a", "100.00", when="2026-09-10T12:00:00-03:00")  # B owes 40
    spend(client, household, "a", "200.00", when="2026-10-10T12:00:00-03:00")  # B owes 80
    pay(client, household, "b", "b", "a", "40.00", month="2026-09")
    pay(client, household, "b", "b", "a", "30.00", month="2026-10")
    n, _ = nets(client, household)
    assert n[household["a_id"]] == D("50.00")
    assert sum(n.values()) == 0


def test_balance_report_shows_settled_amounts(client, household):
    spend(client, household, "a", "100.00")
    pay(client, household, "b", "b", "a", "40.00")
    members = {m["user_id"]: m for m in client.get(
        "/balances/", headers=household["a"], params={"month": "2026-10"}).json()["members"]}
    assert D(members[household["b_id"]]["settled_out"]) == D("40.00")
    assert D(members[household["a_id"]]["settled_in"]) == D("40.00")


# --- create / list / delete ---------------------------------------------------

def test_list_by_month_newest_first(client, household):
    pay(client, household, "b", "b", "a", "10.00", month="2026-10", when="2026-11-01T09:00:00-03:00", note="first")
    pay(client, household, "b", "b", "a", "20.00", month="2026-10", when="2026-11-05T09:00:00-03:00", note="second")
    pay(client, household, "b", "b", "a", "30.00", month="2026-09")
    listed = client.get("/settlements/", headers=household["a"], params={"month": "2026-10"}).json()
    assert [s["note"] for s in listed] == ["second", "first"]
    assert listed[0]["from_name"] == "bob" and listed[0]["to_name"] == "alice"
    assert listed[0]["month"] == "2026-10"
    assert len(client.get("/settlements/", headers=household["a"]).json()) == 3


def test_either_party_can_record(client, household):
    assert pay(client, household, "a", "b", "a", "10.00").status_code == 200  # payee records it
    assert pay(client, household, "b", "b", "a", "10.00").status_code == 200  # payer records it


def test_outsider_cannot_record_a_payment_between_others(client, household):
    _, carol = signup_and_login(client, "carol")
    resp = client.post("/settlements/", headers=carol, json={
        "settled_at": "2026-11-03T09:00:00-03:00", "from_user_id": household["b_id"],
        "to_user_id": household["a_id"], "amount": "10.00",
    })
    assert resp.status_code == 403


def test_validation(client, household):
    assert pay(client, household, "a", "a", "a", "10.00").status_code == 422   # same person
    assert pay(client, household, "a", "b", "a", "0").status_code == 422       # not positive
    assert pay(client, household, "a", "b", "a", "10.00", month="2026-13").status_code == 422
    resp = client.post("/settlements/", headers=household["a"], json={
        "settled_at": "2026-11-03T09:00:00-03:00", "from_user_id": 9999,
        "to_user_id": household["a_id"], "amount": "10.00",
    })
    assert resp.status_code == 400


def test_delete_restores_the_balance(client, household):
    spend(client, household, "a", "100.00")
    sid = pay(client, household, "b", "b", "a", "40.00").json()["settlement_id"]
    assert client.delete(f"/settlements/{sid}", headers=household["a"]).status_code == 200
    assert nets(client, household, "2026-10")[0][household["b_id"]] == D("-40.00")


def test_outsider_cannot_delete(client, household):
    sid = pay(client, household, "b", "b", "a", "40.00").json()["settlement_id"]
    _, carol = signup_and_login(client, "carol")
    assert client.delete(f"/settlements/{sid}", headers=carol).status_code == 404
