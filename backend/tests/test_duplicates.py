"""POST /expenditures/ refuses (409) an expense that looks already logged, unless told to save anyway."""
import pytest

from conftest import expenditure_payload

DAY = "2026-09-05T12:30:00-03:00"


def post(client, h, who="a", **extra):
    fields = {"price": "85.00", "transaction_timestamp": DAY, **extra}
    return client.post("/expenditures/", headers=h[who], json=expenditure_payload(h, **fields))


def test_the_same_expense_twice_is_a_409_naming_the_first(client, household):
    first = post(client, household)
    assert first.status_code == 200
    resp = post(client, household, transaction_timestamp="2026-09-05T19:02:00-03:00")  # same day, other time
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    [dup] = detail["duplicates"]
    assert (dup["logged_by"], dup["logged_by_me"], dup["price"]) == ("alice", True, "85.00")
    assert dup["category"] == "Food › Groceries" and dup["payment_method"] == "Pix"
    assert len(client.get("/expenditures/", headers=household["a"]).json()) == 1


def test_save_anyway(client, household):
    post(client, household)
    assert post(client, household, allow_duplicate=True).status_code == 200
    assert len(client.get("/expenditures/", headers=household["a"]).json()) == 2


@pytest.mark.parametrize("change", [
    {"price": "85.01"},
    {"transaction_timestamp": "2026-09-06T12:30:00-03:00"},
    {"nature": "Extraordinary"},
    {"is_shared": False},
    {"is_treat": True},
    {"total_installments": 2},
])
def test_any_other_difference_is_not_a_duplicate(client, household, change):
    post(client, household)
    assert post(client, household, **change).status_code == 200


def test_a_day_is_a_sao_paulo_day(client, household):
    post(client, household, transaction_timestamp="2026-09-05T23:30:00-03:00")  # already the 6th in UTC
    assert post(client, household, transaction_timestamp="2026-09-05T08:00:00-03:00").status_code == 409
    assert post(client, household, transaction_timestamp="2026-09-06T08:00:00-03:00").status_code == 200


def test_the_partners_shared_expense_is_flagged_even_with_another_card(client, household):
    card = client.post("/payment_methods/", headers=household["b"], json={
        "method_name": "Credit Card", "institution": "Itaú", "is_credit": True,
    }).json()["payment_method_id"]
    assert post(client, household, who="b", payment_method_id=card).status_code == 200  # bob logged dinner
    resp = post(client, household)                                                         # alice logs it too
    assert resp.status_code == 409
    [dup] = resp.json()["detail"]["duplicates"]
    assert (dup["logged_by"], dup["logged_by_me"]) == ("bob", False)


def test_a_personal_expense_doesnt_match_the_partners_shared_one(client, household):
    post(client, household, who="b")
    assert post(client, household, is_shared=False).status_code == 200


def test_the_partners_personal_spending_is_never_revealed(client, household):
    post(client, household, who="b", is_shared=False)  # bob's own: alice can't see it
    assert post(client, household).status_code == 200
