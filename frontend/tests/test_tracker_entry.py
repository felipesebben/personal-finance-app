"""
The Add expense page's entry form, driven through AppTest with the API mocked.

The page calls requests.get / requests.post directly, so patching those on
the requests module is enough; nothing here needs a backend.
"""
from unittest.mock import MagicMock, patch

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import ButtonGroup

PAGE = "pages/1_Add_expense.py"
ME = "me@example.com"

CATEGORIES = [
    {"category_id": 1, "primary_category": "Food", "sub_category": "Groceries", "cost_type": "Variable"},
    {"category_id": 2, "primary_category": "Home", "sub_category": "Furniture", "cost_type": "Variable"},
    {"category_id": 3, "primary_category": "Pets", "sub_category": "Vet", "cost_type": "Variable", "for_pets": True},
]
PETS = [{"pet_id": 7, "name": "Thor"}, {"pet_id": 8, "name": "Luna"}]
PAYMENT_METHODS = [
    {"payment_method_id": 10, "method_name": "Credit Card", "institution": "Nubank", "is_credit": True},
    {"payment_method_id": 11, "method_name": "Cash", "institution": None, "is_credit": False},
    # Pix registered only without a bank; Debit Card both with and without one.
    {"payment_method_id": 12, "method_name": "Pix", "institution": None, "is_credit": False},
    {"payment_method_id": 13, "method_name": "Debit Card", "institution": "Itaú", "is_credit": False},
    {"payment_method_id": 14, "method_name": "Debit Card", "institution": None, "is_credit": False},
    # The account you both top up, e.g. for groceries.
    {"payment_method_id": 15, "method_name": "Debit Card", "institution": "Nubank Conjunta",
     "is_credit": False, "is_joint": True},
]
HOUSEHOLD = [
    {"user_id": 1, "share_pct": "0.6000", "user": {"user_id": 1, "full_name": "Me", "email": ME}},
    {"user_id": 2, "share_pct": "0.4000", "user": {"user_id": 2, "full_name": "Her", "email": "her@example.com"}},
]


def response(payload, status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = payload
    r.text = str(payload)
    return r


def fake_get(url, *args, **kwargs):
    for endpoint, payload in [
        ("/categories", CATEGORIES),
        ("/payment_methods", PAYMENT_METHODS),
        ("/household_settings", HOUSEHOLD),
        ("/pets", PETS),
    ]:
        if endpoint in url:
            return response(payload)
    # Summary, balances, settlements and expenditures: nothing logged yet.
    return response([])


@pytest.fixture(autouse=True)
def single_select_button_groups(monkeypatch):
    """
    AppTest 1.50 models st.segmented_control as a multi-select ButtonGroup:
    it iterates the value, so a single-select "Normal" becomes "N", "o", ...
    and every interaction on the page fails. Present a single value as a
    one-item list, which is also what the browser sends for it.
    """
    multi = ButtonGroup.value

    def value(self):
        v = multi.fget(self)
        return v if isinstance(v, list) else ([] if v is None else [v])

    monkeypatch.setattr(ButtonGroup, "value", property(value))


@pytest.fixture
def api():
    st.cache_data.clear()  # get_data is cached across AppTest runs in one process
    with patch("requests.get", side_effect=fake_get) as get, \
            patch("requests.post", return_value=response({"expenditure_id": 1})) as post:
        yield get, post
    st.cache_data.clear()


@pytest.fixture
def at(api):
    # Start from Home so st.page_link (used in the tabs) can resolve pages.
    app = AppTest.from_file("Home.py", default_timeout=30)
    app.session_state["access_token"] = "x"
    app.session_state["user_email"] = ME
    app.run()
    app.switch_page(PAGE)
    return app.run()


def captions(at):
    return [c.value for c in at.caption]


def submit(at):
    at.button(key="entry_submit_0").click().run()


def test_preview_shows_installments_and_my_share(at):
    assert not at.exception
    at.text_input(key="entry_price_0").input("1.200,00").run()
    at.selectbox(key="entry_payment_0_primary").select("Credit Card").run()
    at.button_group(key="entry_inst_pick_0").set_value([10]).run()

    assert not at.exception
    assert r"R\$ 1.200,00 · 10x R\$ 120,00 · your share 60% = R\$ 720,00" in captions(at)


def test_invalid_price_shows_error_and_does_not_post(at, api):
    _, post = api
    at.text_input(key="entry_price_0").input("12,345").run()
    assert any("at most two digits" in e.value for e in at.error)

    submit(at)
    assert not at.exception
    assert any("Price" in e.value for e in at.error)
    post.assert_not_called()


def test_valid_submit_posts_price_as_string_and_resets(at, api):
    _, post = api
    at.text_input(key="entry_price_0").input("1.200,00").run()
    at.selectbox(key="entry_payment_0_primary").select("Credit Card").run()
    at.selectbox(key="entry_payment_0_secondary_Credit Card").select("Nubank").run()
    at.button_group(key="entry_inst_pick_0").set_value([10]).run()
    at.selectbox(key="entry_category_0_primary").select("Home").run()
    at.selectbox(key="entry_category_0_secondary_Home").select("Furniture").run()
    submit(at)

    assert not at.exception
    post.assert_called_once()
    url, payload = post.call_args.args[0], post.call_args.kwargs["json"]
    assert url.endswith("/expenditures/")
    assert payload["price"] == "1200.00"
    assert payload["category_id"] == 2
    assert payload["payment_method_id"] == 10
    assert payload["total_installments"] == 10
    assert payload["current_installment"] == 1
    assert payload["nature"] == "Normal"
    assert payload["is_shared"] is True
    assert "shares" not in payload

    # The confirmation survived the rerun, and the form came back empty
    # under the next nonce.
    assert [t.value for t in at.toast] == [r"Expense saved: R\$ 1.200,00"]
    assert at.session_state["entry_nonce"] == 1
    assert at.text_input(key="entry_price_1").value == ""
    assert at.selectbox(key="entry_payment_1_primary").value is None


def fill_rest_and_submit(at):
    at.text_input(key="entry_price_0").input("50").run()
    at.selectbox(key="entry_category_0_primary").select("Food").run()
    at.selectbox(key="entry_category_0_secondary_Food").select("Groceries").run()
    submit(at)


def test_method_without_institution_is_picked_and_submits(at, api):
    _, post = api
    at.selectbox(key="entry_payment_0_primary").select("Pix").run()

    inst = at.selectbox(key="entry_payment_0_secondary_Pix")
    assert inst.options == ["N/A"] and inst.value == "N/A" and inst.disabled
    assert any("Settings → Payment methods" in c for c in captions(at))

    fill_rest_and_submit(at)
    assert not at.exception
    assert post.call_args.kwargs["json"]["payment_method_id"] == 12


def test_cash_gets_no_add_a_bank_hint(at):
    at.selectbox(key="entry_payment_0_primary").select("Cash").run()
    assert at.selectbox(key="entry_payment_0_secondary_Cash").value == "N/A"
    assert not any("Settings → Payment methods" in c for c in captions(at))


def test_method_with_banks_offers_them_and_no_bank(at, api):
    _, post = api
    at.selectbox(key="entry_payment_0_primary").select("Debit Card").run()

    inst = at.selectbox(key="entry_payment_0_secondary_Debit Card")
    assert inst.options == ["Itaú", "Nubank Conjunta", "N/A"] and inst.value is None and not inst.disabled

    # Choosing is required while banks exist...
    fill_rest_and_submit(at)
    assert any("Institution" in e.value for e in at.error)
    post.assert_not_called()

    # ...and the bank picked decides which payment method is saved.
    at.selectbox(key="entry_payment_0_secondary_Debit Card").select("Itaú").run()
    submit(at)
    assert not at.exception
    assert post.call_args.kwargs["json"]["payment_method_id"] == 13


def test_its_on_me_is_sent_with_a_shared_expense(at, api):
    _, post = api
    at.selectbox(key="entry_payment_0_primary").select("Pix").run()
    treat = at.checkbox(key="entry_treat_0")
    assert treat.label == "It's on me: Her doesn't pay their share back"
    treat.check().run()
    fill_rest_and_submit(at)
    assert not at.exception
    sent = post.call_args.kwargs["json"]
    assert sent["is_shared"] is True and sent["is_treat"] is True


def test_its_on_me_is_off_by_default_and_gone_for_personal(at, api):
    _, post = api
    at.selectbox(key="entry_payment_0_primary").select("Pix").run()
    at.toggle(key="entry_shared_0").set_value(False).run()
    assert not [c for c in at.checkbox if c.key == "entry_treat_0"]
    fill_rest_and_submit(at)
    assert post.call_args.kwargs["json"]["is_treat"] is False


def test_joint_account_offers_no_its_on_me(at):
    at.selectbox(key="entry_payment_0_primary").select("Debit Card").run()
    at.selectbox(key="entry_payment_0_secondary_Debit Card").select("Nubank Conjunta").run()
    assert not [c for c in at.checkbox if c.key == "entry_treat_0"]


def test_joint_account_is_shared_and_says_nobody_owes(at, api):
    _, post = api
    at.selectbox(key="entry_payment_0_primary").select("Debit Card").run()
    at.selectbox(key="entry_payment_0_secondary_Debit Card").select("Nubank Conjunta").run()

    shared = at.toggle(key="entry_shared_joint_0")
    assert shared.value is True and shared.disabled
    assert any("joint account, so nobody owes" in c for c in captions(at))

    fill_rest_and_submit(at)
    sent = post.call_args.kwargs["json"]
    assert sent["payment_method_id"] == 15 and sent["is_shared"] is True


def test_personal_account_at_the_same_method_keeps_the_choice(at):
    at.selectbox(key="entry_payment_0_primary").select("Debit Card").run()
    at.selectbox(key="entry_payment_0_secondary_Debit Card").select("Itaú").run()
    assert not at.toggle(key="entry_shared_0").disabled
    assert not any("joint account" in c for c in captions(at))


JOINT_STATUS = {
    "payment_method_id": 15, "label": "Debit Card · Nubank Conjunta",
    "balance": "500.00", "counted_from": "2026-12-01T11:00:00Z",
    "deposits_since": "0.00", "spent_since": "500.00",
    "month": "2026-12", "as_of_day": 3, "days_in_month": 31,
    "spent_to_day": "500.00", "usual_to_day": "400.00", "usual_month_total": "450.00",
    "history_months": 2, "runs_out_on": "2026-12-20",
    "days": [{"day": d, "this_month": "500.00" if d <= 3 else None, "usual": "400.00"} for d in range(1, 32)],
}
JOINT_ENTRIES = [{"joint_entry_id": 3, "payment_method_id": 15, "kind": "balance", "amount": "1000.00",
                  "entry_at": "2026-12-01T11:00:00Z", "note": "start"}]


def choose_vet(at):
    at.text_input(key="entry_price_0").input("300").run()
    at.selectbox(key="entry_payment_0_primary").select("Pix").run()
    at.selectbox(key="entry_category_0_primary").select("Pets").run()
    at.selectbox(key="entry_category_0_secondary_Pets").select("Vet").run()


def test_pet_category_asks_which_pet_and_sends_it(at, api):
    _, post = api
    # Not asked for an ordinary category.
    assert not at.radio
    choose_vet(at)
    picker = at.radio(key="entry_pet_0")
    assert picker.options == ["Luna", "Thor", "Both"]

    submit(at)  # nothing picked yet
    assert any("Which pet" in e.value for e in at.error)
    post.assert_not_called()

    at.radio(key="entry_pet_0").set_value("Thor").run()
    submit(at)
    assert not at.exception
    assert post.call_args.kwargs["json"]["pet_id"] == 7


def test_both_pets_is_sent_without_a_pet_id(at, api):
    _, post = api
    choose_vet(at)
    at.radio(key="entry_pet_0").set_value("Both").run()
    submit(at)
    assert not at.exception
    assert "pet_id" not in post.call_args.kwargs["json"]


def test_custom_split_is_sent_as_shares(at, api):
    _, post = api
    at.text_input(key="entry_price_0").input("100").run()
    at.selectbox(key="entry_payment_0_primary").select("Cash").run()
    at.selectbox(key="entry_category_0_primary").select("Food").run()
    at.selectbox(key="entry_category_0_secondary_Food").select("Groceries").run()
    at.checkbox(key="entry_custom_0").check().run()
    at.number_input(key="entry_share_1_0").set_value(70).run()
    at.number_input(key="entry_share_2_0").set_value(30).run()
    assert r"R\$ 100,00 · your share 70% = R\$ 70,00" in captions(at)
    submit(at)

    assert not at.exception
    payload = post.call_args.kwargs["json"]
    assert payload["price"] == "100.00"
    assert payload["total_installments"] == 1
    assert payload["shares"] == [{"user_id": 1, "share_pct": "0.70"}, {"user_id": 2, "share_pct": "0.30"}]


SUMMARY = {
    "month": "2026-10", "previous_month": "2026-09",
    "me": {"total": "1234.50", "previous_total": "1000.00", "shared_share": "1000.00", "personal": "234.50"},
    "household_shared": {"total": "1666.67", "previous_total": "1700.00"},
    "by_category": [{"label": "Home", "amount": "1234.50"}],
    "by_cost_type": [{"label": "Variable", "amount": "1234.50"}],
}
BALANCES = {
    "month": "2026-10",
    "members": [
        {"user_id": 1, "full_name": "Me", "paid": "1666.67", "borne": "1000.00",
         "settled_out": "0.00", "settled_in": "0.00", "net": "666.67"},
        {"user_id": 2, "full_name": "Her", "paid": "0.00", "borne": "666.67",
         "settled_out": "0.00", "settled_in": "0.00", "net": "-666.67"},
    ],
    "transfers": [{"from_user_id": 2, "from_name": "Her", "to_user_id": 1, "to_name": "Me", "amount": "666.67"}],
}
EXPENDITURE = {
    "expenditure_id": 7, "transaction_timestamp": "2026-10-05T15:30:00+00:00", "price": "1666.67",
    "nature": "Normal", "is_shared": True, "my_share": "1000.00", "total_installments": 10,
    "user": {"user_id": 1, "full_name": "Me", "email": ME},
    "category": CATEGORIES[1], "payment_method": PAYMENT_METHODS[0],
}
