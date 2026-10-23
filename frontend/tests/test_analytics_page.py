"""The shared-expense overview (Our expenses, and My expenses' "My share over time") from mocked API responses."""
import html
import re
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from conftest import empty_payload, kpi_cards, sample_expenses, sample_payload

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


def kpis(at):
    """Every ui.kpi on the page as (label, value): labels are markdown (for their tooltip), values html."""
    labels = [re.search(r'class="hf-(?:kpi|hero)-label">(.*?)</span>', m.value).group(1)
              for m in at.markdown if "hf-kpi-label" in m.value or "hf-hero-label" in m.value]
    values = [re.search(r'class="hf-kpi-value">(.*?)</div>', str(h.proto.body)).group(1)
              for h in at.get("html") if str(h.proto.body).startswith("<div class=\"hf-kpi")]
    return [(html.unescape(label), html.unescape(value)) for label, value in zip(labels, values)]


def overview(at):
    """Month by month's four cards: the one before "3-month average" and the three from it."""
    pairs = kpis(at)
    i = next(n for n, (label, _) in enumerate(pairs) if label.startswith("3-month average"))
    return pairs[i - 1:i + 3]


def test_renders_with_data():
    at = run_page(fake_api(lambda month: sample_payload(month)))
    assert not at.exception
    assert [t.label for t in at.tabs] == ["This month", "Month by month", "Settle up"]
    cards = overview(at)
    assert [label for label, _ in cards] == [
        "Shared total so far", "3-month average (same days)", "Shared expenses so far", "Biggest increase"]
    assert cards[3][1] == "Food"
    assert not at.dataframe  # charts, not tables
    assert len(at.get("arrow_vega_lite_chart")) >= 10
    assert not at.error


def test_complete_month_is_not_labelled_to_date():
    at = run_page(fake_api(lambda month: sample_payload(month, is_partial=False, as_of_day=31)))
    assert not at.exception
    assert not any("so far" in label for label, _ in overview(at))


def test_my_share_lens():
    # Preset through session state: AppTest 1.50 can't set_value on a
    # single-select segmented_control next to another one.
    at = run_page(fake_api(lambda month: sample_payload(month)), page=MINE, mine_window=6, mine_view="shared")
    assert not at.exception
    assert overview(at)[0][0].startswith("My share")


def money(text: str) -> float:
    return float(text.replace("R$", "").replace(".", "").replace(",", ".").strip())


def test_my_spending_views_and_everything_adds_both_halves():
    get = fake_api(lambda month: sample_payload(month))
    personal = run_page(get, page=MINE, mine_view="personal")
    assert not personal.exception
    assert overview(personal)[0][0].startswith("Personal")
    st.cache_data.clear()
    everything = run_page(get, page=MINE)  # the default view
    assert not everything.exception
    assert overview(everything)[0][0].startswith("I spent")
    # The fake answers both endpoints with the same rows, so everything is twice either half.
    assert money(overview(everything)[0][1]) == 2 * money(overview(personal)[0][1])


def test_personal_view_asks_only_the_personal_endpoints():
    # Both tabs (This month and Over time) set to Personal only.
    calls = []
    inner = fake_api(lambda month: sample_payload(month))

    def get(url, *args, **kwargs):
        calls.append(urlparse(url).path)
        return inner(url, *args, **kwargs)

    at = run_page(get, page=MINE, mine_view="personal", mine_daily_view="personal")
    assert not at.exception
    analytics_calls = [c for c in calls if "/analytics/" in c]
    assert analytics_calls and all("/analytics/personal" in c for c in analytics_calls)


def test_empty_data_points_to_the_tracker():
    at = run_page(fake_api(lambda month: empty_payload(month)))
    assert not at.exception
    assert any("No shared expenses" in i.value for i in at.info)
    assert not kpis(at)


def test_month_with_nothing_still_renders_the_trend():
    def payload(month):
        p = sample_payload(month)
        p["rows"] = [r for r in p["rows"] if r["month"] != month]
        return p
    at = run_page(fake_api(payload, expenses=[]))
    assert not at.exception
    assert overview(at)[0][1] == "R$ 0,00"
    assert len(at.get("arrow_vega_lite_chart")) >= 1


def test_api_error_is_shown_not_raised():
    at = run_page(fake_api(lambda month: {}, status=500))
    assert not at.exception
    assert at.error


def test_month_by_month_counts_only_what_the_filters_keep():
    everything = run_page(fake_api(lambda month: sample_payload(month)))
    assert overview(everything)[0][1] == "R$ 2.370,00"  # rent + groceries + restaurants
    st.cache_data.clear()
    day_to_day = run_page(fake_api(lambda month: sample_payload(month)), our_focus="Day-to-day")
    assert not day_to_day.exception
    assert overview(day_to_day)[0][1] == "R$ 370,00"  # no rent
    st.cache_data.clear()
    housing = run_page(fake_api(lambda month: sample_payload(month)), our_categories=["Housing"])
    assert overview(housing)[0][1] == "R$ 2.000,00"


def test_a_partly_logged_last_month_is_named_not_compared():
    # Logging began on 26 September: October can't be judged against it.
    def payload(month):
        return {**sample_payload(month), "first_date": "2026-09-26"}
    at = run_page(fake_api(payload))
    assert not at.exception
    cards = kpi_cards(at)
    assert cards["Shared total so far"]["lines"] == ["Sep 26: R$ 2.980,00, logged from the 26th only"]
    assert cards["Biggest increase"]["value"] == "—"
    assert not any("Where does the difference come from?" in s.value for s in at.subheader)
    assert any("logged from the 26th only" in c.value for c in at.caption)  # the trend's footnote


def test_monthly_targets_show_as_a_dark_tick_on_our_expenses():
    inner = fake_api(lambda month: sample_payload(month))

    def get(url, *args, **kwargs):
        if "/category_targets" in url:
            return MagicMock(status_code=200, json=MagicMock(return_value=[
                {"primary_category": "Food", "amount": "500.00"}]))
        return inner(url, *args, **kwargs)

    at = run_page(get)
    assert not at.exception
    assert any("Dark tick: the monthly target." in c.value for c in at.caption)


def test_installments_when_billed_asks_for_the_billed_basis():
    queries = []
    inner = fake_api(lambda month: sample_payload(month))

    def get(url, *args, **kwargs):
        parsed = urlparse(url)
        if parsed.path.endswith("/analytics/shared"):
            queries.append(parse_qs(parsed.query).get("basis", [None])[0])
        return inner(url, *args, **kwargs)

    default = run_page(get)
    assert not default.exception
    assert queries and set(queries) == {"bought"}
    assert not any("billed" in c.value for c in default.caption)

    queries.clear()
    st.cache_data.clear()
    billed = run_page(get, our_billed=True)
    assert not billed.exception
    assert queries and set(queries) == {"billed"}
    assert any("month they're billed" in c.value for c in billed.caption)
