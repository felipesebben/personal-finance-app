import os

import pandas as pd
import pantab
import database
from config import settings
from etl.tableau_manager import TableauManager


# Helper functions
def get_db_connection():
    """
    Returns the app's SQLAlchemy engine, so the ETL and the API share one
    connection configuration (config.settings) instead of each building
    its own from environment variables.
    """
    return database.engine
    
def extract_data(engine=None):
    """
    Step 1: Extract data from Postgres, one row per expenditure.
    """
    print("Connecting to Database...")
    engine = engine or get_db_connection()
    if not engine: return None

    # Simple query to test the join logic
    query = """
    SELECT
        f.expenditure_id,
        f.transaction_timestamp AT TIME ZONE 'America/Sao_Paulo' AS transaction_timestamp,
        f.price,
        f.nature,
        -- Derived from allocation rows (someone other than the payer bears
        -- part of it); the legacy is_shared column is no longer read.
        EXISTS (
            SELECT 1 FROM fact_expenditure_split o
            WHERE o.expenditure_id = f.expenditure_id AND o.user_id <> f.user_id
        ) AS is_shared,
        p.full_name,
        c.primary_category,
        c.sub_category,
        c.cost_type,
        pm.method_name,
        pm.institution
    FROM fact_expenditures f
    JOIN dim_user p ON f.user_id = p.user_id
    JOIN dim_category c ON f.category_id = c.category_id
    JOIN dim_payment_method pm ON f.payment_method_id = pm.payment_method_id;    
    """

    try:
        df = pd.read_sql(query, engine)
        if df.empty:
            print("Connection successful, but no data found.")
            return None
        print(f"Extracted {len(df)} rows.")
        return df
    except Exception as e:
        print(f"Database Extraction Failed: {e}")
        return None

# One row per person per expenditure: who bears what share of each cost.
# This is the grain per-person analysis should use - summing `share_amount`
# gives each person's real burden, while summing `price` from the
# expenditures datasource attributes 100% of a shared cost to the payer.
# `expense_total` repeats the full price on every row of the same
# expenditure, so never SUM it here; use share_amount.
ALLOCATIONS_QUERY = """
SELECT
    s.expenditure_id,
    f.transaction_timestamp AT TIME ZONE 'America/Sao_Paulo' AS transaction_timestamp,
    date_trunc('month', f.transaction_timestamp AT TIME ZONE 'America/Sao_Paulo')::date AS month_start,
    bearer.full_name AS borne_by,
    payer.full_name AS paid_by,
    s.share_pct,
    s.share_amount,
    s.split_source,
    f.price AS expense_total,
    EXISTS (
        SELECT 1 FROM fact_expenditure_split o
        WHERE o.expenditure_id = f.expenditure_id AND o.user_id <> f.user_id
    ) AS is_shared,
    f.nature,
    f.current_installment,
    f.total_installments,
    c.primary_category,
    c.sub_category,
    c.cost_type,
    pm.method_name,
    pm.institution,
    pm.is_credit
FROM fact_expenditure_split s
JOIN fact_expenditures f ON f.expenditure_id = s.expenditure_id
JOIN dim_user bearer ON bearer.user_id = s.user_id
JOIN dim_user payer ON payer.user_id = f.user_id
LEFT JOIN dim_category c ON c.category_id = f.category_id
LEFT JOIN dim_payment_method pm ON pm.payment_method_id = f.payment_method_id
ORDER BY s.expenditure_id, s.user_id;
"""


def extract_allocations(engine=None):
    """
    Extracts the allocation grain (one row per person per expenditure).
    """
    engine = engine or get_db_connection()
    if not engine: return None

    try:
        df = pd.read_sql(ALLOCATIONS_QUERY, engine)
        if df.empty:
            print("No allocation rows found.")
            return None
        print(f"Extracted {len(df)} allocation rows.")
        return df
    except Exception as e:
        print(f"Allocation Extraction Failed: {e}")
        return None

# One row per person per expenditure per *billing month*: the allocation
# grain with installment purchases spread over the months they're paid in,
# so SUM(amount) by billing_month is what each month actually cost, card
# statements included. The fact table keeps one row per purchase (notes/02,
# decision 3); the spreading happens only here.
#
# `price` is the full purchase price, and `current_installment` is the one
# billed in the month of `transaction_timestamp`, so installment k falls
# (k - current) months from it. Entering a 10x purchase on the day you buy
# it means 1/10; entering one you're already paying, 4/10 in this month.
# Expenses without installments appear once, in their own month.
#
# Each person's share is divided by the number of installments; all but the
# last are rounded down to the cent and the last takes the remainder, so the
# parts always sum exactly to the share and none can go negative.
CASHFLOW_QUERY = """
WITH alloc AS (
    SELECT
        s.expenditure_id,
        s.user_id,
        s.share_pct,
        s.share_amount,
        s.split_source,
        f.user_id AS payer_id,
        f.nature,
        f.category_id,
        f.payment_method_id,
        date_trunc('month', f.transaction_timestamp AT TIME ZONE 'America/Sao_Paulo')::date AS purchase_month,
        GREATEST(COALESCE(f.total_installments, 1), 1) AS n,
        LEAST(GREATEST(COALESCE(f.current_installment, 1), 1), GREATEST(COALESCE(f.total_installments, 1), 1)) AS cur
    FROM fact_expenditure_split s
    JOIN fact_expenditures f ON f.expenditure_id = s.expenditure_id
)
SELECT
    a.expenditure_id,
    k AS installment_number,
    a.n AS total_installments,
    (a.purchase_month + (k - a.cur) * interval '1 month')::date AS billing_month,
    a.purchase_month,
    CASE
        WHEN k < a.n THEN trunc(a.share_amount / a.n, 2)
        ELSE a.share_amount - (a.n - 1) * trunc(a.share_amount / a.n, 2)
    END AS amount,
    bearer.full_name AS borne_by,
    payer.full_name AS paid_by,
    a.share_pct,
    a.split_source,
    EXISTS (
        SELECT 1 FROM fact_expenditure_split o
        WHERE o.expenditure_id = a.expenditure_id AND o.user_id <> a.payer_id
    ) AS is_shared,
    a.nature,
    c.primary_category,
    c.sub_category,
    c.cost_type,
    pm.method_name,
    pm.institution,
    pm.is_credit
FROM alloc a
CROSS JOIN LATERAL generate_series(1, a.n) AS k
JOIN dim_user bearer ON bearer.user_id = a.user_id
JOIN dim_user payer ON payer.user_id = a.payer_id
LEFT JOIN dim_category c ON c.category_id = a.category_id
LEFT JOIN dim_payment_method pm ON pm.payment_method_id = a.payment_method_id
ORDER BY a.expenditure_id, a.user_id, k;
"""


def extract_cashflow(engine=None):
    """
    Extracts the billing-month grain (one row per person per expenditure per installment).
    """
    engine = engine or get_db_connection()
    if not engine: return None

    try:
        df = pd.read_sql(CASHFLOW_QUERY, engine)
        if df.empty:
            print("No cashflow rows found.")
            return None
        for col in ("billing_month", "purchase_month"):
            df[col] = pd.to_datetime(df[col])
        print(f"Extracted {len(df)} cashflow rows.")
        return df
    except Exception as e:
        print(f"Cashflow Extraction Failed: {e}")
        return None

# One row per payment between household members. Settlements move money
# between people rather than spending it, so they live in their own
# datasource instead of being mixed into the spending grain. `period_month`
# is the month the payment squares up (NULL = against the all-time
# balance), which is usually not the month the money moved.
SETTLEMENTS_QUERY = """
SELECT
    s.settlement_id,
    s.settled_at AT TIME ZONE 'America/Sao_Paulo' AS settled_at,
    date_trunc('month', s.settled_at AT TIME ZONE 'America/Sao_Paulo')::date AS settled_month_start,
    s.period_month,
    payer.full_name AS from_name,
    payee.full_name AS to_name,
    s.amount,
    s.note,
    recorder.full_name AS recorded_by
FROM fact_settlement s
JOIN dim_user payer ON payer.user_id = s.from_user_id
JOIN dim_user payee ON payee.user_id = s.to_user_id
JOIN dim_user recorder ON recorder.user_id = s.recorded_by_user_id
ORDER BY s.settled_at, s.settlement_id;
"""


def extract_settlements(engine=None):
    """
    Extracts settlements, one row per payment.
    """
    engine = engine or get_db_connection()
    if not engine: return None

    try:
        df = pd.read_sql(SETTLEMENTS_QUERY, engine)
        if df.empty:
            print("No settlements found.")
            return None
        # Pin the date columns' type: if every period_month is NULL, pandas
        # can't infer one, and a column that is text on one refresh and a
        # date on the next breaks Tableau workbooks built on it.
        for col in ("period_month", "settled_month_start"):
            df[col] = pd.to_datetime(df[col])
        print(f"Extracted {len(df)} settlements.")
        return df
    except Exception as e:
        print(f"Settlement Extraction Failed: {e}")
        return None

    # 2. Hyper Logic
def generate_hyper_file(df, filename="expenditures.hyper", output_dir="artifacts"):
    """
    Step 2: Testing Hyper File Generation
    
    :param df: DataFrame
    :param filename: Filename for generated `.hyper` file
    """
    print("Generating Hyper file...")

    # Create the folder if it does not exist
    os.makedirs(output_dir, exist_ok=True)

    # Combine folder + filename
    file_path = os.path.join(output_dir, filename)
    
    # A column that is entirely NULL (e.g. no payment method has an
    # institution yet) has no inferable type, and Hyper rejects it. Treat
    # those as text, which is what every nullable dimension column is.
    # Columns that already carry a type (e.g. pinned dates) keep it.
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object and df[col].isna().all():
            df[col] = df[col].astype("string")

    try:
        pantab.frame_to_hyper(df, file_path, table="Expenditures")

        # Verify the file was actually created
        if os.path.exists(file_path):
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"Success! File '{file_path}' was created.")
            print(f"File size: {size_mb:.2f} MB.")
            return file_path
        else:
            print("Error: Function but file is missing.")
            return None
    except Exception as e:
        print(f"Hyper Generation Failed: {e}")
        return None

# Main pipeline function - called by API #
# Define the function
def run_pipeline():
    """
    Runs the entire ETL pipeline sequence.
    """
    # 1. Extract
    df = extract_data()
    if df is None:
        print("Pipeline stopped: Extraction failed.")
        return
    
    # 2. Transform / Generate Files
    # The datasource name on Tableau comes from the file name, so these
    # publish as separate datasources: "expenditures" (unchanged, one row
    # per expense), "allocations" (one row per person per expense),
    # "cashflow" (allocations spread over installment billing months) and
    # "settlements" (one row per payment between members).
    hyper_files = []
    hyper_file = generate_hyper_file(df)
    if not hyper_file:
        print("Pipeline stopped: Hyper file generation failed.")
        return
    hyper_files.append(hyper_file)

    allocations_df = extract_allocations()
    if allocations_df is not None:
        allocations_file = generate_hyper_file(allocations_df, filename="allocations.hyper")
        if allocations_file:
            hyper_files.append(allocations_file)

    cashflow_df = extract_cashflow()
    if cashflow_df is not None:
        cashflow_file = generate_hyper_file(cashflow_df, filename="cashflow.hyper")
        if cashflow_file:
            hyper_files.append(cashflow_file)

    settlements_df = extract_settlements()
    if settlements_df is not None:
        settlements_file = generate_hyper_file(settlements_df, filename="settlements.hyper")
        if settlements_file:
            hyper_files.append(settlements_file)

    # 3. Publish
    try:
        print("Publishing to Tableau...")
        manager = TableauManager()
        for path in hyper_files:
            manager.publish_hyper(path, target_project_name=settings.tableau_project_name)
        print("ETL Finished Successfully!")

    except Exception as e:
        print(f"Publishing failed: {e}")
        # Raise the error so the API knows it failed (trigger 500 error)
        raise e
    
if __name__ == "__main__":
    run_pipeline()
