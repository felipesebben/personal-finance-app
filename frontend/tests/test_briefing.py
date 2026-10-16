"""briefing: the login summary's sentences, from sample API payloads."""
from analytics_shaping import to_frame
from briefing import joint_lines, settle_line, spending_line
from conftest import row, sample_payload


def line(payload, label="Shared", lens="Household", **kw):
    return spending_line(label, to_frame(payload), payload, lens, **kw)


def test_shared_against_the_usual_same_days():
    # October to day 10: 2.370. Jul/Aug/Sep days 1-10: 2.100, 2.200, 2.150 -> usual 2.150.
    assert line(sample_payload(), top_category=True) == (
        "Shared: R$ 2.370,00 so far in October, ▲ R$ 220,00 more than usual by the 10th. Biggest: Housing."
    )


def test_my_share_uses_the_mine_column():
    # 1.422 against (1.260 + 1.320 + 1.290) / 3 = 1.290.
    assert line(sample_payload(), label="Yours", lens="My share") == (
        "Yours: R$ 1.422,00 so far in October, ▲ R$ 132,00 more than usual by the 10th."
    )


def test_less_than_usual_points_down():
    payload = sample_payload()
    payload["rows"] = [r for r in payload["rows"] if not (r["month"] == "2026-10" and r["primary_category"] == "Housing")]
    assert "▼ R$ 1.780,00 less than usual by the 10th" in line(payload)


def test_without_three_months_it_compares_with_last_month():
    payload = sample_payload()
    payload["rows"] = [r for r in payload["rows"] if r["month"] in ("2026-09", "2026-10")]
    # September days 1-10: 2.150.
    assert line(payload) == "Shared: R$ 2.370,00 so far in October, ▲ R$ 220,00 more than September by the 10th."


def test_first_month_makes_no_comparison():
    payload = sample_payload()
    payload["rows"] = [r for r in payload["rows"] if r["month"] == "2026-10"]
    assert line(payload) == "Shared: R$ 2.370,00 so far in October."


def test_a_finished_month_says_in_not_so_far():
    payload = sample_payload(is_partial=False, as_of_day=31)
    assert line(payload).startswith("Shared: R$ 2.370,00 in October, ")
    assert "by the" not in line(payload)


def test_nothing_at_all_is_left_out():
    payload = sample_payload()
    payload["rows"] = []
    assert line(payload) is None


def test_settle_up_from_my_point_of_view():
    owed = {"transfers": [{"from_user_id": 2, "from_name": "Lívia", "to_user_id": 1, "to_name": "Felipe", "amount": "120.00"}]}
    assert settle_line(owed, 1, "October") == "Settle up: Lívia owes you R$ 120,00 for October."
    assert settle_line(owed, 2, "October") == "Settle up: You owe Felipe R$ 120,00 for October."
    assert settle_line({"transfers": []}, 1, "October") == "Settle up: all square for October."
    assert settle_line([], 1, "October") is None


def test_joint_account_line_only_with_a_known_balance():
    status = {"label": "Debit · Nubank", "balance": "1150.00", "runs_out_on": "2026-10-28", "month": "2026-10"}
    assert joint_lines([status]) == ["Joint account: R$ 1.150,00 left. At this pace the money lasts until 28 October."]
    two = joint_lines([status, dict(status, label="Pix · Inter", runs_out_on="2026-11-02")])
    assert two[1] == "Joint account (Pix · Inter): R$ 1.150,00 left. At this pace the money lasts past the end of the month."
    assert joint_lines([dict(status, balance=None)]) == []
    assert joint_lines(None) == []


def test_shared_and_personal_rows_add_up_for_yours():
    payload = sample_payload()
    payload["rows"] = [r for r in payload["rows"] if r["month"] == "2026-10"] + [
        row("2026-10", "Health", "Pharmacy", "Variable", "30.00", "30.00"),
    ]
    assert line(payload, label="Yours", lens="My share") == "Yours: R$ 1.452,00 so far in October."
