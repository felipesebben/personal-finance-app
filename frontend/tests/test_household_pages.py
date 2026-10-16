"""
Our expenses and My expenses, driven through AppTest with the API mocked
(the same fakes as the Add expense tests).
"""
from urllib.parse import parse_qs, urlparse

import pytest
from streamlit.testing.v1 import AppTest

from conftest import empty_payload
from test_tracker_entry import (
    BALANCES, EXPENDITURE, JOINT_ENTRIES, JOINT_STATUS, ME, PAYMENT_METHODS, SUMMARY,
    api, captions, fake_get, response, single_select_button_groups,  # noqa: F401 (fixtures)
)

OURS = "pages/2_Our_expenses.py"
MINE = "pages/3_My_expenses.py"


def answering(extra: dict):
    """requests.get stand-in: `extra` maps a URL fragment to a payload; analytics answers empty."""
    def get(url, *args, **kwargs):
        for fragment, payload in extra.items():
            if fragment in url:
                return response(payload)
        if "/analytics/shared" in url or "/analytics/personal" in url:
            month = parse_qs(urlparse(url).query).get("month", [None])[0]
            return response(empty_payload(month))
        return fake_get(url)
    return get


def open_page(page):
    # Start from Home so st.page_link can resolve pages.
    app = AppTest.from_file("Home.py", default_timeout=30)
    app.session_state["access_token"] = "x"
    app.session_state["user_email"] = ME
    app.run()
    app.switch_page(page)
    return app.run()


def test_our_expenses_tabs_and_the_joint_account(api):
    get, post = api
    get.side_effect = answering({"/joint/status": [JOINT_STATUS], "/joint/entries": JOINT_ENTRIES})
    at = open_page(OURS)
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Overview", "Joint account", "Settle up"]

    metrics = {m.label: m for m in at.metric}
    assert metrics["Left in the account"].value == "R$ 500,00"
    assert metrics["Spent this month"].delta == "+R$ 100,00 vs usual"
    assert metrics["Runs out"].value == "20/12"
    assert any("▲" in c and "100,00 more than usual" in c for c in captions(at))
    assert list(at.dataframe[-1].value["What"]) == ["Balance check"]

    at.text_input(key="joint_amount").input("1.500,00")
    at.button(key="FormSubmitter:joint_entry_form-Save").click().run()
    assert not at.exception
    url, sent = post.call_args.args[0], post.call_args.kwargs["json"]
    assert url.endswith("/joint/entries")
    assert (sent["payment_method_id"], sent["kind"], sent["amount"]) == (15, "deposit", "1500.00")


def test_no_joint_tab_without_a_joint_method(api, monkeypatch):
    import test_tracker_entry
    monkeypatch.setattr(test_tracker_entry, "PAYMENT_METHODS", [m for m in PAYMENT_METHODS if not m.get("is_joint")])
    api[0].side_effect = answering({})
    at = open_page(OURS)
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Overview", "Settle up"]


def test_our_expenses_settle_up_leads_with_who_owes(api):
    api[0].side_effect = answering({"/balances/": BALANCES})
    at = open_page(OURS)
    assert not at.exception
    html = " ".join(str(h.proto) for h in at.get("html"))
    assert "Her owes Me" in html and "R$ 666,67" in html
    owed = next(df.value for df in at.dataframe if "Should have paid" in df.value.columns)
    assert list(owed["Difference"]) == ["R$ 666,67", "-R$ 666,67"]
    # The other-payment form is pre-filled with what's owed, typed like a price.
    assert "666,67" in [t.value for t in at.text_input]


def test_my_expenses_month_and_entries(api):
    api[0].side_effect = answering({"/summary/": SUMMARY, "/expenditures": [EXPENDITURE]})
    at = open_page(MINE)
    assert not at.exception
    assert [t.label for t in at.tabs] == ["This month", "Over time", "My entries"]
    # This month: what I spent, split into my share of shared and my personal spending.
    assert [m.label for m in at.metric] == ["You spent", "Your share of shared", "Personal"]
    assert at.metric[0].value == "R$ 1.234,50"
    assert at.metric[0].delta == "+R$ 234,50 vs September 2026"
    assert at.metric[2].value == "R$ 234,50"
    # My entries: full price and the viewer's part, with the type spelled out.
    recent = at.dataframe[-1].value
    assert list(recent["Price"]) == ["R$ 1.666,67"]
    assert list(recent["Your part"]) == ["R$ 1.000,00"]
    assert list(recent["Type"]) == ["Shared · 10x"]


@pytest.mark.parametrize("page", [OURS, MINE])
def test_household_pages_never_show_the_lens_switch(api, page):
    # Each page has one point of view: Household on Our expenses, My share on My expenses.
    api[0].side_effect = answering({})
    at = open_page(page)
    assert not at.exception
    assert "Lens" not in [b.label for b in at.button_group]


def test_my_entries_marks_a_treat(api):
    treat = {**EXPENDITURE, "is_treat": True, "total_installments": 1}
    api[0].side_effect = answering({"/expenditures": [treat]})
    at = open_page(MINE)
    assert not at.exception
    assert list(at.dataframe[-1].value["Type"]) == ["Shared · treat"]
