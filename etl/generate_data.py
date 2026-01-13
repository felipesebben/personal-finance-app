import os
import random
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 1. Setup Connection
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5433")
DB_NAME = os.getenv("DB_NAME")

# Connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

print("Connecting to database...")

def get_ids(table_name, id_col):
    """
    Helper to get list of valid IDs from a dimension table.
    """
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
        if df.empty:
            print(f"Warning: Table {table_name} is empty! Please add data via App first.")
            return [], df
        return df[id_col].tolist(), df
    except Exception as e:
        print(f"Error reading {table_name}: {e}")
        return [], None
    
# 2. Fetch dimensions (so we only use existing IDs)
person_ids, _ = get_ids("dim_person", "person_id")
method_ids, _ = get_ids("dim_paymentmethod", "payment_method_id")
cat_ids, cat_df = get_ids("dim_category", "category_id")

if not person_ids or not method_ids or not cat_ids:
    print("Cannot generate data. Missing Dimensions. Check 'Manage Settings'.")
    exit()

# 3. Smart pricing logic
# Maps sub-categories to realistic price ranges (min, max)
price_logic = {
    "Condo Fees": (400, 900),
    "Electricity": (110, 400),
    "House Gas": (50, 100),
    "Internet": (100, 150),
    "Maintenance": (200, 300),
    "Renovation": (300, 3000),
    "Furnishings": (100, 1500),
    "Groceries": (50, 800),
    "Eating Out": (30, 600),
    "Fuel": (100, 280),
    "Rideshare": (10, 100),
    "Car Maintenance": (50, 1200)    
}

print("Generating 50 dummy transactions...")

data = []

for _ in range(50):
    # Pick random category
    cat_row = cat_df.sample(1).iloc[0]
    cat_id = cat_row["category_id"]
    sub_cat = cat_row["sub_category"]

    # Determine price based on category
    low, high = price_logic.get(sub_cat, (20, 100))
    price = round(random.uniform(low, high), 2)

    # Determine date (last 60 days)
    days_ago = random.randint(0, 60)
    tx_date = datetime.now() - timedelta(days=days_ago)

    # Special logic for fixed costs (set to 1st or 10th of month)
    if cat_row["cost_type"] == "Fixed":
        # Force day to be 5th or 10th
        try:
            tx_date = tx_date.replace(day=random.choice([5, 10]))
        except ValueError:
            pass # Handle Feb 30 issues
    
    data.append({
        "transaction_timestamp": tx_date,
        "price": price,
        "person_id": random.choice(person_ids),
        "category_id": cat_id,
        "payment_method_id": random.choice(method_ids),
        "nature": "Normal",
        "is_shared": True
    })

# 4. Insert into Database
df_new = pd.DataFrame(data)

try:
    df_new.to_sql("fact_expenditures", engine, if_exists="append", index=False)
    print(f"Success! Inserted {len(df_new)} rows.")

    # 5. Show preview
    print("\nSample Data:")
    print(df_new[["transaction_timestamp", "price", "category_id"]].head())
except Exception as e:
    print(f"Insert Failed: {e}")
