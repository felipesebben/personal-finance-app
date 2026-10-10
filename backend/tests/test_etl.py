"""ETL extracts and Hyper generation. Nothing here talks to Tableau."""
from decimal import Decimal

import pandas as pd
import pantab
import pytest
from tableauhyperapi import Connection, HyperProcess, TableName, Telemetry

import database
from conftest import expenditure_payload
from etl.main import extract_allocations, extract_cashflow, extract_data, extract_settlements, generate_hyper_file


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


# --- settlements ----------------------------------------------------------

def record(client, household, amount, month, when="2026-11-03T09:00:00-03:00", note=None):
    body = {
        "settled_at": when, "from_user_id": household["b_id"], "to_user_id": household["a_id"],
        "amount": amount, "month": month, "note": note,
    }
    resp = client.post("/settlements/", headers=household["b"], json=body)
    assert resp.status_code == 200, resp.text


def test_settlements_extract_matches_the_table(client, household):
    record(client, household, "40.00", "2026-10", note="Pix")
    record(client, household, "15.50", None, when="2026-11-30T23:30:00-03:00")
    df = extract_settlements(database.engine)

    assert len(df) == 2
    assert round(df["amount"].sum(), 2) == 55.50
    first, second = df.iloc[0], df.iloc[1]
    assert (first["from_name"], first["to_name"], first["recorded_by"]) == ("bob", "alice", "bob")
    assert first["period_month"].strftime("%Y-%m") == "2026-10"
    assert first["settled_month_start"].strftime("%Y-%m") == "2026-11"
    assert pd.isna(second["period_month"])
    # 23:30 on 30 Nov in São Paulo is 1 Dec in UTC; still November locally
    assert second["settled_month_start"].strftime("%Y-%m") == "2026-11"


def test_no_settlements_extracts_nothing(client):
    assert extract_settlements(database.engine) is None


def test_settlements_hyper_keeps_dates_when_no_month_is_set(client, household, tmp_path):
    # Every period_month NULL must still publish as a date, not text, so the
    # column's type in Tableau doesn't flip once a month is recorded.
    record(client, household, "40.00", None)
    df = extract_settlements(database.engine)
    path = generate_hyper_file(df, filename="settlements.hyper", output_dir=str(tmp_path))
    assert path is not None

    # Check the column type stored in the Hyper file itself — what Tableau sees.
    # log_dir keeps hyperd.log out of the working directory.
    hyper_params = {"log_dir": str(tmp_path)}
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters=hyper_params) as hyper:
        with Connection(hyper.endpoint, path) as conn:
            table = conn.catalog.get_table_definition(TableName("Expenditures"))
            types = {col.name.unescaped: str(col.type) for col in table.columns}
            assert conn.execute_scalar_query('SELECT COUNT(*) FROM "Expenditures"') == 1
    assert types["period_month"] == "TIMESTAMP"
    assert types["settled_month_start"] == "TIMESTAMP"
    assert types["note"] == "TEXT"


def test_is_shared_column_is_derived_from_split_rows(seeded):
    # seeded: three shared expenses and one personal one
    exps = extract_data(database.engine)
    assert sorted(exps["is_shared"].tolist()) == [False, True, True, True]
    alloc = extract_allocations(database.engine)
    assert set(alloc.loc[alloc["split_source"] == "not_shared", "is_shared"]) == {False}
    assert set(alloc.loc[alloc["split_source"] == "household_default", "is_shared"]) == {True}


# --- cashflow: installments spread over billing months ----------------------

def spend_in_installments(client, household, price, total, current=1, who="a", is_shared=True,
                          when="2026-10-08T12:00:00-03:00"):
    resp = client.post("/expenditures/", headers=household[who], json=expenditure_payload(
        household, price=price, is_shared=is_shared, transaction_timestamp=when,
        current_installment=current, total_installments=total,
    ))
    assert resp.status_code == 200, resp.text


def months(series):
    return list(series.dt.strftime("%Y-%m"))


def test_installments_spread_each_share_over_the_billing_months(client, household):
    spend_in_installments(client, household, "100.00", total=3)   # shared 60/40
    df = extract_cashflow(database.engine)

    alice = df[df["borne_by"] == "alice"]
    bob = df[df["borne_by"] == "bob"]
    assert months(alice["billing_month"]) == ["2026-10", "2026-11", "2026-12"]
    assert list(alice["amount"]) == [20.00, 20.00, 20.00]
    # 40.00 / 3: the first two round down, the last takes the remainder
    assert list(bob["amount"]) == [13.33, 13.33, 13.34]
    assert list(bob["installment_number"]) == [1, 2, 3]
    assert set(months(df["purchase_month"])) == {"2026-10"}
    assert round(df["amount"].sum(), 2) == 100.00


def test_current_installment_anchors_the_schedule(client, household):
    # Entered in October while paying installment 2 of 3: it started in September.
    spend_in_installments(client, household, "90.00", total=3, current=2, is_shared=False)
    df = extract_cashflow(database.engine)
    assert months(df["billing_month"]) == ["2026-09", "2026-10", "2026-11"]
    assert list(df["amount"]) == [30.00, 30.00, 30.00]


def test_cashflow_reconciles_to_expenditures(seeded, client):
    spend_in_installments(client, seeded, "1234.57", total=10)
    flow = extract_cashflow(database.engine)
    exps = extract_data(database.engine)
    per_expense = flow.groupby("expenditure_id")["amount"].sum().round(2)
    prices = exps.set_index("expenditure_id")["price"]
    pd.testing.assert_series_equal(per_expense.sort_index(), prices.sort_index(), check_names=False)
    # Expenses without installments are a single row in their own month.
    single = flow[flow["total_installments"] == 1]
    assert (single["billing_month"] == single["purchase_month"]).all()


def test_tiny_installments_never_go_negative(client, household):
    spend_in_installments(client, household, "0.05", total=10, is_shared=False)
    df = extract_cashflow(database.engine)
    assert (df["amount"] >= 0).all()
    assert round(df["amount"].sum(), 2) == 0.05


def test_cashflow_hyper_keeps_month_columns_as_dates(client, household, tmp_path):
    spend_in_installments(client, household, "100.00", total=2)
    path = generate_hyper_file(extract_cashflow(database.engine), filename="cashflow.hyper", output_dir=str(tmp_path))
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_dir": str(tmp_path)}) as hyper:
        with Connection(hyper.endpoint, path) as conn:
            table = conn.catalog.get_table_definition(TableName("Expenditures"))
            types = {col.name.unescaped: str(col.type) for col in table.columns}
            assert conn.execute_scalar_query('SELECT COUNT(*) FROM "Expenditures"') == 4
    assert types["billing_month"] == "TIMESTAMP"
    assert types["purchase_month"] == "TIMESTAMP"
