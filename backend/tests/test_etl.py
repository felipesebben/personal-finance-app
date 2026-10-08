"""ETL extracts and Hyper generation. Nothing here talks to Tableau."""
from decimal import Decimal

import pandas as pd
import pantab
import pytest

import database
from conftest import expenditure_payload
from etl.main import extract_allocations, extract_data, generate_hyper_file


def spend(client, household, who, price, is_shared=True, when="2026-10-08T12:00:00-03:00"):
    resp = client.post("/expenditures/", headers=household[who], json=expenditure_payload(
        household, price=price, is_shared=is_shared, transaction_timestamp=when,
    ))
    assert resp.status_code == 200, resp.text


@pytest.fixture
def seeded(client, household):
    spend(client, household, "a", "100.01")                     # shared, 60/40
    spend(client, household, "b", "33.33")                      # shared, 60/40
    spend(client, household, "a", "20.00", is_shared=False)     # personal
    spend(client, household, "b", "50.00", when="2026-10-31T23:30:00-03:00")  # 1 Nov in UTC
    return household


def test_allocations_reconcile_to_expenditures(seeded):
    alloc = extract_allocations(database.engine)
    exps = extract_data(database.engine)

    # one row per bearer: 3 shared x 2 people + 1 personal
    assert len(alloc) == 7
    # every expense's shares add up to its price, to the cent
    per_expense = alloc.groupby("expenditure_id")["share_amount"].sum().round(2)
    prices = exps.set_index("expenditure_id")["price"]
    pd.testing.assert_series_equal(per_expense.sort_index(), prices.sort_index(), check_names=False)
    # and so does the whole dataset
    assert round(alloc["share_amount"].sum(), 2) == round(exps["price"].sum(), 2)


def test_allocations_carry_payer_and_bearer(seeded):
    alloc = extract_allocations(database.engine)
    first = alloc[alloc["expenditure_id"] == alloc["expenditure_id"].min()]
    assert list(first["borne_by"]) == ["alice", "bob"]
    assert set(first["paid_by"]) == {"alice"}
    assert list(first["share_amount"]) == [60.01, 40.00]
    assert set(first["split_source"]) == {"household_default"}

    personal = alloc[alloc["split_source"] == "not_shared"]
    assert len(personal) == 1
    assert personal.iloc[0]["borne_by"] == personal.iloc[0]["paid_by"] == "alice"


def test_month_start_uses_sao_paulo_time(seeded):
    alloc = extract_allocations(database.engine)
    assert set(pd.to_datetime(alloc["month_start"]).dt.strftime("%Y-%m")) == {"2026-10"}


def test_empty_database_extracts_nothing(client):
    assert extract_allocations(database.engine) is None


def test_allocations_hyper_round_trip(seeded, tmp_path):
    alloc = extract_allocations(database.engine)
    path = generate_hyper_file(alloc, filename="allocations.hyper", output_dir=str(tmp_path))
    assert path is not None

    back = pantab.frame_from_hyper(path, table="Expenditures")
    back = back.to_pandas() if hasattr(back, "to_pandas") else back
    assert len(back) == len(alloc)
    assert {"borne_by", "paid_by", "share_amount", "share_pct", "split_source", "month_start"} <= set(back.columns)
    assert round(float(back["share_amount"].sum()), 2) == round(float(alloc["share_amount"].sum()), 2)


def test_expenditures_hyper_handles_all_null_column(seeded, tmp_path):
    # The seeded payment method has no institution, so that column is all NULL.
    exps = extract_data(database.engine)
    assert exps["institution"].isna().all()
    path = generate_hyper_file(exps, output_dir=str(tmp_path))
    assert path is not None
