"""The seed script writes history that obeys the same rules as real data."""
import random
from datetime import date

import pytest
from sqlalchemy import text

import database
from seed import SeedRefused, months_ending, seed

TODAY = date(2026, 10, 10)


def run_seed(months=4, random_seed=1, **kwargs):
    with database.SessionLocal() as db:
        return seed(db, months=months, rng=random.Random(random_seed), today=TODAY, **kwargs)


def scalar_rows(sql):
    with database.engine.connect() as conn:
        return conn.execute(text(sql)).all()


def test_months_ending_crosses_the_year():
    assert months_ending(date(2026, 2, 14), 3) == [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)]


def test_every_seeded_expense_reconciles_to_its_price(client, household):
    counts = run_seed()
    assert counts["shared"] > 0 and counts["personal"] > 0

    mismatched = scalar_rows("""
        SELECT f.expenditure_id
        FROM fact_expenditures f JOIN fact_expenditure_split s USING (expenditure_id)
        GROUP BY f.expenditure_id, f.price
        HAVING SUM(s.share_amount) <> f.price
    """)
    assert mismatched == []
    # Shared ones carry the household's 60/40 ratio; personal ones a single 100% row.
    sources = dict(scalar_rows("SELECT split_source, COUNT(*) FROM fact_expenditure_split GROUP BY split_source"))
    assert sources["household_default"] == 2 * counts["shared"]
    assert sources["not_shared"] == counts["personal"]


def test_seed_covers_the_window_and_nothing_after_today(client, household):
    run_seed(months=4)
    months = [r[0] for r in scalar_rows("""
        SELECT DISTINCT to_char(transaction_timestamp AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM')
        FROM fact_expenditures ORDER BY 1
    """)]
    assert months == ["2026-07", "2026-08", "2026-09", "2026-10"]
    latest = scalar_rows("SELECT MAX((transaction_timestamp AT TIME ZONE 'America/Sao_Paulo')::date) FROM fact_expenditures")
    assert latest[0][0] <= TODAY


def test_finished_months_are_settled_and_the_current_one_is_not(client, household):
    counts = run_seed(months=4)
    assert counts["settlements"] == 3  # Jul, Aug, Sep; October is still running

    for month in ("2026-07", "2026-08", "2026-09"):
        report = client.get(f"/balances/?month={month}", headers=household["a"]).json()
        assert report["transfers"] == [], month
        assert all(m["net"] == "0.00" for m in report["members"]), month

    october = client.get("/balances/?month=2026-10", headers=household["a"]).json()
    all_time = client.get("/balances/", headers=household["a"]).json()
    # Everything still owed is October's.
    assert all_time["transfers"] == october["transfers"]


def test_seed_reuses_existing_dimensions(client, household):
    # The household fixture already created Food > Groceries; seeding must not fail on its unique constraint.
    run_seed()
    rows = scalar_rows("SELECT COUNT(*) FROM dim_category WHERE primary_category = 'Food' AND sub_category = 'Groceries'")
    assert rows[0][0] == 1


def test_seed_refuses_to_double_up_unless_appending(client, household):
    first = run_seed()
    with pytest.raises(SeedRefused, match="--append"):
        run_seed()
    second = run_seed(append=True, random_seed=2)
    total = scalar_rows("SELECT COUNT(*) FROM fact_expenditures")[0][0]
    assert total == first["expenditures"] + second["expenditures"]


def test_seed_refuses_without_a_household(client):
    with pytest.raises(SeedRefused, match="Household split ratio"):
        run_seed()
    assert scalar_rows("SELECT COUNT(*) FROM fact_expenditures")[0][0] == 0
