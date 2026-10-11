"""Categories and payment methods: create, edit, usage counts, duplicates."""
from conftest import expenditure_payload, signup_and_login


def by_id(rows, key, value):
    return next(r for r in rows if r[key] == value)


# --- usage counts --------------------------------------------------------

def test_lists_report_how_many_expenses_use_each_row(client, household):
    h = household["a"]
    spare = client.post("/categories/", headers=h, json={
        "primary_category": "Pets", "sub_category": "Vet", "cost_type": "Variable",
    }).json()["category_id"]
    for _ in range(2):
        assert client.post("/expenditures/", headers=h, json=expenditure_payload(household)).status_code == 200

    categories = client.get("/categories/", headers=h).json()
    assert by_id(categories, "category_id", household["category_id"])["expense_count"] == 2
    assert by_id(categories, "category_id", spare)["expense_count"] == 0

    methods = client.get("/payment_methods/", headers=h).json()
    assert by_id(methods, "payment_method_id", household["payment_method_id"])["expense_count"] == 2


# --- editing categories --------------------------------------------------

def test_patch_category_changes_only_the_fields_sent(client, household):
    h, cid = household["a"], household["category_id"]
    resp = client.patch(f"/categories/{cid}", headers=h, json={"sub_category": "Supermarket"})
    assert resp.status_code == 200, resp.text
    assert resp.json() | {"expense_count": 0} == {
        "category_id": cid, "primary_category": "Food", "sub_category": "Supermarket",
        "cost_type": "Variable", "expense_count": 0,
    }

    resp = client.patch(f"/categories/{cid}", headers=h, json={"cost_type": "Fixed"})
    assert resp.json()["cost_type"] == "Fixed"
    assert resp.json()["sub_category"] == "Supermarket"


def test_renaming_a_category_relabels_its_past_expenses(client, household):
    h = household["a"]
    client.post("/expenditures/", headers=h, json=expenditure_payload(household))
    client.patch(f"/categories/{household['category_id']}", headers=h, json={"primary_category": "Groceries & Food"})

    [expense] = client.get("/expenditures/", headers=h).json()
    assert expense["category"]["primary_category"] == "Groceries & Food"


def test_patch_category_rejects_bad_values(client, household):
    h, cid = household["a"], household["category_id"]
    assert client.patch(f"/categories/{cid}", headers=h, json={"cost_type": "Sometimes"}).status_code == 422
    assert client.patch(f"/categories/{cid}", headers=h, json={"sub_category": ""}).status_code == 422
    assert client.patch("/categories/999999", headers=h, json={"sub_category": "x"}).status_code == 404


def test_duplicate_category_is_a_409_on_create_and_on_rename(client, household):
    h = household["a"]
    resp = client.post("/categories/", headers=h, json={"primary_category": "Food", "sub_category": "Groceries"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Food › Groceries already exists."

    other = client.post("/categories/", headers=h, json={
        "primary_category": "Food", "sub_category": "Eating Out",
    }).json()["category_id"]
    resp = client.patch(f"/categories/{other}", headers=h, json={"sub_category": "Groceries"})
    assert resp.status_code == 409
    # and the failed rename left the row untouched
    assert by_id(client.get("/categories/", headers=h).json(), "category_id", other)["sub_category"] == "Eating Out"


# --- editing payment methods ---------------------------------------------

def test_patch_payment_method_sets_and_clears_institution(client, household):
    h, pid = household["a"], household["payment_method_id"]
    resp = client.patch(f"/payment_methods/{pid}", headers=h, json={"institution": "Nubank", "is_credit": True})
    assert resp.status_code == 200, resp.text
    assert (resp.json()["institution"], resp.json()["is_credit"]) == ("Nubank", True)

    resp = client.patch(f"/payment_methods/{pid}", headers=h, json={"institution": None})
    assert (resp.json()["method_name"], resp.json()["institution"], resp.json()["is_credit"]) == ("Pix", None, True)


def test_duplicate_payment_method_is_a_409(client, household):
    h = household["a"]
    client.post("/payment_methods/", headers=h, json={"method_name": "Pix", "institution": "Nubank"})
    resp = client.post("/payment_methods/", headers=h, json={"method_name": "Pix", "institution": "Nubank"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Pix · Nubank already exists."


def test_delete_of_a_category_in_use_is_still_a_400(client, household):
    h = household["a"]
    client.post("/expenditures/", headers=h, json=expenditure_payload(household))
    resp = client.delete(f"/categories/{household['category_id']}", headers=h)
    assert resp.status_code == 400
    assert "existing records" in resp.json()["detail"]


# --- the payer must be in the household to share --------------------------

def test_shared_expense_by_someone_outside_the_household_is_a_400(client, household):
    # carol has an account but no household share: splitting her expense by
    # the ratio would hand all of it to alice and bob.
    _, carol = signup_and_login(client, "carol")
    resp = client.post("/expenditures/", headers=carol, json=expenditure_payload(household))
    assert resp.status_code == 400
    assert "not in the household split" in resp.json()["detail"]
    assert client.get("/expenditures/", headers=carol).json() == []

    # A personal expense is still fine.
    resp = client.post("/expenditures/", headers=carol, json=expenditure_payload(household, is_shared=False))
    assert resp.status_code == 200
