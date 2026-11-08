"""/category_targets/: a monthly target per primary category or sub-category, replaced as a whole set."""


def put(client, h, targets, who="a"):
    return client.put("/category_targets/", headers=h[who], json={"targets": targets})


def test_no_targets_until_some_are_set(client, household):
    assert client.get("/category_targets/", headers=household["a"]).json() == []


def test_put_replaces_the_whole_set(client, household):
    h = household
    client.post("/categories/", headers=h["a"], json={"primary_category": "Pets", "sub_category": "Vet"})
    resp = put(client, h, [{"primary_category": "Food", "amount": "3000.00"},
                           {"primary_category": "Pets", "amount": "800"}])
    assert resp.status_code == 200, resp.text
    assert resp.json() == [{"primary_category": "Food", "sub_category": None, "amount": "3000.00"},
                           {"primary_category": "Pets", "sub_category": None, "amount": "800.00"}]
    # Bob sees and changes the same household targets; leaving Pets out removes it.
    assert put(client, h, [{"primary_category": "Food", "amount": "2500.50"}], who="b").status_code == 200
    assert client.get("/category_targets/", headers=h["a"]).json() == [
        {"primary_category": "Food", "sub_category": None, "amount": "2500.50"}]
    assert put(client, h, []).json() == []


def test_targets_must_name_real_categories_once_and_be_positive(client, household):
    h = household
    assert put(client, h, [{"primary_category": "Yachts", "amount": "10"}]).status_code == 400
    assert put(client, h, [{"primary_category": "Food", "amount": "10"},
                           {"primary_category": "Food", "amount": "20"}]).status_code == 400
    assert put(client, h, [{"primary_category": "Food", "amount": "0"}]).status_code == 422
    assert put(client, h, [{"primary_category": "Food", "amount": "1.234"}]).status_code == 422
    assert client.get("/category_targets/", headers=h["a"]).json() == []  # nothing half-written


def test_a_sub_category_has_its_own_target_beside_its_category(client, household):
    h = household
    client.post("/categories/", headers=h["a"], json={"primary_category": "Pets", "sub_category": "Grooming"})
    resp = put(client, h, [{"primary_category": "Pets", "amount": "1500"},
                           {"primary_category": "Pets", "sub_category": "Grooming", "amount": "200"},
                           {"primary_category": "Food", "sub_category": "", "amount": "100"}])  # '' = whole
    assert resp.status_code == 200, resp.text
    assert resp.json() == [{"primary_category": "Food", "sub_category": None, "amount": "100.00"},
                           {"primary_category": "Pets", "sub_category": None, "amount": "1500.00"},
                           {"primary_category": "Pets", "sub_category": "Grooming", "amount": "200.00"}]


def test_a_sub_category_target_must_name_a_real_sub_category_once(client, household):
    h = household
    client.post("/categories/", headers=h["a"], json={"primary_category": "Pets", "sub_category": "Grooming"})
    resp = put(client, h, [{"primary_category": "Pets", "sub_category": "Yachts", "amount": "10"}])
    assert resp.status_code == 400 and "Pets › Yachts" in resp.json()["detail"]
    # Grooming lives under Pets, not Food.
    assert put(client, h, [{"primary_category": "Food", "sub_category": "Grooming", "amount": "10"}]).status_code == 400
    assert put(client, h, [{"primary_category": "Pets", "sub_category": "Grooming", "amount": "10"},
                           {"primary_category": "Pets", "sub_category": "Grooming", "amount": "20"}]).status_code == 400
    assert client.get("/category_targets/", headers=h["a"]).json() == []
