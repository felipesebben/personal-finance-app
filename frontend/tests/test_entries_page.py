"""The Entries page, driven through AppTest with the API mocked: audit the table, open an expense, fix it."""
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from test_tracker_entry import (  # noqa: F401 (fixtures)
    CATEGORIES, EXPENDITURE, ME, PAYMENT_METHODS, api, fake_get, response, single_select_button_groups,
)

PAGE = "pages/4_Entries.py"
HER = {"user_id": 2, "full_name": "Her", "email": "her@example.com"}
LOGGED = [
    {**EXPENDITURE, "expenditure_id": 7, "current_installment": 1, "total_installments": 10,
     "category": CATEGORIES[0], "payment_method": PAYMENT_METHODS[0],
     "splits": [{"user_id": 1, "share_pct": "0.6000", "share_amount": "1000.00", "split_source": "household_default"},
                {"user_id": 2, "share_pct": "0.4000", "share_amount": "666.67", "split_source": "household_default"}],
     "updated_at": "2026-10-06T12:00:00+00:00", "updated_by": HER},
    {**EXPENDITURE, "expenditure_id": 8, "transaction_timestamp": "2026-10-03T15:30:00+00:00", "price": "45.90",
     "my_share": "45.90", "is_shared": False, "total_installments": 1, "user": HER,
     "category": CATEGORIES[1], "payment_method": PAYMENT_METHODS[2],
     "splits": [{"user_id": 2, "share_pct": "1.0000", "share_amount": "45.90", "split_source": "not_shared"}]},
]


def get(url, *args, **kwargs):
    if "/expenditures" in url:
        return response(LOGGED)
    return fake_get(url)


def open_page(**state):
    app = AppTest.from_file("Home.py", default_timeout=30)
    app.session_state["access_token"] = "x"
    app.session_state["user_email"] = ME
    app.run()
    app.switch_page(PAGE)
    for key, value in state.items():
        app.session_state[key] = value
    return app.run()


def test_the_table_lists_everything_with_its_trace(api):
    api[0].side_effect = get
    at = open_page(entries_month=None)  # all months
    assert not at.exception
    table = at.dataframe[0].value
    assert list(table["Price"]) == ["R$ 1.666,67", "R$ 45,90"]
    assert list(table["Type"]) == ["Shared · 10x", "Personal"]
    assert list(table["Last edit"]) == ["Her · 06/10 09:00", ""]
    assert any("2 expenses · R\$ 1.712,57 · your part" in c.value for c in at.caption)


def test_filters_narrow_the_table(api):
    api[0].side_effect = get
    at = open_page(entries_month=None, entries_kind="personal")
    assert list(at.dataframe[0].value["Price"]) == ["R$ 45,90"]
    at.text_input(key="entries_search").set_value("nothing like this").run()
    assert any("Nothing matches" in c.value for c in at.caption)


def test_a_ticked_row_opens_the_form_filled_in(api):
    api[0].side_effect = get
    at = open_page(entries_month=None, entries_table_0={"selection": {"rows": [0], "columns": []}})
    assert not at.exception
    assert any("Last edited by Her on 6 October at 09:00" in c.value for c in at.caption)
    assert at.text_input(key="edit7_price_0").value == "1.666,67"
    assert at.selectbox(key="edit7_category_0_primary").value == "Food"
    assert at.selectbox(key="edit7_payment_0_primary").value == "Credit Card"
    assert any("Split as when it was logged: Me 60% · Her 40%" in c.value for c in at.caption)


def test_saving_sends_a_patch_with_the_fix(api):
    api[0].side_effect = get
    at = open_page(entries_month=None, entries_table_0={"selection": {"rows": [1], "columns": []}})
    assert at.text_input(key="edit8_price_0").value == "45,90"
    assert at.toggle(key="edit8_shared_0").value is False
    at.text_input(key="edit8_price_0").set_value("54,90").run()
    with patch("requests.patch", return_value=response(LOGGED[1])) as sent:
        at.button(key="edit8_submit_0").click().run()
    assert not at.exception
    [(url,), kwargs] = sent.call_args
    assert url.endswith("/expenditures/8")
    payload = kwargs["json"]
    assert payload["price"] == "54.90" and payload["category_id"] == 2 and payload["payment_method_id"] == 12
    assert payload["is_shared"] is False and payload["pet_id"] is None
    assert "shares" not in payload and "reset_split" not in payload
    assert "user_id" not in payload  # the payer never changes


def test_installments_are_filled_in_and_sent(api):
    api[0].side_effect = get
    at = open_page(entries_month=None, entries_table_0={"selection": {"rows": [0], "columns": []}})
    with patch("requests.patch", return_value=response(LOGGED[0])) as sent:
        at.button(key="edit7_submit_0").click().run()
    assert not at.exception
    payload = sent.call_args.kwargs["json"]
    assert (payload["total_installments"], payload["current_installment"], payload["is_shared"]) == (10, 1, True)
    assert "shares" not in payload and "reset_split" not in payload  # keeps the split it was logged with
