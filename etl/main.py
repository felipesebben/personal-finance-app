import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import pantab
from tableauhyperapi import TableName
import tableauserverclient as TSC

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
        pm.method_name
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

    try:
        pantab.frame_to_hyper(df, filename, table="Expenditures")
  
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

# 3. Tableau Auth
def get_tableau_session():
    """
    Creates the Server and Auth objects using .env credentials.
    Returns (server, auth_object) or (None, None) if config is missing.
    """
    server_url = os.getenv("TABLEAU_SERVER_URL")
    site_name = os.getenv("TABLEAU_SITENAME")
    token_name = os.getenv("TABLEAU_TOKEN_NAME")
    token_value = os.getenv("TABLEAU_TOKEN_VALUE")

    if not all([server_url, site_name, token_name, token_value]):
        print("Error: Missing Tableau credentials in .env")
        return None, None
    
    tableau_auth = TSC.PersonalAccessTokenAuth(
        token_name=token_name,
        personal_access_token=token_value,
        site_id=site_name
    )
    server = TSC.Server(server_url, use_server_version=True)
    return server, tableau_auth

# 4. Publishing
def publish_datasource(hyper_file):
    """
    Step 3: Publish to Tableau Cloud with Expiry Handling
    
    :param hyper_file: `.hyper` filename
    """
    print("Connecting to Tableau Cloud...")

    # 1. Authenticate
    server, tableau_auth = get_tableau_session()
    if not server: return

    try:
        # 2. Try to Sign in
        with server.auth.sign_in(tableau_auth):
            print(f"Logged in as user ID: {server.user_id}")

        # 3. Find project
        target_project = "default"
        all_projects, _ = server.projects.get()
        project_id = next((p.id for p in all_projects if p.name == target_project), None)

        if not project_id:
            print(f"Could not find project '{target_project}'")
            return
        
        # 4. Publish
        print(f"Uploading {hyper_file} to {target_project}...")
        datasource = TSC.DatasourceItem(project_id)
        published_item = server.datasources.publish(datasource, hyper_file, "Overwrite")

        print(f"Success! Published '{published_item.name}'")
        print(f"ID: {published_item.id}")

    except TSC.ServerResponseError as e:
        if e.code == '401002':
            print("\n Authentication Error: Token Invalid or Expired.")
            print("Action: Your Personal Access Token may have expired")
            print("Go to Tableau Cloud > Users > Settings and generate a new one.")
            print(f"    (Error detail): {e}")
        else:
            print(f"Tableau Server Error: {e}")
    except Exception as e:
        print(f"Unexpected Error during publishing: {e}")


# 4. Publish
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
    df = extract_data()

    # 2. Generate file
    # Only run if Step 1 returned actual data
    if df is not None:
        hyper_file = generate_hyper_file(df, filename="expenditures.hyper")

        # 3. Publish
        # Only run if file was created successfully
        if hyper_file:
            publish_datasource(hyper_file)