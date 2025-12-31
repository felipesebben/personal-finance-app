import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import pantab
from tableauhyperapi import TableName
import tableauserverclient as TSC

# Load credentias from .env
load_dotenv()

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

        url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        return create_engine(url)
    except Exception as e:
        print(f"Configuration error: {e}")
        return None
    
def test_extraction():
    print("--- Step 1: Testing Database Connection ---")
    engine = get_db_connection()

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
        pm.method_name
    FROM fact_expenditures f
    JOIN dim_person p ON f.person_id = p.person_id
    JOIN dim_category c ON f.category_id = c.category_id
    JOIN dim_paymentmethod pm ON f.payment_method_id = pm.payment_method_id
    LIMIT 5;    
    """

    try:
        df = pd.read_sql(query, engine)
        if not df.empty:
            print("Connection successful!")
            print(f"Extracted {len(df)} rows.")
            print(f"\nPreview of the data:")
            print(df.head())
            return df
        else:
            print("Connection worked, but table is empty.")
            return None
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

def test_hyper_generation(df):
    print("\n--- Step 2: Testing Hyper File Generation ---")
    filename = "test_extract.hyper"

    try:
        # pantab converts the pandas DataFrame to a .hyper file
        # The TableName creates a schema named Extract
        # And a table named "Expenditures" inside the file
        pantab.frame_to_hyper(
            df,
            filename,
            table=TableName("Extract", "Expenditures")
        )
        # Verify the file was actually created
        if os.path.exists(filename):
            print(f"Success! File '{filename}' was created.")
            print(f"File size: {os.path.getsize(filename)} bytes.")
            return filename
        else:
            print("Error: Function but file is missing.")
            return None
    except Exception as e:
        print(f"Hyper Generation Failed: {e}")
        return None

def test_tableau_auth():
    print("\n--- Step 3: Testing Tableau Authentication ---")

    try:
        # Load vars from .env
        server_url = os.getenv("TABLEAU_SERVER_URL")
        site_name = os.getenv("TABLEAU_SITENAME")
        token_name = os.getenv("TABLEAU_TOKEN_NAME")
        token_value = os.getenv("TABLEAU_TOKEN_VALUE")

        print(f"Attempting to connect to: {server_url}")
        print(f"Target Site: {site_name}")

        # Create Auth Object
        tableau_auth = TSC.PersonalAccessTokenAuth(
            token_name=token_name,
            personal_access_token=token_value,
            site_id=site_name
        )

        server = TSC.Server(server_url, use_server_version=True)

        # Try to sign in
        with server.auth.sign_in(tableau_auth):
            print("Login Successful!")
            print(f"Connected as user ID: {server.user_id}")

            # List projects just to check we can read data
            all_projects, _ = server.projects.get()
            print(f"Found {len(all_projects)} projects on server.")
            print("/nList of projects:")
            for proj in all_projects:
                print(f"    - {proj.name} (ID: {proj.id})")
            
            return True
    
    except Exception as e:
        print(f"Authentication Failed: {e}")
        print("Tip: Check your Token Name, Secred, and Site Name in .env")
        return False
    

def publish_datasource(hyper_file):
    print(f"\n---Step 4: Publishing to Tableau ---")

    # 1.Re-Authenticate (In a real class structure, reuse the seession)
    tableau_auth = TSC.PersonalAccessTokenAuth(
        token_name=os.getenv("TABLEAU_TOKEN_NAME"),
        personal_access_token=os.getenv("TABLEAU_TOKEN_VALUE"),
        site_id=os.getenv("TABLEAU_SITENAME")
    )

    server = TSC.Server(os.getenv("TABLEAU_SERVER_URL"), use_server_version=True)

    with server.auth.sign_in(tableau_auth):
        # 2. Find the "Default" project
        target_project_name = "default"
        all_projects, _ = server.projects.get()
        project_id = next((p.id for p in all_projects if p.name == target_project_name), None)

        if not project_id:
            print(f"Could not find project '{target_project_name}'")
            return
        # 3. Define the datasource
        print(f"Uploading to project {target_project_name}...")
        datasource = TSC.DatasourceItem(project_id)

        # Publish (overwrite mode ensures it updates everytime we run this)
        published_item = server.datasources.publish(
            datasource,
            hyper_file,
            "Overwrite"
        )
        print(f"Success! Published '{published_item.name}'")
        print(f"ID: {published_item.id}")

if __name__ == "__main__":
    # 1. Extract
    df = test_extraction()

    # 2. Generate file
    # Only run if Step 1 returned actual data
    if df is not None and not df.empty:
        hyper_file = test_hyper_generation(df)

        # 3. Test Auth
        # Only run if file was created successfully
        if hyper_file:
            test_tableau_auth()

        # 4. Publish
        publish_datasource(hyper_file)