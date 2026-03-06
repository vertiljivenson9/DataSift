"""
Database Configuration - SQLAlchemy with Supabase PostgreSQL
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool
import os
import logging

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.warning("DATABASE_URL not set. Using SQLite for development.")
    DATABASE_URL = "sqlite:///./datasift_dev.db"


def get_engine_config(url: str) -> dict:
    """Get SQLAlchemy engine configuration based on database type"""
    
    if url.startswith("postgresql"):
        # Production PostgreSQL configuration (Supabase)
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
    else:
        # SQLite configuration for development
        return {
            "connect_args": {"check_same_thread": False},
            "poolclass": NullPool
        }


# Create engine
engine_config = get_engine_config(DATABASE_URL)
engine = create_engine(DATABASE_URL, **engine_config)

# Add event listeners for connection debugging
@event.listens_for(engine, "connect")
def on_connect(dbapi_conn, connection_record):
    logger.debug("Database connection established")


@event.listens_for(engine, "checkout")
def on_checkout(dbapi_conn, connection_record, connection_proxy):
    logger.debug("Database connection checked out from pool")


# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

# Scoped session for thread safety
ScopedSession = scoped_session(SessionLocal)


def get_db():
    """
    Get database session.
    Use as FastAPI dependency.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_scoped():
    """
    Get scoped database session.
    Use for background tasks.
    """
    db = ScopedSession()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    from . import models
    logger.info("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def check_connection() -> bool:
    """Check database connectivity"""
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False
