import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import pantab
from tableauhyperapi import TableName
from tableau_manager import TableauManager

# Load credentias from .env
load_dotenv()

# 1. Database Logic
def get_db_connection():
    """
    Creates the connection string for SQLAlchemy.
    """
    try:
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT")
        dbname = os.getenv("DB_NAME")

        # Validate inputs to avoid errors later on
        if not all([user, password, host, port, dbname]):
            print("Error: Missing DB credentials in .env")
            return None
        
        url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        return create_engine(url)
    except Exception as e:
        print(f"Configuration error: {e}")
        return None
    
def extract_data():
    """
    Step 1: Extract data from Postgres.
    """
    print("Connecting to Database...")
    engine = get_db_connection()
    if not engine: return None

    # Simple query to test the join logic
    query = """
    SELECT
        f.expenditure_id,
        f.transaction_timestamp,
        f.price,
        f.nature,
        f.is_shared,
        p.person_name,
        c.primary_category,
        c.sub_category,
        c.cost_type,
        pm.method_name,
        pm.institution
    FROM fact_expenditures f
    JOIN dim_person p ON f.person_id = p.person_id
    JOIN dim_category c ON f.category_id = c.category_id
    JOIN dim_paymentmethod pm ON f.payment_method_id = pm.payment_method_id;    
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

# 2. Hyper Logic
def generate_hyper_file(df, filename="expenditures.hyper"):
    """
    Step 2: Testing Hyper File Generation
    
    :param df: DataFrame
    :param filename: Filename for generated `.hyper` file
    """
    print("Generating Hyper file...")

    # Define a clean subfolder for output
    output_dir = "artifacts"

    # Create the folder if it does not exist
    os.makedirs(output_dir, exist_ok=True)

    # Combine folder + filename
    file_path = os.path.join(output_dir, filename)
    
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

if __name__ == "__main__":
    # 1. Extract
    df = extract_data()

    # 2. Generate file
    # Only run if Step 1 returned actual data
    if df is not None:
        hyper_file = generate_hyper_file(df, filename="expenditures.hyper")

        # Only run if file was created successfully
        if hyper_file:
            # 3. Publish using new Class
            manager = TableauManager()

            # Test:  change project name to an unexisting value.
            manager.publish_hyper(hyper_file, targer_project_name="Finance App 2026")
