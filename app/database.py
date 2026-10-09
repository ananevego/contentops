import os
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from sqlalchemy import create_engine

from app.models.content_db import Base

load_dotenv()

def _database_url() -> str:
    """Builds a database URL without requiring PostgreSQL for local demos/tests."""
    if configured_url := os.getenv("DATABASE_URL"):
        return configured_url

    values = {
        name: os.getenv(name)
        for name in (
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "POSTGRES_DB",
        )
    }
    if all(values.values()):
        return (
            "postgresql+psycopg://"
            f"{values['POSTGRES_USER']}:{values['POSTGRES_PASSWORD']}@"
            f"{values['POSTGRES_HOST']}:{values['POSTGRES_PORT']}/"
            f"{values['POSTGRES_DB']}"
        )

    # The fallback intentionally contains no credentials and keeps the API,
    # analytics demo and test suite usable without external infrastructure.
    return "sqlite:///./contentops.db"


DATABASE_URL = _database_url()
engine_options = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def create_tables():
    Base.metadata.create_all(engine)


def get_db():
    """FastAPI dependency which always closes the SQLAlchemy session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
