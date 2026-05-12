"""
database.py — SQLAlchemy engine + session factory
Database: SQLite (fichier local  converter.db)
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./converter.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},   # needed for SQLite + threads
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()