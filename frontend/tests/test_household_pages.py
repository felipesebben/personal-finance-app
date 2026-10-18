"""
Our expenses and My expenses, driven through AppTest with the API mocked
(the same fakes as the Add expense tests).
"""
import re
from urllib.parse import parse_qs, urlparse

import pytest
from streamlit.testing.v1 import AppTest

from conftest import empty_payload, kpi_cards
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
        if "/analytics/" in url and "/expenses" in url:
            return response([])
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
    assert [t.label for t in at.tabs] == ["This month", "Month by month", "Joint account", "Settle up"]

    cards = kpi_cards(at)
    assert cards["Left in the account"]["value"] == "R$ 500,00"
    assert cards["Spent this month"]["lines"][0] == "▲ +R$ 100,00 vs usual"
    assert cards["Runs out"]["value"] == "20/12"
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
    assert [t.label for t in at.tabs] == ["This month", "Month by month", "Settle up"]


def test_our_expenses_settle_up_leads_with_who_owes(api):
    api[0].side_effect = answering({"/balances/": BALANCES})
    at = open_page(OURS)
    assert not at.exception
    html = " ".join(str(h.proto) for h in at.get("html"))
    assert "Her owes Me" in html and "R$ 666,67" in html
    # One card per person instead of a table.
    cards = kpi_cards(at)
    assert cards["Me"]["value"] == "Is owed R$ 666,67" and cards["Her"]["value"] == "Owes R$ 666,67"
    assert cards["Me"]["lines"][:2] == ["Paid R$ 1.666,67", "Their share R$ 1.000,00"]
    # The other-payment form is pre-filled with what's owed, typed like a price.
    assert "666,67" in [t.value for t in at.text_input]


def test_my_expenses_month_and_entries(api):
    def get(url, *args, **kwargs):
        query = parse_qs(urlparse(url).query)
        if "/analytics/shared/daily" in url or "/analytics/personal/daily" in url:
            return response(daily_payload(query["month"][0]))
        if "/expenditures" in url:
            return response([EXPENDITURE])
        return answering({})(url)

    api[0].side_effect = get
    at = open_page(MINE)
    assert not at.exception
    assert [t.label for t in at.tabs] == ["This month", "Over time", "My entries"]
    # This month: the daily view of my share, shared and personal added together by default.
    html = kpi_text(at)
    # Both endpoints answer the same two rows a month, my share R$ 60 each: 4 x 60.
    assert "Spent in" in html and "R$ 240,00" in html
    assert at.session_state["mine_daily_view"] == "all"
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


def test_home_briefs_the_month_after_login(api):
    from conftest import sample_payload
    api[0].side_effect = answering({
        "/analytics/shared": sample_payload("2026-10"),
        "/balances/": BALANCES,
        "/joint/status": [dict(JOINT_STATUS, runs_out_on="2026-10-20", month="2026-10")],
    })
    app = AppTest.from_file("Home.py", default_timeout=30)
    app.session_state["access_token"] = "x"
    app.session_state["user_email"] = ME
    at = app.run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "This month so far" in text
    assert "Shared: R\$ 2.370,00" in text and "Biggest: Housing" in text
    assert "Settle up: Her owes you R\$ 666,67" in text
    assert "Joint account: R\$ 500,00 left." in text


def test_home_briefing_says_nothing_without_data(api):
    api[0].side_effect = answering({})
    app = AppTest.from_file("Home.py", default_timeout=30)
    app.session_state["access_token"] = "x"
    app.session_state["user_email"] = ME
    at = app.run()
    assert not at.exception
    assert not at.error


def daily_payload(month):
    """Six earlier months and this one, so every comparison shows: groceries on the 1st, an IPVA on the 2nd."""
    from analytics_shaping import shift_month
    months = [shift_month(month, -k) for k in range(6, -1, -1)]
    groceries = {"primary_category": "Food", "sub_category": "Groceries", "cost_type": "Variable", "nature": "Normal"}
    ipva = {"primary_category": "Transport", "sub_category": "IPVA", "cost_type": "Fixed", "nature": "Annual"}
    rows = [{"date": f"{m}-0{d}", **kind, "household": "100.00", "mine": "60.00", "count": 1}
            for m in months for d, kind in ((1, groceries), (2, ipva))]
    return {"month": month, "months": months, "is_partial": False, "as_of_day": 28, "today": f"{month}-28",
            "rows": rows}


def daily_get(day_expenses=None):
    def get(url, *args, **kwargs):
        query = parse_qs(urlparse(url).query)
        if "/analytics/shared/daily" in url:
            return response(daily_payload(query["month"][0]))
        if "/analytics/shared/expenses" in url:  # a day's, or a category's month
            return response(day_expenses or [])
        if "/analytics/shared" in url:
            return response(empty_payload(query.get("month", [None])[0]))
        return fake_get(url)
    return get


def kpi_text(at):
    """The cards' text: labels are markdown (for their tooltip), numbers and lines html."""
    return " ".join([str(h.proto) for h in at.get("html")] + [m.value for m in at.markdown])


def test_this_month_tab_answers_first_then_charts(api):
    api[0].side_effect = daily_get()
    at = open_page(OURS)
    assert not at.exception
    assert [t.label for t in at.tabs][:2] == ["This month", "Month by month"]
    html = kpi_text(at)
    assert "Spent in" in html and "R$ 200,00" in html  # groceries + IPVA (the fake month is finished)
    for card in ("Per day", "Last month · ", "Usual month", "Days with spending"):
        assert card in html
    # Hero sparkline, the calendar, card sparklines, running total, where the money goes (categories,
    # inside), the biggest days (days, purchases) and the weekday chart. Charts, no tables.
    assert len(at.get("arrow_vega_lite_chart")) >= 11
    assert not at.dataframe


def test_this_month_can_leave_out_one_offs_and_fixed_costs(api):
    api[0].side_effect = daily_get()
    app = AppTest.from_file("Home.py", default_timeout=30)
    app.session_state["access_token"] = "x"
    app.session_state["user_email"] = ME
    app.run()
    app.switch_page(OURS)
    # AppTest can't set a segmented control: preset it.
    app.session_state["our_daily_focus"] = "Day-to-day"
    at = app.run()
    assert not at.exception
    html = kpi_text(at)
    assert "Spent in" in html and "· day-to-day costs" in html and "R$ 100,00" in html
    at.toggle(key="our_daily_one_offs").set_value(True).run()
    assert "without one-offs" in kpi_text(at)


def test_the_biggest_category_and_day_open_without_a_tap(api):
    api[0].side_effect = daily_get([{
        "expenditure_id": 7, "transaction_timestamp": "2026-10-01T15:00:00Z",
        "primary_category": "Food", "sub_category": "Groceries", "cost_type": "Variable",
        "payment_method": "Pix", "institution": "Nubank", "paid_by": "Her",
        "price": "100.00", "mine": "60.00", "share_pct": "0.6000",
        "current_installment": 1, "total_installments": 1, "nature": "Normal",
    }])
    at = open_page(OURS)
    assert not at.exception
    # Before any pick, each opens on the biggest: both categories cost R$ 100,00 this month, so the
    # tie goes to the name (Food), and both days too, so it goes to the earlier day (the 1st).
    assert at.button_group(key="our_daily_inside").value == ["Food"]
    month = at.selectbox(key="our_daily_month").value
    assert at.selectbox(key="our_daily_day").value == f"{month}-01"
    # That day's purchases were fetched for its chart.
    assert any(f"day={month}-01" in str(c.args[0]) for c in api[0].call_args_list)
