"""
database.py — SQLAlchemy engine, session factory, Base ORM et dépendance FastAPI.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/nvest")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dépendance FastAPI : fournit une session DB, fermée après la requête."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
