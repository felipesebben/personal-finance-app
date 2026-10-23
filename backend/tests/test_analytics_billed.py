"""basis=billed on the monthly analytics: an installment purchase counted per installment, in its billing month."""
from decimal import Decimal

from test_analytics import analytics, frozen_today, spend, total  # noqa: F401 (frozen_today: autouse fixture)
from test_personal_analytics import personal

D = Decimal


def by_month(rows, field):
    return {m: total(rows, field, m) for m in sorted({r["month"] for r in rows})}


def test_billed_spreads_a_purchase_over_its_installments(client, household):
    # R$ 100,00 in 3 installments, bought in August (installment 1 billed then): 33,33 + 33,33 + 33,34.
    spend(client, household, "a", "100.00", when="2026-08-05T12:00:00-03:00", total_installments=3,
          current_installment=1)
    billed = analytics(client, household["a"], month="2026-10", months=3, basis="billed")["rows"]
    assert by_month(billed, "household") == {"2026-08": D("33.33"), "2026-09": D("33.33"), "2026-10": D("33.34")}
    assert by_month(billed, "mine") == {"2026-08": D("20.00"), "2026-09": D("20.00"), "2026-10": D("20.00")}
    assert {r["count"] for r in billed} == {1}
    # The default counts it in full when bought.
    bought = analytics(client, household["a"], month="2026-10", months=3)["rows"]
    assert by_month(bought, "household") == {"2026-08": D("100.00")}


def test_a_purchase_logged_mid_way_bills_its_earlier_installments_before(client, household):
    # Logged in September as installment 2 of 3: installment 1 was August's, 3 is October's.
    spend(client, household, "a", "90.00", when="2026-09-20T12:00:00-03:00", total_installments=3,
          current_installment=2)
    billed = analytics(client, household["a"], month="2026-10", months=3, basis="billed")["rows"]
    assert by_month(billed, "household") == {"2026-08": D("30.00"), "2026-09": D("30.00"), "2026-10": D("30.00")}
    # By the 10th of October (today in these tests), the September part, billed on the 20th, isn't counted yet.
    assert total(billed, "household_to_day", "2026-09") == D("0.00")


def test_billed_works_for_personal_expenses_too(client, household):
    spend(client, household, "a", "50.00", is_shared=False, when="2026-09-03T12:00:00-03:00",
          total_installments=2, current_installment=1)
    billed = personal(client, household["a"], month="2026-10", months=2, basis="billed")["rows"]
    assert by_month(billed, "household") == {"2026-09": D("25.00"), "2026-10": D("25.00")}
    assert client.get("/analytics/personal", headers=household["a"],
                      params={"basis": "someday"}).status_code == 422
