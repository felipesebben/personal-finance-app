"""The shared-expense overview (Our expenses, and My expenses' "My share over time") from mocked API responses."""
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from conftest import empty_payload, sample_expenses, sample_payload

PAGE = "pages/2_Our_expenses.py"
MINE = "pages/3_My_expenses.py"


def fake_api(payload_for, expenses=None, status=200):
    """
    A requests.get stand-in: answers /analytics/shared and /analytics/personal
    for the requested month (the same payload), and their expenses routes.
    """
    def get(url, headers=None, **kwargs):
        parsed = urlparse(url)
        month = parse_qs(parsed.query).get("month", [None])[0]
        response = MagicMock(status_code=status)
        if parsed.path.endswith(("/analytics/shared/expenses", "/analytics/personal/expenses")):
            response.json.return_value = sample_expenses() if expenses is None else expenses
        elif parsed.path.endswith(("/analytics/shared", "/analytics/personal")):
            response.json.return_value = payload_for(month)
        else:  # the page's other reads (payment methods, household, balances...): nothing
            response.status_code = 200
            response.json.return_value = []
        return response
    return get


@pytest.fixture(autouse=True)
def fresh_cache():
    # The page caches API calls; each test brings its own responses.
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def run_page(get, page=PAGE, **state):
    # Start from Home.py, as `streamlit run` does, so st.page_link can resolve
    # the other pages, then open the page.
    at = AppTest.from_file("Home.py", default_timeout=30)
    at.switch_page(page)
    at.session_state["access_token"] = "test-token"
    for key, value in state.items():
        at.session_state[key] = value
    with patch("requests.get", side_effect=get):
        at.run()
    return at


def labels(elements):
    return [e.label for e in elements]


def test_renders_with_data():
    at = run_page(fake_api(lambda month: sample_payload(month)))
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Overview", "Settle up"]
    assert len(at.metric) == 4
    assert any("to date" in label for label in labels(at.metric))
    assert at.metric[3].value == "Food"  # biggest increase
    assert len(at.get("arrow_vega_lite_chart")) >= 5
    assert not at.error


def test_complete_month_is_not_labelled_to_date():
    at = run_page(fake_api(lambda month: sample_payload(month, is_partial=False, as_of_day=31)))
    assert not at.exception
    assert not any("to date" in label for label in labels(at.metric))


def test_my_share_lens():
    # Preset through session state: AppTest 1.50 can't set_value on a
    # single-select segmented_control next to another one.
    at = run_page(fake_api(lambda month: sample_payload(month)), page=MINE, mine_window=6, mine_view="shared")
    assert not at.exception
    assert at.metric[0].label.startswith("My share")


def money(text: str) -> float:
    return float(text.replace("R$", "").replace(".", "").replace(",", ".").strip())


def test_my_spending_views_and_everything_adds_both_halves():
    get = fake_api(lambda month: sample_payload(month))
    personal = run_page(get, page=MINE, mine_view="personal")
    assert not personal.exception
    assert personal.metric[0].label.startswith("Personal")
    st.cache_data.clear()
    everything = run_page(get, page=MINE)  # the default view
    assert not everything.exception
    assert everything.metric[0].label.startswith("I spent")
    # The fake answers both endpoints with the same rows, so everything is twice either half.
    assert money(everything.metric[0].value) == 2 * money(personal.metric[0].value)


def test_personal_view_asks_only_the_personal_endpoints():
    calls = []
    inner = fake_api(lambda month: sample_payload(month))

    def get(url, *args, **kwargs):
        calls.append(urlparse(url).path)
        return inner(url, *args, **kwargs)

    at = run_page(get, page=MINE, mine_view="personal")
    assert not at.exception
    analytics_calls = [c for c in calls if "/analytics/" in c]
    assert analytics_calls and all("/analytics/personal" in c for c in analytics_calls)


def test_empty_data_points_to_the_tracker():
    at = run_page(fake_api(lambda month: empty_payload(month)))
    assert not at.exception
    assert any("No shared expenses" in i.value for i in at.info)
    assert not at.metric


def test_month_with_nothing_still_renders_the_trend():
    def payload(month):
        p = sample_payload(month)
        p["rows"] = [r for r in p["rows"] if r["month"] != month]
        return p
    at = run_page(fake_api(payload, expenses=[]))
    assert not at.exception
    assert at.metric[0].value == "R$ 0,00"
    assert len(at.get("arrow_vega_lite_chart")) >= 1


def test_api_error_is_shown_not_raised():
    at = run_page(fake_api(lambda month: {}, status=500))
    assert not at.exception
    assert at.error
