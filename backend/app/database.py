"""Connexion SQLAlchemy + helper de session FastAPI."""
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import DATABASE_URL

_log = logging.getLogger(__name__)

try:
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    _log.info("DB engine créé : %s", DATABASE_URL[:40])
except Exception as _e:
    _log.error("DATABASE_URL invalide (%s), fallback SQLite. Erreur : %s", DATABASE_URL[:60], _e)
    _fallback = f"sqlite:///{Path(__file__).parent.parent / 'reclamations.db'}"
    engine = create_engine(_fallback, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
