"""entries.py: the Entries page's table, filters, edit trace and the edit form's starting values."""
import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import entries

SP = ZoneInfo("America/Sao_Paulo")
ME = {"user_id": 1, "full_name": "Me", "email": "me@example.com"}
HER = {"user_id": 2, "full_name": "Her", "email": "her@example.com"}
FOOD = {"primary_category": "Food", "sub_category": "Groceries", "for_pets": False}
VET = {"primary_category": "Pets", "sub_category": "Vet", "for_pets": True}
NUBANK = {"method_name": "Credit Card", "institution": "Nubank"}
PIX = {"method_name": "Pix", "institution": None}


def expense(eid=1, when="2026-10-05T15:30:00+00:00", price="100.00", **extra):
    return {"expenditure_id": eid, "transaction_timestamp": when, "price": price, "nature": "Normal",
            "is_shared": True, "my_share": "60.00", "is_treat": False, "total_installments": 1,
            "current_installment": 1, "user": ME, "category": FOOD, "payment_method": NUBANK, "pet": None,
            "splits": [{"user_id": 1, "share_pct": "0.6000", "share_amount": "60.00",
                        "split_source": "household_default"},
                       {"user_id": 2, "share_pct": "0.4000", "share_amount": "40.00",
                        "split_source": "household_default"}],
            "updated_at": None, "updated_by": None, **extra}


def test_the_table_reads_newest_first_in_sao_paulo_time():
    df = entries.entries_frame([expense(1), expense(2, when="2026-10-01T01:00:00+00:00", payment_method=PIX)], SP)
    assert list(df["id"]) == [1, 2]
    assert list(df["When"]) == ["05/10/2026 12:30", "30/09/2026 22:00"]  # the 2nd is still September in São Paulo
    assert list(df["month"]) == ["2026-10", "2026-09"]
    assert list(df["Paid with"]) == ["Credit Card · Nubank", "Pix"]
    assert list(df["Price"]) == ["R$ 100,00", "R$ 100,00"]


def test_types_pets_and_the_last_edit():
    e = expense(category=VET, pet={"pet_id": 7, "name": "Thor"}, total_installments=10, is_treat=True,
                updated_at="2026-10-18T17:02:00+00:00", updated_by=HER)
    [row] = entries.entries_frame([e], SP).to_dict("records")
    assert row["What"] == "Pets · Vet · Thor"
    assert row["Type"] == "Shared · treat · 10x"
    assert row["Last edit"] == "Her · 18/10 14:02"
    assert entries.what_text(expense(category=VET)) == "Pets · Vet · Both"
    assert entries.entries_frame([expense()], SP).loc[0, "Last edit"] == ""


def test_the_trace_in_words():
    assert entries.trace_text(expense(), SP) == "Logged by Me. Never edited."
    edited = expense(updated_at="2026-10-18T17:02:00+00:00", updated_by=HER)
    assert entries.trace_text(edited, SP) == "Logged by Me. Last edited by Her on 18 October at 14:02."
    gone = expense(updated_at="2026-10-18T17:02:00+00:00", updated_by=None)
    assert "an account since deleted" in entries.trace_text(gone, SP)


def test_filters_combine():
    df = entries.entries_frame([
        expense(1),
        expense(2, when="2026-10-04T15:30:00+00:00", is_shared=False, user=HER, payment_method=PIX,
                price="45.90"),
        expense(3, when="2026-09-05T15:30:00+00:00", category=VET),
    ], SP)
    assert list(entries.filter_entries(df, month="2026-10")["id"]) == [1, 2]
    assert list(entries.filter_entries(df, kind="personal")["id"]) == [2]
    assert list(entries.filter_entries(df, logged_by="Her")["id"]) == [2]
    assert list(entries.filter_entries(df, categories=["Pets"])["id"]) == [3]
    assert list(entries.filter_entries(df, search="45,90")["id"]) == [2]
    assert list(entries.filter_entries(df, search="nubank")["id"]) == [1, 3]
    assert entries.filter_entries(df, month="2026-10", categories=["Pets"]).empty


def test_summary():
    df = entries.entries_frame([expense(1), expense(2)], SP)
    assert entries.summary(df) == "2 expenses · R$ 200,00 · your part R$ 120,00"


def test_form_values_for_an_edit():
    e = expense(price="1234.56", total_installments=10, current_installment=4, nature="Annual")
    v = entries.form_values(e, pets=[], tz=SP, names={1: "Me", 2: "Her"})
    assert v["price_text"] == "1.234,56"
    assert (v["method"], v["institution"]) == ("Credit Card", "Nubank")
    assert (v["total_installments"], v["current_installment"]) == (10, 4)
    assert (v["primary"], v["sub"], v["nature"]) == ("Food", "Groceries", "Annual")
    assert v["shared"] and v["custom"] is None
    assert v["split"] == [(1, Decimal("0.6000")), (2, Decimal("0.4000"))]
    assert v["split_text"] == "Me 60% · Her 40%"
    assert (v["date"], v["time"]) == (datetime.date(2026, 10, 5), datetime.time(12, 30))


def test_form_values_manual_split_pet_and_no_institution():
    manual = [{"user_id": 1, "share_pct": "0.3000", "share_amount": "30.00", "split_source": "manual"},
              {"user_id": 2, "share_pct": "0.7000", "share_amount": "70.00", "split_source": "manual"}]
    two_pets = [{"pet_id": 7, "name": "Thor"}, {"pet_id": 8, "name": "Luna"}]
    v = entries.form_values(expense(splits=manual, category=VET, payment_method=PIX), two_pets, SP)
    assert v["custom"] == {1: 30, 2: 70}
    assert v["pet"] == entries.ALL_PETS  # no pet_id on a pet category: all of them
    assert v["institution"] == entries.NO_INSTITUTION
    # With one pet the form doesn't ask.
    assert entries.form_values(expense(category=VET), two_pets[:1], SP)["pet"] is None
