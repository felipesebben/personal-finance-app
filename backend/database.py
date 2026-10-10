from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import settings

# Connection details come from config.settings (validated at startup).
# DB_NAME and DATABASE_URL stay exported here because Alembic's env.py and
# the test fixtures read them from this module.
DB_NAME = settings.db_name
DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
