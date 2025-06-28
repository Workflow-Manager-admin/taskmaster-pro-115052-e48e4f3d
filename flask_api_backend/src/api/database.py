from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


# PUBLIC_INTERFACE
def get_sqlite_url():
    """Returns the SQLite database URL."""
    # For now, store database in the local project directory (can change path if needed)
    return "sqlite:///./tasks.db"


SQLALCHEMY_DATABASE_URL = get_sqlite_url()
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
