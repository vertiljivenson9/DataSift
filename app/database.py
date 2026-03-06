"""
Database Configuration - SQLAlchemy with Supabase PostgreSQL
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool
import os
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.warning("DATABASE_URL not set. Using SQLite for development.")
    DATABASE_URL = "sqlite:///./datasift_dev.db"


def get_engine_config(url: str):

    if url.startswith("postgresql"):
        return {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_timeout": 30,
            "connect_args": {
                "sslmode": "require",
                "connect_timeout": 10
            }
        }

    return {
        "connect_args": {"check_same_thread": False},
        "poolclass": NullPool
    }


engine_config = get_engine_config(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    **engine_config
)


@event.listens_for(engine, "connect")
def on_connect(dbapi_conn, connection_record):
    logger.debug("Database connection established")


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

ScopedSession = scoped_session(SessionLocal)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_scoped():
    db = ScopedSession()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models

    logger.info("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def check_connection():

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True

    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False
