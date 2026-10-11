"""The calendar datasource: every day, no gaps, covering expenses and future installments."""
import datetime

import pandas as pd
from tableauhyperapi import Connection, HyperProcess, TableName, Telemetry

import database
from conftest import expenditure_payload
from etl.main import extract_allocations, extract_calendar, extract_cashflow, extract_data, generate_hyper_file


def spend(client, household, when, **extra):
    resp = client.post("/expenditures/", headers=household["a"], json=expenditure_payload(
        household, transaction_timestamp=when, **extra,
    ))
    assert resp.status_code == 200, resp.text


def test_empty_database_still_gets_this_year(client):
    cal = extract_calendar(database.engine)
    this_year = datetime.date.today().year  # São Paulo could differ only on New Year's Eve
    assert cal["date"].min().year in (this_year, this_year - 1)
    assert cal["date"].max() == pd.Timestamp(cal["date"].max().year, 12, 31)


def test_one_row_per_day_with_no_gaps_from_the_first_expense_year(client, household):
    spend(client, household, "2025-03-15T10:00:00-03:00")
    cal = extract_calendar(database.engine)

    assert cal["date"].min() == pd.Timestamp(2025, 1, 1)
    assert cal["date"].is_unique
    assert (cal["date"].diff().dropna() == pd.Timedelta(days=1)).all()


def test_reaches_the_year_of_the_last_installment(client, household):
    # 12x bought in Nov 2026, entered on installment 1: the last bill is Oct 2027.
    when = f"{datetime.date.today().year}-11-10T10:00:00-03:00"
    spend(client, household, when, total_installments=12, current_installment=1)
    cal = extract_calendar(database.engine)
    last_bill = pd.to_datetime(extract_cashflow(database.engine)["billing_month"]).max()

    assert cal["date"].max() == pd.Timestamp(last_bill.year, 12, 31)
    assert last_bill.year == datetime.date.today().year + 1


def test_weeks_are_iso_and_weekends_marked(client):
    cal = extract_calendar(database.engine).set_index("date")
    # The first two weeks of the year, checked against Python's ISO calendar.
    for day, row in cal.iloc[:14].iterrows():
        iso = day.isocalendar()
        assert (row["iso_year"], row["iso_week"], row["weekday_number"]) == (iso.year, iso.week, iso.weekday)
        assert row["week_start"] == day - pd.Timedelta(days=iso.weekday - 1)  # the Monday
        assert row["is_weekend"] == (iso.weekday >= 6)
        assert row["month_start"] == day.replace(day=1)
        assert row["month_name"] == day.strftime("%B") and row["weekday_name"] == day.strftime("%A")


def test_fact_dates_are_sao_paulo_days_that_exist_in_the_calendar(client, household):
    # 23:30 on 31 Oct in São Paulo is already 1 Nov in UTC.
    spend(client, household, "2026-10-31T23:30:00-03:00")
    cal_days = set(extract_calendar(database.engine)["date"])

    for df in (extract_data(database.engine), extract_allocations(database.engine), extract_cashflow(database.engine)):
        assert set(df["transaction_date"]) == {pd.Timestamp(2026, 10, 31)}
        assert set(df["transaction_date"]) <= cal_days


def test_calendar_hyper_types_match_the_fact_dates(client, household, tmp_path):
    spend(client, household, "2026-10-08T12:00:00-03:00")
    paths = {
        "calendar": generate_hyper_file(extract_calendar(database.engine), "calendar.hyper", str(tmp_path)),
        "allocations": generate_hyper_file(extract_allocations(database.engine), "allocations.hyper", str(tmp_path)),
    }
    types = {}
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_dir": str(tmp_path)}) as hyper:
        for name, path in paths.items():
            with Connection(hyper.endpoint, path) as conn:
                table = conn.catalog.get_table_definition(TableName("Expenditures"))
                types[name] = {c.name.unescaped: str(c.type) for c in table.columns}
    # Relationships need both sides to have the same type.
    assert types["calendar"]["date"] == types["allocations"]["transaction_date"] == "TIMESTAMP"
    assert types["calendar"]["is_weekend"] == "BOOL"
