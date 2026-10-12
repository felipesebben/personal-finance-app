"""What's left in a joint account, this month's pace, and the joint_account datasource."""
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

import database
import main
from conftest import expenditure_payload, signup_and_login
from etl.main import extract_joint_entries

D = Decimal
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


class FrozenDatetime(datetime):
    """Today is 10 Dec 2026 in São Paulo."""
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 12, 10, 12, 0, tzinfo=SAO_PAULO).astimezone(tz)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(main, "datetime", FrozenDatetime)


@pytest.fixture
def pot(client, household):
    joint_id = client.post("/payment_methods/", headers=household["a"], json={
        "method_name": "Debit", "institution": "Nubank Conjunta", "is_joint": True,
    }).json()["payment_method_id"]
    return {**household, "joint_id": joint_id}


def spend(client, h, price, when, joint=True):
    extra = {"payment_method_id": h["joint_id"]} if joint else {}
    resp = client.post("/expenditures/", headers=h["a"], json=expenditure_payload(
        h, price=price, transaction_timestamp=when, **extra))
    assert resp.status_code == 200, resp.text


def entry(client, h, kind, amount, when, who="a"):
    return client.post("/joint/entries", headers=h[who], json={
        "payment_method_id": h["joint_id"], "kind": kind, "amount": amount, "entry_at": when,
    })


def status(client, h, who="a"):
    resp = client.get("/joint/status", headers=h[who])
    assert resp.status_code == 200, resp.text
    [s] = resp.json()
    return s


def test_balance_unknown_until_something_is_recorded(client, pot):
    spend(client, pot, "100.00", "2026-12-02T10:00:00-03:00")
    s = status(client, pot)
    assert s["label"] == "Debit · Nubank Conjunta"
    assert s["balance"] is None and s["runs_out_on"] is None
    assert D(s["spent_to_day"]) == D("100.00")


def test_left_is_latest_balance_plus_deposits_minus_spending_since(client, pot):
    spend(client, pot, "999.00", "2026-11-20T10:00:00-03:00")               # before the check: ignored
    assert entry(client, pot, "balance", "300.00", "2026-12-01T09:00:00-03:00").status_code == 200
    entry(client, pot, "deposit", "1000.00", "2026-12-01T10:00:00-03:00")
    spend(client, pot, "250.00", "2026-12-03T10:00:00-03:00")
    spend(client, pot, "80.00", "2026-12-04T10:00:00-03:00", joint=False)   # another card: ignored
    s = status(client, pot)
    assert D(s["balance"]) == D("1050.00")
    assert (D(s["deposits_since"]), D(s["spent_since"])) == (D("1000.00"), D("250.00"))
    assert s["counted_from"].startswith("2026-12-01T12:00:00")  # 09:00 São Paulo, in UTC


def test_a_new_balance_check_resets_the_count(client, pot):
    entry(client, pot, "deposit", "1000.00", "2026-12-01T10:00:00-03:00")
    spend(client, pot, "250.00", "2026-12-03T10:00:00-03:00")
    entry(client, pot, "balance", "700.00", "2026-12-05T10:00:00-03:00")  # an unlogged R$ 50 somewhere
    spend(client, pot, "100.00", "2026-12-06T10:00:00-03:00")
    assert D(status(client, pot)["balance"]) == D("600.00")


def test_without_a_check_counting_starts_at_the_first_deposit(client, pot):
    spend(client, pot, "40.00", "2026-11-30T10:00:00-03:00")  # before any deposit
    entry(client, pot, "deposit", "500.00", "2026-12-01T10:00:00-03:00")
    spend(client, pot, "100.00", "2026-12-02T10:00:00-03:00")
    assert D(status(client, pot)["balance"]) == D("400.00")


def test_pace_against_the_usual_month_and_run_out(client, pot):
    # Tracked since 1 Oct: October and November are full months.
    spend(client, pot, "300.00", "2026-10-01T10:00:00-03:00")
    spend(client, pot, "500.00", "2026-11-05T10:00:00-03:00")
    spend(client, pot, "100.00", "2026-11-20T10:00:00-03:00")
    entry(client, pot, "balance", "1000.00", "2026-12-01T08:00:00-03:00")
    spend(client, pot, "500.00", "2026-12-04T10:00:00-03:00")

    s = status(client, pot)
    assert (s["month"], s["as_of_day"], s["days_in_month"], s["history_months"]) == ("2026-12", 10, 31, 2)
    assert D(s["spent_to_day"]) == D("500.00")
    assert D(s["usual_to_day"]) == D("400.00")         # by day 10: (300 + 500) / 2
    assert D(s["usual_month_total"]) == D("450.00")    # (300 + 600) / 2
    # R$ 500 in 10 days = R$ 50/day; R$ 500 left lasts 10 more days.
    assert s["runs_out_on"] == "2026-12-20"

    days = {d["day"]: d for d in s["days"]}
    assert len(days) == 31
    assert D(days[4]["this_month"]) == D("500.00") and D(days[3]["this_month"]) == D("0")
    assert days[11]["this_month"] is None              # the future
    assert D(days[31]["usual"]) == D("450.00")


def test_not_enough_history_without_a_full_month(client, pot):
    spend(client, pot, "300.00", "2026-11-11T10:00:00-03:00")  # tracking began mid-November
    spend(client, pot, "50.00", "2026-12-02T10:00:00-03:00")
    s = status(client, pot)
    assert s["history_months"] == 0
    assert s["usual_to_day"] is None and all(d["usual"] is None for d in s["days"])


def test_only_joint_methods_are_listed(client, household):
    assert client.get("/joint/status", headers=household["a"]).json() == []


def test_entries_need_a_joint_method(client, pot):
    resp = client.post("/joint/entries", headers=pot["a"], json={
        "payment_method_id": pot["payment_method_id"], "kind": "deposit", "amount": "10.00",
        "entry_at": "2026-12-01T10:00:00-03:00",
    })
    assert resp.status_code == 400
    assert "Tick Joint in Settings" in resp.json()["detail"]


def test_a_deposit_must_be_positive_but_a_balance_can_be_zero(client, pot):
    assert entry(client, pot, "deposit", "0", "2026-12-01T10:00:00-03:00").status_code == 422
    assert entry(client, pot, "deposit", "-5", "2026-12-01T10:00:00-03:00").status_code == 422
    assert entry(client, pot, "balance", "0", "2026-12-01T10:00:00-03:00").status_code == 200


def test_both_members_list_and_delete_entries(client, pot):
    first = entry(client, pot, "deposit", "100.00", "2026-12-01T10:00:00-03:00").json()
    entry(client, pot, "deposit", "200.00", "2026-12-02T10:00:00-03:00", who="b")
    listed = client.get("/joint/entries", headers=pot["b"], params={"payment_method_id": pot["joint_id"]}).json()
    assert [D(e["amount"]) for e in listed] == [D("200.00"), D("100.00")]  # newest first

    assert client.delete(f"/joint/entries/{first['joint_entry_id']}", headers=pot["b"]).status_code == 200
    assert client.delete(f"/joint/entries/{first['joint_entry_id']}", headers=pot["b"]).status_code == 404
    assert D(status(client, pot)["balance"]) == D("200.00")


def test_outsiders_cant_see_or_change_the_pot(client, pot):
    _, outsider = signup_and_login(client, "eve")
    assert client.get("/joint/status", headers=outsider).status_code == 403
    assert client.get("/joint/entries", headers=outsider).status_code == 403
    assert entry(client, {**pot, "eve": outsider}, "deposit", "10.00", "2026-12-01T10:00:00-03:00", who="eve").status_code == 403


def test_etl_publishes_entries_with_sao_paulo_dates(client, pot):
    assert extract_joint_entries(database.engine) is None  # nothing yet: skipped, not published empty
    entry(client, pot, "balance", "300.00", "2026-11-30T23:30:00-03:00")  # already 1 Dec in UTC
    entry(client, pot, "deposit", "1000.00", "2026-12-01T10:00:00-03:00")
    df = extract_joint_entries(database.engine)
    assert list(df["kind"]) == ["balance", "deposit"]
    assert str(df["entry_date"].iloc[0].date()) == "2026-11-30"
    assert str(df["month_start"].dtype).startswith("datetime64")
    assert set(df["institution"]) == {"Nubank Conjunta"}
