from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


# This is the connection string for our PostgreSQL database.
# We'll replace the credentials with environment variables
# once we set up Docker.

DATABASE_URL = "postgresql://user:password@localhost/expenditures"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocomit=False, autoflush=False, bind=engine)
Base = declarative_base()