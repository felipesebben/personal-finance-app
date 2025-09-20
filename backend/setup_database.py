# backend/setup_database.py
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import getpass

# --- CONFIGURATION for the new user and database ---
NEW_DB_NAME = "expenditures"
NEW_DB_USER = "testuser"
NEW_DB_PASS = "testpassword123"
# ---

try:
    # SECURELY PROMPT FOR THE SUPERUSER PASSWORD AT RUNTIME
    POSTGRES_SUPERUSER_PASSWORD = getpass.getpass(
        "Enter the password for the 'postgres' superuser: "
    )

    # Connect to the default 'postgres' database as the superuser
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres", # It's safe to assume the superuser is 'postgres'
        password=POSTGRES_SUPERUSER_PASSWORD,
        host="localhost",
        client_encoding='utf8'
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    print("\nSuccessfully connected to PostgreSQL as superuser.")

    # Create the user if they don't exist
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (NEW_DB_USER,))
    if not cursor.fetchone():
        print(f"User '{NEW_DB_USER}' not found. Creating user...")
        cursor.execute(f"CREATE USER {NEW_DB_USER} WITH PASSWORD '{NEW_DB_PASS}'")
        print("User created successfully.")
    else:
        print(f"User '{NEW_DB_USER}' already exists.")
        # If user exists, it's good practice to ensure their password is what we expect
        cursor.execute(f"ALTER USER {NEW_DB_USER} WITH PASSWORD '{NEW_DB_PASS}'")
        print(f"Password for user '{NEW_DB_USER}' has been set/updated.")


    # Create the database if it doesn't exist
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (NEW_DB_NAME,))
    if not cursor.fetchone():
        print(f"Database '{NEW_DB_NAME}' not found. Creating database...")
        cursor.execute(f"CREATE DATABASE {NEW_DB_NAME}")
        print("Database created successfully.")
    else:
        print(f"Database '{NEW_DB_NAME}' already exists.")

    # Grant privileges to the new user on the new database
    cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {NEW_DB_NAME} TO {NEW_DB_USER}")
    print(f"Privileges granted to '{NEW_DB_USER}' on database '{NEW_DB_NAME}'.")

    print("\nDatabase setup is complete!")
    cursor.close()
    conn.close()

except psycopg2.OperationalError as e:
    if "password authentication failed" in str(e):
        print("\nError: Password authentication failed for the 'postgres' superuser.")
    else:
        print(f"\nAn operational error occurred: {e}")
except Exception as e:
    print(f"\nA general error occurred: {e}")