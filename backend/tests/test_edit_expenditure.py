"""PATCH /expenditures/{id}: fix a logged expense, re-split it, and leave a trace of who changed it."""
from decimal import Decimal

import pytest

from conftest import expenditure_payload, splits_for


def logged(client, h, who="a", **extra):
    resp = client.post("/expenditures/", headers=h[who], json=expenditure_payload(h, **extra))
    assert resp.status_code == 200, resp.text
    # POST answers with what was sent, not the id: the newest one is it.
    return max(e["expenditure_id"] for e in client.get("/expenditures/", headers=h[who]).json())


def patch(client, h, expenditure_id, who="a", **changes):
    return client.patch(f"/expenditures/{expenditure_id}", headers=h[who], json=changes)


def shares(expenditure_id):
    return [(r["user_id"], r["share_pct"], r["share_amount"], r["split_source"]) for r in splits_for(expenditure_id)]


def test_a_new_price_is_split_by_the_ratio_it_was_logged_with(client, household):
    h = household
    eid = logged(client, h)
    # The household ratio changes after it was logged...
    client.put("/household_settings/", headers=h["a"], json={"settings": [
        {"user_id": h["a_id"], "share_pct": "0.5"}, {"user_id": h["b_id"], "share_pct": "0.5"}]})
    resp = patch(client, h, eid, price="250.00")
    assert resp.status_code == 200, resp.text
    # ...but the edit keeps the 60/40 snapshot.
    assert shares(eid) == [(h["a_id"], Decimal("0.6000"), Decimal("150.00"), "household_default"),
                           (h["b_id"], Decimal("0.4000"), Decimal("100.00"), "household_default")]
    body = resp.json()
    assert body["price"] == "250.00" and body["my_share"] == "150.00"


def test_an_edit_leaves_a_trace_of_who_and_when(client, household):
    h = household
    eid = logged(client, h)
    [before] = client.get("/expenditures/", headers=h["a"]).json()
    assert before["updated_at"] is None and before["updated_by"] is None
    resp = patch(client, h, eid, who="b", nature="Extraordinary")  # bob fixes alice's expense
    assert resp.status_code == 200, resp.text
    [after] = client.get("/expenditures/", headers=h["a"]).json()
    assert after["nature"] == "Extraordinary"
    assert after["updated_by"]["full_name"] == "bob" and after["updated_at"] is not None
    assert after["user"]["full_name"] == "alice"  # still alice's: the payer never changes


def test_an_edit_that_changes_nothing_leaves_no_trace(client, household):
    h = household
    eid = logged(client, h)
    resp = patch(client, h, eid, price="100.00", nature="Normal", is_shared=True,
                 transaction_timestamp="2026-10-08T15:00:00Z")  # the same moment, in UTC
    assert resp.status_code == 200
    assert resp.json()["updated_at"] is None


def test_made_personal_then_shared_again_by_todays_ratio(client, household):
    h = household
    eid = logged(client, h)
    assert patch(client, h, eid, is_shared=False).status_code == 200
    assert shares(eid) == [(h["a_id"], Decimal("1.0000"), Decimal("100.00"), "not_shared")]
    assert client.get("/expenditures/", headers=h["b"]).json() == []  # bob no longer sees it
    client.put("/household_settings/", headers=h["a"], json={"settings": [
        {"user_id": h["a_id"], "share_pct": "0.7"}, {"user_id": h["b_id"], "share_pct": "0.3"}]})
    assert patch(client, h, eid, is_shared=True).status_code == 200
    assert [s[1] for s in shares(eid)] == [Decimal("0.7000"), Decimal("0.3000")]


def test_a_manual_split_and_back_to_the_household_ratio(client, household):
    h = household
    eid = logged(client, h)
    resp = patch(client, h, eid, shares=[{"user_id": h["a_id"], "share_pct": "0.2"},
                                         {"user_id": h["b_id"], "share_pct": "0.8"}])
    assert resp.status_code == 200, resp.text
    assert [(s[2], s[3]) for s in shares(eid)] == [(Decimal("20.00"), "manual"), (Decimal("80.00"), "manual")]
    assert [s["split_source"] for s in resp.json()["splits"]] == ["manual", "manual"]
    assert patch(client, h, eid, reset_split=True).status_code == 200
    assert [(s[2], s[3]) for s in shares(eid)] == [(Decimal("60.00"), "household_default"),
                                                   (Decimal("40.00"), "household_default")]


def test_the_partner_cant_edit_my_personal_expense(client, household):
    h = household
    eid = logged(client, h, is_shared=False)
    assert patch(client, h, eid, who="b", price="1.00").status_code == 404
    assert patch(client, h, 999_999, price="1.00").status_code == 404


@pytest.mark.parametrize("changes, status", [
    ({"current_installment": 3}, 422),            # 3 of 1
    ({"is_shared": False, "is_treat": True}, 422),
    ({"price": None}, 422),
    ({"price": "0"}, 422),
    ({"category_id": 999_999}, 400),
    ({"payment_method_id": 999_999}, 400),
    ({"pet_id": 1}, 400),                         # not a pet category
    ({"shares": [{"user_id": 1, "share_pct": "0.5"}]}, 422),  # doesn't sum to 1
])
def test_the_rules_of_a_new_expense_apply(client, household, changes, status):
    h = household
    eid = logged(client, h)
    resp = patch(client, h, eid, **changes)
    assert resp.status_code == status, resp.text
    assert shares(eid)[0][2] == Decimal("60.00")  # untouched


def test_a_treat_turned_personal_must_drop_the_treat(client, household):
    h = household
    eid = logged(client, h, is_treat=True)
    assert patch(client, h, eid, is_shared=False).status_code == 422
    assert patch(client, h, eid, is_shared=False, is_treat=False).status_code == 200


def test_moving_out_of_a_pet_category_drops_the_pet(client, household):
    h = household
    thor = client.post("/pets/", headers=h["a"], json={"name": "Thor"}).json()["pet_id"]
    vet = client.post("/categories/", headers=h["a"], json={
        "primary_category": "Pets", "sub_category": "Vet", "for_pets": True}).json()["category_id"]
    eid = logged(client, h, category_id=vet, pet_id=thor)
    resp = patch(client, h, eid, category_id=h["category_id"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["pet"] is None


def test_balances_follow_the_edit(client, household):
    h = household
    eid = logged(client, h)  # alice paid 100, bob bears 40
    patch(client, h, eid, price="200.00")
    report = client.get("/balances/?month=2026-10", headers=h["a"]).json()
    [transfer] = report["transfers"]
    assert (transfer["from_user_id"], transfer["amount"]) == (h["b_id"], "80.00")
