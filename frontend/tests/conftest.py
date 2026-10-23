"""Sample /analytics/shared responses shared by the analytics tests."""
import html
import re

from analytics_shaping import shift_month


def row(month, primary, sub, cost_type, household, mine, count=1, household_to_day=None, mine_to_day=None):
    return {
        "month": month, "primary_category": primary, "sub_category": sub, "cost_type": cost_type,
        "household": household, "mine": mine, "count": count,
        "household_to_day": household if household_to_day is None else household_to_day,
        "mine_to_day": mine if mine_to_day is None else mine_to_day,
    }


def window(month="2026-10", n=12):
    return [shift_month(month, -k) for k in range(n - 1, -1, -1)]


def sample_payload(month="2026-10", is_partial=True, as_of_day=10):
    """
    Shared expenses over the four months up to `month` (default October 2026,
    in progress at day 10). Food rises against the previous month's first ten
    days; Housing is flat.
    """
    m3, m2, m1 = (shift_month(month, -k) for k in (3, 2, 1))
    return {
        "month": month, "months": window(month), "is_partial": is_partial, "as_of_day": as_of_day,
        "rows": [
            row(m3, "Housing", "Rent", "Fixed", "2000.00", "1200.00"),
            row(m3, "Food", "Groceries", "Variable", "300.00", "180.00", 3, "100.00", "60.00"),
            row(m2, "Housing", "Rent", "Fixed", "2000.00", "1200.00"),
            row(m2, "Food", "Groceries", "Variable", "600.00", "360.00", 4, "200.00", "120.00"),
            row(m1, "Housing", "Rent", "Fixed", "2000.00", "1200.00", 1, "2000.00", "1200.00"),
            row(m1, "Food", "Groceries", "Variable", "900.00", "540.00", 6, "150.00", "90.00"),
            row(m1, "Leisure", "Cinema", "Variable", "80.00", "48.00", 1, "0.00", "0.00"),
            row(month, "Housing", "Rent", "Fixed", "2000.00", "1200.00"),
            row(month, "Food", "Groceries", "Variable", "250.00", "150.00", 3),
            row(month, "Food", "Restaurants", "Variable", "120.00", "72.00", 2),
        ],
    }


def empty_payload(month="2026-10"):
    return {"month": month, "months": window(month), "is_partial": True, "as_of_day": 10, "rows": []}


def sample_expenses():
    return [
        {
            "expenditure_id": 7, "transaction_timestamp": "2026-10-08T15:00:00Z",
            "primary_category": "Food", "sub_category": "Restaurants", "cost_type": "Variable",
            "payment_method": "Credit card", "institution": "Nubank", "paid_by": "alice",
            "price": "120.00", "mine": "72.00", "share_pct": "0.6000",
            "current_installment": 1, "total_installments": 1, "nature": "Normal",
        },
        {
            "expenditure_id": 5, "transaction_timestamp": "2026-10-02T01:30:00Z",
            "primary_category": "Food", "sub_category": "Groceries", "cost_type": "Variable",
            "payment_method": "Pix", "institution": None, "paid_by": "bob",
            "price": "250.00", "mine": "150.00", "share_pct": "0.6000",
            "current_installment": 1, "total_installments": 1, "nature": "Normal",
        },
    ]


def kpi_cards(at) -> dict[str, dict]:
    """
    Every ui.kpi on the page by label: {"value": ..., "lines": [...]}. Labels
    are markdown (for their tooltip); the number and lines are one html block.
    """
    labels = [html.unescape(re.search(r'class="hf-(?:kpi|hero)-label">(.*?)</span>', m.value).group(1))
              for m in at.markdown if "hf-kpi-label" in m.value or "hf-hero-label" in m.value]
    blocks = [str(h.proto.body) for h in at.get("html") if "hf-kpi-value" in str(h.proto.body) and str(h.proto.body).startswith('<div class="hf-kpi')]
    cards = {}
    for label, block in zip(labels, blocks):
        value = re.search(r'class="hf-kpi-value">(.*?)</div>', block).group(1)
        lines = re.findall(r'class="hf-kpi-line[^"]*">(.*?)</div>', block)
        cards[label] = {"value": html.unescape(value), "lines": [html.unescape(x) for x in lines]}
    return cards
