"""joint_shaping: the Joint account tab's chart frame and sentences."""
from zoneinfo import ZoneInfo

from analytics_charts import joint_pace_chart
from joint_shaping import (
    THIS_MONTH, USUAL, counted_from_text, ordinal, pace_frame, pace_gap, pace_sentence, run_out_text,
)

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def status(**over):
    base = {
        "payment_method_id": 15, "label": "Debit · Nubank Conjunta",
        "balance": "500.00", "counted_from": "2026-12-01T11:00:00Z",
        "deposits_since": "0.00", "spent_since": "500.00",
        "month": "2026-12", "as_of_day": 3, "days_in_month": 31,
        "spent_to_day": "500.00", "usual_to_day": "400.00", "usual_month_total": "450.00",
        "history_months": 2, "runs_out_on": "2026-12-20",
        "days": [
            {"day": 1, "this_month": "0", "usual": "100.00"},
            {"day": 2, "this_month": "200.00", "usual": "300.00"},
            {"day": 3, "this_month": "500.00", "usual": "400.00"},
            {"day": 4, "this_month": None, "usual": "450.00"},
        ],
    }
    return {**base, **over}


def test_ordinals():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 31)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "31st",
    ]


def test_frame_stops_this_month_at_today_and_keeps_the_usual_line():
    df = pace_frame(status())
    assert list(df[df["series"] == THIS_MONTH]["day"]) == [1, 2, 3]
    assert list(df[df["series"] == USUAL]["day"]) == [1, 2, 3, 4]
    assert df["amount_brl"].iloc[-1] == "R$ 450,00"
    joint_pace_chart(df, THIS_MONTH, USUAL, 31).to_dict()  # the spec builds


def test_frame_without_history_has_only_this_month():
    df = pace_frame(status(days=[{"day": 1, "this_month": "10.00", "usual": None}]))
    assert set(df["series"]) == {THIS_MONTH}


def test_pace_sentences_use_arrows_and_say_when_history_is_missing():
    assert pace_gap(status()) == 100
    assert pace_sentence(status()) == "By the 3rd you've spent R$ 500,00, ▲ R$ 100,00 more than usual by now (R$ 400,00)."
    assert "▼ R$ 100,00 less" in pace_sentence(status(spent_to_day="300.00"))
    assert "right on the usual pace" in pace_sentence(status(spent_to_day="400.00"))
    no_history = status(usual_to_day=None)
    assert pace_gap(no_history) is None
    assert "Not enough history yet" in pace_sentence(no_history)


def test_run_out_text():
    assert run_out_text(status()) == "At this pace the money lasts until 20 December."
    assert run_out_text(status(runs_out_on="2027-01-04")) == "At this pace the money lasts past the end of the month."
    assert run_out_text(status(balance="0.00", runs_out_on="2026-12-03")) == "The account is empty."
    assert "Nothing spent yet" in run_out_text(status(runs_out_on=None))
    assert run_out_text(status(balance=None)) is None


def test_counted_from_text():
    assert counted_from_text(status(), SAO_PAULO).startswith("From the balance you entered on 01/12/2026")
    assert counted_from_text(status(counted_from=None), SAO_PAULO).startswith("From your first deposit")
    assert counted_from_text(status(balance=None), SAO_PAULO) == "Enter the balance your bank shows to start."
