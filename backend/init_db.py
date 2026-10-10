import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from config import settings

# Load database configuration from config.settings (environment / .env)
DB_USER = settings.db_user
DB_PASSWORD = settings.db_password.get_secret_value()
DB_HOST = settings.db_host
DB_PORT = settings.db_port
DB_NAME = settings.db_name

try:
    # Connect to the default 'postgres' database
    
    conn = psycopg2.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        dbname='postgres' # Connect to the maintenance database
    )
    conn.set_client_encoding('UTF8')
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Check if the database already exists
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
    exists = cursor.fetchone()

    if not exists:
        print(f"Database '{DB_NAME}' does not exist. Creating it...")
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        print(f"Database '{DB_NAME}' created succsessfully.")
    else:
        print(f"Database '{DB_NAME}' already exists.")

    # Clean up
    cursor.close()
    conn.close()

except Exception as e:
    print(f"An error ocurred: {e}")