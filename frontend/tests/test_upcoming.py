"""upcoming.py: recurring bills not logged yet, and card installments billed this month."""
import datetime
from zoneinfo import ZoneInfo

import upcoming
from test_entries import expense

SP = ZoneInfo("America/Sao_Paulo")
TODAY = datetime.date(2026, 10, 12)
POWER = {"primary_category": "Housing", "sub_category": "Electricity", "cost_type": "Fixed", "for_pets": False}
NET = {"primary_category": "Housing", "sub_category": "Internet", "cost_type": "Fixed", "for_pets": False}
SOFA = {"primary_category": "Home", "sub_category": "Furniture", "cost_type": "Variable", "for_pets": False}


def bill(eid, when, price, category=POWER, **extra):
    return expense(eid, when=when, price=price, category=category, nature="Recurring",
                   **{"my_share": price, **extra})


def test_a_recurring_bill_not_logged_yet_is_still_to_come_at_its_latest_amount_and_day():
    logged = [
        bill(1, "2026-08-10T15:00:00+00:00", "150.00"),
        bill(2, "2026-09-12T15:00:00+00:00", "180.00"),   # the latest: R$ 180 on the 12th
        bill(3, "2026-09-05T15:00:00+00:00", "99.90", NET),
        bill(4, "2026-10-04T15:00:00+00:00", "99.90", NET),  # already logged this month
        bill(5, "2026-05-01T15:00:00+00:00", "70.00", SOFA),  # too long ago
    ]
    due = upcoming.recurring_due(logged, "2026-10", TODAY, "all", "Household", SP)
    assert list(due["name"]) == ["Housing › Electricity"]
    assert list(due["amount"]) == [180.0]
    assert list(due["text"]) == ["R$ 180 · usually the 12th"]
    assert due["cost_type"].iloc[0] == "Fixed" and due["nature"].iloc[0] == "Recurring"


def test_installments_billed_this_month_until_paid_off():
    sofa = expense(1, when="2026-07-20T15:00:00+00:00", price="1000.03", category=SOFA,
                   total_installments=4, current_installment=1, my_share="600.02")
    due = upcoming.installments_due([sofa], "2026-10", "all", "Household", SP)
    # July is 1 of 4, so October is the last: it takes the cents the others rounded off.
    assert list(due["text"]) == ["R$ 250 · 4 of 4"]
    assert list(due["amount"]) == [250.03]
    assert due["name"].iloc[0] == "Home › Furniture · 20/07"
    assert upcoming.installments_due([sofa], "2026-08", "all", "Household", SP)["amount"].tolist() == [250.0]
    assert upcoming.installments_due([sofa], "2026-11", "all", "Household", SP).empty   # paid off
    assert upcoming.installments_due([sofa], "2026-07", "all", "Household", SP).empty   # bought this month
    # Started at installment 3 of 4 in July: August is the last one.
    late = {**sofa, "current_installment": 3}
    assert upcoming.installments_due([late], "2026-09", "all", "Household", SP).empty
    assert upcoming.installments_due([sofa], "2026-10", "all", "My share", SP)["amount"].tolist() == [150.02]


def test_views_and_lenses():
    shared = bill(1, "2026-09-12T15:00:00+00:00", "180.00", my_share="108.00")
    personal = bill(2, "2026-09-03T15:00:00+00:00", "50.00", NET, is_shared=False)
    both = [shared, personal]
    assert set(upcoming.recurring_due(both, "2026-10", TODAY, "shared", "Household", SP)["name"]) == {
        "Housing › Electricity"}
    assert set(upcoming.recurring_due(both, "2026-10", TODAY, "personal", "My share", SP)["name"]) == {
        "Housing › Internet"}
    mine = upcoming.recurring_due(both, "2026-10", TODAY, "all", "My share", SP)
    assert dict(zip(mine["name"], mine["amount"])) == {"Housing › Electricity": 108.0, "Housing › Internet": 50.0}
    assert upcoming.recurring_due([], "2026-10", TODAY, "all", "Household", SP).empty
