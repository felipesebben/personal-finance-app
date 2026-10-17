"""entry_checks: the duplicate warning's sentences and the backfill line."""
from zoneinfo import ZoneInfo

from entry_checks import backfill_lines, duplicate_lines

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def test_duplicate_lines_say_who_logged_it():
    lines = duplicate_lines([
        {"logged_by": "Me", "logged_by_me": True, "transaction_timestamp": "2026-09-05T15:30:00+00:00",
         "price": "85.00", "category": "Food › Eating Out", "payment_method": "Pix · Nubank"},
        {"logged_by": "Lívia", "logged_by_me": False, "transaction_timestamp": "2026-09-06T02:30:00+00:00",
         "price": "85.00", "category": "Food › Eating Out", "payment_method": "Credit Card · Itaú"},
    ], SAO_PAULO)
    assert lines == [
        "You already logged this on 05/09/2026: R$ 85,00 · Food › Eating Out · Pix · Nubank.",
        # 02:30 UTC on the 6th is still the 5th in São Paulo.
        "Lívia already logged a matching shared expense on 05/09/2026: R$ 85,00 · Food › Eating Out · Credit Card · Itaú.",
    ]


def expense(when, price, user_id, shared, primary="Food", sub="Groceries", name=None):
    return {"transaction_timestamp": when, "price": price, "is_shared": shared,
            "user": {"user_id": user_id, "full_name": name or ("Me" if user_id == 1 else "Lívia")},
            "category": {"primary_category": primary, "sub_category": sub}}


def test_shared_names_who_logged_and_personal_is_only_mine():
    expenses = [
        expense("2026-10-02T12:00:00+00:00", "40.00", 2, True),                        # Lívia, shared: latest
        expense("2026-08-03T12:00:00+00:00", "450.00", 1, True, "Housing", "Cleaning"),  # me, shared: earliest
        expense("2026-08-20T12:00:00+00:00", "12.50", 1, True),
        expense("2026-09-10T12:00:00+00:00", "30.00", 1, False, "Health", "Pharmacy"),  # mine, personal
        expense("2026-09-25T12:00:00+00:00", "99.00", 1, False),                       # mine, personal
    ]
    assert backfill_lines(expenses, 1, SAO_PAULO) == [
        "Shared: earliest 3 August 2026 (R$ 450,00 · Housing › Cleaning · logged by you), "
        "latest 2 October 2026 (R$ 40,00 · Food › Groceries · logged by Lívia). By month: Aug 2026 2 · Oct 2026 1.",
        "Personal: earliest 10 September 2026 (R$ 30,00 · Health › Pharmacy), "
        "latest 25 September 2026 (R$ 99,00 · Food › Groceries). By month: Sep 2026 2.",
    ]


def test_a_single_expense_is_said_once():
    assert backfill_lines([expense("2026-08-03T12:00:00+00:00", "85.00", 2, True)], 1, SAO_PAULO) == [
        "Shared: one so far, 3 August 2026 (R$ 85,00 · Food › Groceries · logged by Lívia).",
    ]


def test_nothing_logged_says_nothing():
    assert backfill_lines([], 1, SAO_PAULO) == []
    # Someone else's personal expense (never sent by the API anyway) isn't mine to show.
    assert backfill_lines([expense("2026-08-03T12:00:00+00:00", "85.00", 2, False)], 1, SAO_PAULO) == []
