"""Expenditure write path, allocation rows, and the ownership/visibility filter."""
from decimal import Decimal

from conftest import expenditure_payload, signup_and_login, splits_for

D = Decimal


def create(client, household, who="a", **kwargs):
    resp = client.post("/expenditures/", headers=household[who], json=expenditure_payload(household, **kwargs))
    assert resp.status_code == 200, resp.text
    # POST doesn't return the id, so take the newest one this user can see
    listed = client.get("/expenditures/", headers=household[who]).json()
    return max(e["expenditure_id"] for e in listed)


def visible_ids(client, headers):
    return {e["expenditure_id"] for e in client.get("/expenditures/", headers=headers).json()}


# --- allocation rows -----------------------------------------------------

def test_shared_expense_is_split_by_household_ratio(client, household):
    exp_id = create(client, household, price="100.01", is_shared=True)
    rows = splits_for(exp_id)
    assert [(r["user_id"], r["share_pct"], r["share_amount"], r["split_source"]) for r in rows] == [
        (household["a_id"], D("0.6000"), D("60.01"), "household_default"),
        (household["b_id"], D("0.4000"), D("40.00"), "household_default"),
    ]
    assert sum(r["share_amount"] for r in rows) == D("100.01")


def test_personal_expense_gets_one_row_at_100_percent(client, household):
    exp_id = create(client, household, price="55.55", is_shared=False)
    assert splits_for(exp_id) == [{
        "user_id": household["a_id"], "share_pct": D("1.0000"),
        "share_amount": D("55.55"), "split_source": "not_shared",
    }]


def test_shared_expense_without_household_ratio_is_a_400(client):
    # A fresh signup has no household_setting row, so there's no ratio to split by.
    _, headers = signup_and_login(client, "carol")
    category_id = client.post("/categories/", headers=headers, json={
        "primary_category": "Food", "sub_category": "Groceries",
    }).json()["category_id"]
    payment_method_id = client.post("/payment_methods/", headers=headers, json={
        "method_name": "Pix",
    }).json()["payment_method_id"]

    resp = client.post("/expenditures/", headers=headers, json={
        "transaction_timestamp": "2026-10-08T12:00:00-03:00", "price": "10.00",
        "category_id": category_id, "payment_method_id": payment_method_id, "is_shared": True,
    })
    assert resp.status_code == 400
    # and the expenditure itself was not half-written
    assert client.get("/expenditures/", headers=headers).json() == []


def test_user_id_in_body_is_ignored(client, household):
    exp_id = create(client, household, who="a", is_shared=False, user_id=household["b_id"])
    listed = client.get("/expenditures/", headers=household["a"]).json()
    assert next(e for e in listed if e["expenditure_id"] == exp_id)["user"]["user_id"] == household["a_id"]


def test_price_must_be_positive(client, household):
    resp = client.post("/expenditures/", headers=household["a"], json=expenditure_payload(household, price="0"))
    assert resp.status_code == 422


def test_current_installment_cannot_exceed_total(client, household):
    body = expenditure_payload(household, current_installment=4, total_installments=3)
    assert client.post("/expenditures/", headers=household["a"], json=body).status_code == 422


def test_installments_must_be_positive(client, household):
    body = expenditure_payload(household, current_installment=1, total_installments=0)
    assert client.post("/expenditures/", headers=household["a"], json=body).status_code == 422


# --- manual split override ------------------------------------------------

def shares(household, a_pct, b_pct):
    return [{"user_id": household["a_id"], "share_pct": a_pct}, {"user_id": household["b_id"], "share_pct": b_pct}]


def test_manual_shares_override_the_household_ratio(client, household):
    exp_id = create(client, household, price="100.01", shares=shares(household, "0.3", "0.7"))
    assert [(r["user_id"], r["share_pct"], r["share_amount"], r["split_source"]) for r in splits_for(exp_id)] == [
        (household["a_id"], D("0.3000"), D("30.00"), "manual"),
        (household["b_id"], D("0.7000"), D("70.01"), "manual"),
    ]


def test_expense_entirely_on_the_other_person(client, household):
    # "This one's on her": A pays, B bears all of it, so B owes A the full price.
    exp_id = create(client, household, who="a", price="80.00",
                    shares=[{"user_id": household["b_id"], "share_pct": "1"}])
    assert splits_for(exp_id) == [{
        "user_id": household["b_id"], "share_pct": D("1.0000"),
        "share_amount": D("80.00"), "split_source": "manual",
    }]
    assert exp_id in visible_ids(client, household["b"])
    report = client.get("/balances/", headers=household["a"]).json()
    assert [(t["from_user_id"], t["to_user_id"], t["amount"]) for t in report["transfers"]] == [
        (household["b_id"], household["a_id"], "80.00"),
    ]


def test_shares_must_sum_to_one(client, household):
    resp = client.post("/expenditures/", headers=household["a"],
                       json=expenditure_payload(household, shares=shares(household, "0.5", "0.4")))
    assert resp.status_code == 422


def test_shares_must_not_repeat_a_person(client, household):
    body = expenditure_payload(household, shares=[
        {"user_id": household["a_id"], "share_pct": "0.5"}, {"user_id": household["a_id"], "share_pct": "0.5"},
    ])
    assert client.post("/expenditures/", headers=household["a"], json=body).status_code == 422


def test_shares_on_a_personal_expense_is_a_422(client, household):
    body = expenditure_payload(household, is_shared=False, shares=shares(household, "0.5", "0.5"))
    assert client.post("/expenditures/", headers=household["a"], json=body).status_code == 422


def test_shares_naming_an_outsider_is_a_400_and_writes_nothing(client, household):
    outsider_id, _ = signup_and_login(client, "mallory")
    body = expenditure_payload(household, shares=[
        {"user_id": household["a_id"], "share_pct": "0.5"}, {"user_id": outsider_id, "share_pct": "0.5"},
    ])
    resp = client.post("/expenditures/", headers=household["a"], json=body)
    assert resp.status_code == 400
    assert "not in the household" in resp.json()["detail"]
    assert client.get("/expenditures/", headers=household["a"]).json() == []


# --- delete --------------------------------------------------------------

def test_delete_cascades_to_allocation_rows(client, household):
    exp_id = create(client, household, is_shared=True)
    assert len(splits_for(exp_id)) == 2
    assert client.delete(f"/expenditures/{exp_id}", headers=household["a"]).status_code == 200
    assert splits_for(exp_id) == []


# --- visibility ----------------------------------------------------------

def test_personal_expense_is_private_to_its_owner(client, household):
    exp_id = create(client, household, who="a", is_shared=False)
    assert exp_id in visible_ids(client, household["a"])
    assert exp_id not in visible_ids(client, household["b"])


def test_shared_expense_is_visible_to_both(client, household):
    exp_id = create(client, household, who="a", is_shared=True)
    assert exp_id in visible_ids(client, household["a"])
    assert exp_id in visible_ids(client, household["b"])


def test_cannot_delete_someone_elses_personal_expense(client, household):
    exp_id = create(client, household, who="a", is_shared=False)
    assert client.delete(f"/expenditures/{exp_id}", headers=household["b"]).status_code == 404
    assert exp_id in visible_ids(client, household["a"])


def test_can_delete_a_shared_expense_someone_else_paid(client, household):
    exp_id = create(client, household, who="a", is_shared=True)
    assert client.delete(f"/expenditures/{exp_id}", headers=household["b"]).status_code == 200


# --- "shared" is derived from allocation rows, not the is_shared column ---

def listed(client, headers, exp_id):
    return next(e for e in client.get("/expenditures/", headers=headers).json() if e["expenditure_id"] == exp_id)


def test_outsider_cannot_see_a_shared_expense(client, household):
    # Before: any logged-in account saw every is_shared expense.
    exp_id = create(client, household, who="a", is_shared=True)
    _, carol = signup_and_login(client, "carol")
    assert exp_id not in visible_ids(client, carol)


def test_outsider_cannot_delete_a_shared_expense(client, household):
    exp_id = create(client, household, who="a", is_shared=True)
    _, carol = signup_and_login(client, "carol")
    assert client.delete(f"/expenditures/{exp_id}", headers=carol).status_code == 404
    assert exp_id in visible_ids(client, household["a"])


def test_is_shared_in_response_reflects_split_rows(client, household):
    shared = create(client, household, is_shared=True)
    personal = create(client, household, is_shared=False)
    assert listed(client, household["a"], shared)["is_shared"] is True
    assert listed(client, household["a"], personal)["is_shared"] is False


def test_shared_request_with_payer_only_household_is_not_shared(client, household):
    # If the household ratio only contains the payer, "split by the ratio"
    # gives them 100% — nobody else bears anything, so it isn't shared,
    # whatever the request said, and the other person can't see it.
    client.put("/household_settings/", headers=household["a"], json={"settings": [
        {"user_id": household["a_id"], "share_pct": "1"},
    ]})
    exp_id = create(client, household, who="a", is_shared=True)
    assert listed(client, household["a"], exp_id)["is_shared"] is False
    assert exp_id not in visible_ids(client, household["b"])


def test_share_holder_who_did_not_pay_can_see_and_delete(client, household):
    exp_id = create(client, household, who="a", is_shared=True)
    assert listed(client, household["b"], exp_id)["user"]["user_id"] == household["a_id"]
    assert client.delete(f"/expenditures/{exp_id}", headers=household["b"]).status_code == 200
