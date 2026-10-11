"""
The Tracker's expense entry form, driven through AppTest with the API mocked.

The page calls requests.get / requests.post directly, so patching those on
the requests module is enough; nothing here needs a backend.
"""
from unittest.mock import MagicMock, patch

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import ButtonGroup

PAGE = "pages/1_Tracker.py"
ME = "me@example.com"

CATEGORIES = [
    {"category_id": 1, "primary_category": "Food", "sub_category": "Groceries", "cost_type": "Variable"},
    {"category_id": 2, "primary_category": "Home", "sub_category": "Furniture", "cost_type": "Variable"},
]
PAYMENT_METHODS = [
    {"payment_method_id": 10, "method_name": "Credit Card", "institution": "Nubank", "is_credit": True},
    {"payment_method_id": 11, "method_name": "Cash", "institution": None, "is_credit": False},
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


def test_overview_formats_money_the_brazilian_way(api):
    get, _ = api

    def with_overview(url, *args, **kwargs):
        if "/summary/" in url:
            return response(SUMMARY)
        if "/balances/" in url:
            return response(BALANCES)
        if url.endswith("/expenditures"):
            return response([EXPENDITURE])
        return fake_get(url)

    get.side_effect = with_overview
    # Start from Home so st.page_link (used in the tabs) can resolve pages.
    app = AppTest.from_file("Home.py", default_timeout=30)
    app.session_state["access_token"] = "x"
    app.session_state["user_email"] = ME
    app.run()
    app.switch_page(PAGE)
    at = app.run()

    assert not at.exception
    # This month: three explained metrics, deltas against the named previous month.
    assert [m.label for m in at.metric] == ["You spent", "Your share of shared", "Household shared total"]
    assert at.metric[0].value == "R$ 1.234,50"
    assert at.metric[0].delta == "+R$ 234,50 vs September 2026"
    assert at.metric[2].delta == "-R$ 33,33 vs September 2026"
    # Settle up leads with the answer, then the plain-language table.
    html = " ".join(str(h.proto) for h in at.get("html"))
    assert "Her owes Me" in html and "R$ 666,67" in html
    owed = next(df.value for df in at.dataframe if "Should have paid" in df.value.columns)
    assert list(owed["Difference"]) == ["R$ 666,67", "-R$ 666,67"]
    # The other-payment form is pre-filled with what's owed, typed like a price.
    assert "666,67" in [t.value for t in at.text_input]
    # History: full price and the viewer's part, with the type spelled out.
    recent = at.dataframe[-1].value
    assert list(recent["Price"]) == ["R$ 1.666,67"]
    assert list(recent["Your part"]) == ["R$ 1.000,00"]
    assert list(recent["Type"]) == ["Shared · 10x"]
