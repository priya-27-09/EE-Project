from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

# Strict validation
if "sqlite" in settings.DATABASE_URL.lower():
    raise RuntimeError("SQLite is strictly prohibited. Use PostgreSQL only.")

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Yield database session and handle cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
