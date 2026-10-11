"""Pets: the dimension, tagging a pet-category expense, and the ETL's pet column."""
import pytest

import database
from conftest import expenditure_payload
from etl.main import extract_allocations, extract_cashflow, extract_data


@pytest.fixture
def pets(client, household):
    h = household["a"]
    thor = client.post("/pets/", headers=h, json={"name": "Thor"}).json()["pet_id"]
    luna = client.post("/pets/", headers=h, json={"name": " Luna "}).json()["pet_id"]
    vet = client.post("/categories/", headers=h, json={
        "primary_category": "Pets", "sub_category": "Vet", "for_pets": True,
    }).json()["category_id"]
    return {**household, "thor": thor, "luna": luna, "vet": vet}


def post(client, pets, **extra):
    return client.post("/expenditures/", headers=pets["a"], json=expenditure_payload(pets, **extra))


def test_pets_are_listed_trimmed_with_usage(client, pets):
    post(client, pets, category_id=pets["vet"], pet_id=pets["thor"])
    listed = {p["name"]: p["expense_count"] for p in client.get("/pets/", headers=pets["a"]).json()}
    assert listed == {"Thor": 1, "Luna": 0}


def test_duplicate_pet_is_a_409(client, pets):
    resp = client.post("/pets/", headers=pets["a"], json={"name": "Thor"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Thor already exists."


def test_rename_and_delete_a_pet(client, pets):
    h = pets["a"]
    assert client.patch(f"/pets/{pets['luna']}", headers=h, json={"name": "Lua"}).json()["name"] == "Lua"
    assert client.delete(f"/pets/{pets['luna']}", headers=h).status_code == 200
    assert [p["name"] for p in client.get("/pets/", headers=h).json()] == ["Thor"]


def test_a_pet_in_use_cant_be_deleted(client, pets):
    post(client, pets, category_id=pets["vet"], pet_id=pets["thor"])
    resp = client.delete(f"/pets/{pets['thor']}", headers=pets["a"])
    assert resp.status_code == 400


def test_category_reports_for_pets(client, pets):
    cats = {c["sub_category"]: c["for_pets"] for c in client.get("/categories/", headers=pets["a"]).json()}
    assert cats == {"Groceries": False, "Vet": True}
    client.patch(f"/categories/{pets['category_id']}", headers=pets["a"], json={"for_pets": True})
    assert all(c["for_pets"] for c in client.get("/categories/", headers=pets["a"]).json())


def test_expense_reads_back_with_its_pet_or_none_for_both(client, pets):
    assert post(client, pets, category_id=pets["vet"], pet_id=pets["thor"]).status_code == 200
    assert post(client, pets, category_id=pets["vet"]).status_code == 200  # both

    listed = sorted(client.get("/expenditures/", headers=pets["a"]).json(), key=lambda e: e["expenditure_id"])
    assert listed[0]["pet"] == {"pet_id": pets["thor"], "name": "Thor", "expense_count": 0}
    assert listed[1]["pet"] is None


def test_pet_on_a_non_pet_category_is_a_400(client, pets):
    resp = post(client, pets, pet_id=pets["thor"])  # Groceries
    assert resp.status_code == 400
    assert resp.json()["detail"] == "A pet can only be given for a pet category."


def test_unknown_pet_is_a_400(client, pets):
    resp = post(client, pets, category_id=pets["vet"], pet_id=999999)
    assert resp.status_code == 400


def test_etl_labels_the_pet_both_or_nothing(client, pets):
    post(client, pets, category_id=pets["vet"], pet_id=pets["thor"], price="300.00")
    post(client, pets, category_id=pets["vet"], price="80.00")      # both dogs
    post(client, pets, price="50.00")                                # groceries

    by_price = extract_data(database.engine).set_index("price")["pet"]
    assert by_price[300.00] == "Thor"
    assert by_price[80.00] == "Both"
    assert by_price[50.00] is None

    # Every grain carries it, so cost per pet can be summed per person or per billing month.
    assert set(extract_allocations(database.engine)["pet"].dropna()) == {"Thor", "Both"}
    assert set(extract_cashflow(database.engine)["pet"].dropna()) == {"Thor", "Both"}
