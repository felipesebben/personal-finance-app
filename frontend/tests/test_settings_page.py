"""The Settings page renders from mocked API responses, and saves the household split."""
from unittest.mock import MagicMock, patch

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

PAGE = "pages/5_Settings.py"
ME = "me@example.com"

USERS = [
    {"user_id": 12, "full_name": "Me", "email": ME},
    {"user_id": 13, "full_name": "Her", "email": "her@example.com"},
]
CATEGORIES = [
    {"category_id": 1, "primary_category": "Food", "sub_category": "Groceries", "cost_type": "Variable", "expense_count": 2},
]
PAYMENT_METHODS = [
    {"payment_method_id": 5, "method_name": "Pix", "institution": "Nubank", "is_credit": False, "expense_count": 0},
]


def response(payload, status_code=200):
    r = MagicMock(status_code=status_code)
    r.json.return_value = payload
    return r


def fake_get(users, household):
    def get(url, *args, **kwargs):
        for endpoint, payload in [
            ("/users/", users), ("/household_settings/", household),
            ("/categories/", CATEGORIES), ("/payment_methods/", PAYMENT_METHODS),
        ]:
            if url.endswith(endpoint):
                return response(payload)
        return response([])
    return get


@pytest.fixture(autouse=True)
def fresh_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def run(users=USERS, household=()):
    at = AppTest.from_file("Home.py", default_timeout=30)
    at.session_state["access_token"] = "x"
    at.session_state["user_email"] = ME
    # Home's briefing calls the API too, so mock it there as well: an
    # unmocked call could reach a real backend, whose 401 logs the test out.
    with patch("requests.get", side_effect=fake_get(users, list(household))):
        at.run()
        at.switch_page(PAGE)
        at.run()
    return at


def test_renders_every_section_with_no_pending_changes():
    at = run()
    assert not at.exception
    assert [s.value for s in at.subheader] == ["Household", "Categories", "Payment methods", "Pets", "Publish to Tableau"]
    # No edits yet, so no Save changes / Discard buttons for the tables.
    assert not [b for b in at.button if b.label in ("Save changes", "Discard")]
    # The old add-a-person form is gone: partners sign up themselves.
    assert not [t for t in at.text_input if t.label == "Password"]


def test_household_lists_everyone_with_me_first_and_zero_for_newcomers():
    at = run(household=[{"user_id": 12, "share_pct": "1.0000", "user": USERS[0]}])
    assert [n.value for n in at.number_input] == [100.0, 0.0]
    save = next(b for b in at.button if b.label == "Save split")
    assert save.disabled  # nothing changed yet


def test_saving_a_new_split_puts_both_shares():
    at = run(household=[{"user_id": 12, "share_pct": "1.0000", "user": USERS[0]}])
    with patch("requests.get", side_effect=fake_get(USERS, [])), \
            patch("requests.request", return_value=response({})) as req:
        at.number_input(key="share_12_0").set_value(60.0).run()
        at.number_input(key="share_13_0").set_value(40.0).run()
        assert not at.exception
        next(b for b in at.button if b.label == "Save split").click().run()

    method, url = req.call_args.args
    assert (method, url.endswith("/household_settings/")) == ("PUT", True)
    assert req.call_args.kwargs["json"] == {"settings": [
        {"user_id": 12, "share_pct": 0.6}, {"user_id": 13, "share_pct": 0.4},
    ]}
    assert [t.value for t in at.toast] == ["Household split saved."]


def test_shares_that_dont_add_up_disable_save_and_say_why():
    at = run()
    with patch("requests.get", side_effect=fake_get(USERS, [])):
        at.number_input(key="share_12_0").set_value(70.0).run()
    assert "Shares must add up to 100% (now 70%)." in " ".join(c.value for c in at.caption)
    assert next(b for b in at.button if b.label == "Save split").disabled


def test_alone_in_the_app_explains_how_a_partner_joins():
    at = run(users=USERS[:1])
    assert any("Sign up" in c.value for c in at.caption)
