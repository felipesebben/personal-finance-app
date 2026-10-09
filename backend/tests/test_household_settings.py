"""PUT /household_settings/ validation."""


def test_shares_must_sum_to_one(client, household):
    resp = client.put("/household_settings/", headers=household["a"], json={"settings": [
        {"user_id": household["a_id"], "share_pct": "0.6"},
        {"user_id": household["b_id"], "share_pct": "0.6"},
    ]})
    assert resp.status_code == 422


def test_unknown_user_is_rejected(client, household):
    resp = client.put("/household_settings/", headers=household["a"], json={"settings": [
        {"user_id": household["a_id"], "share_pct": "0.5"},
        {"user_id": 9999, "share_pct": "0.5"},
    ]})
    assert resp.status_code == 400


def test_put_replaces_the_whole_set(client, household):
    resp = client.put("/household_settings/", headers=household["a"], json={"settings": [
        {"user_id": household["a_id"], "share_pct": "1"},
    ]})
    assert resp.status_code == 200
    got = client.get("/household_settings/", headers=household["a"]).json()
    assert [(s["user_id"], s["share_pct"]) for s in got] == [(household["a_id"], "1.0000")]
