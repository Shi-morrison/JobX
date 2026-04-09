import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from db.models import Base
from config import settings


def _ensure_data_dir():
    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # needed for SQLite
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_session() -> Session:
    """Context manager that yields a DB session and handles commit/rollback."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Create all tables. Safe to call multiple times — skips existing tables."""
    _ensure_data_dir()
    Base.metadata.create_all(bind=engine)
