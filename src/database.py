"""Unified database initialization and session management.

Provides database setup, session management, and migration utilities
for the unified schema architecture.
"""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from .config import get_settings
from .schemas.database import (
    Task,
    TaskComment,
    TaskDependency,
    TaskExecutionLog,
    TaskProgress,
)

# Get settings
settings = get_settings()

# Create engines
engine: Engine = create_engine(
    f"sqlite:///{settings.database.implementation_tracker_path}",
    echo=settings.database.echo_sql,
    pool_size=settings.database.pool_size,
    pool_timeout=settings.database.pool_timeout,
)

# Legacy compatibility - sync engine for existing code
sync_engine = engine


def create_db_and_tables() -> None:
    """Create database and all tables.

    This function ensures all SQLModel tables are created in the database.
    Safe to call multiple times - only creates tables that don't exist.
    """
    # Ensure database directory exists
    db_path = Path(settings.database.implementation_tracker_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create all tables
    SQLModel.metadata.create_all(engine)
    print(f"Database initialized at: {db_path}")


def get_sync_session() -> Session:
    """Get a synchronous database session.

    Returns:
        SQLModel Session for database operations

    """
    return Session(engine)


@contextmanager
def get_session_context() -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic cleanup.

    Usage:
        with get_session_context() as session:
            # Use session here
            pass

    Raises:
        Exception: If there is an error during session operations

    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> None:
    """Initialize the database with tables and basic setup.

    This is the main entry point for database initialization.
    """
    print("Initializing unified schema database...")

    # Create database and tables
    create_db_and_tables()

    # Verify tables were created
    with get_session_context() as session:
        # Test basic operations
        task_count = len(session.exec(select(Task)).all())
        print(f"Database ready. Current task count: {task_count}")

    print("Database initialization complete.")


def verify_database() -> bool:
    """Verify database integrity and schema.

    Raises:
        Exception: If there is an error during database verification

    Returns:
        True if database is healthy, False otherwise

    """
    try:
        with get_session_context() as session:
            # Test each table (use SQLModel's exec/select instead of deprecated query)
            task_count = len(session.exec(select(Task)).all())
            dep_count = len(session.exec(select(TaskDependency)).all())
            progress_count = len(session.exec(select(TaskProgress)).all())
            log_count = len(session.exec(select(TaskExecutionLog)).all())
            comment_count = len(session.exec(select(TaskComment)).all())

            print("Database verification successful:")
            print(f"  Tasks: {task_count}")
            print(f"  Dependencies: {dep_count}")
            print(f"  Progress records: {progress_count}")
            print(f"  Execution logs: {log_count}")
            print(f"  Comments: {comment_count}")

            return True
    except Exception as e:
        print(f"Database verification failed: {e}")
        return False


# Export commonly used items
__all__ = [
    "create_db_and_tables",
    "engine",
    "get_session_context",
    "get_sync_session",
    "init_database",
    "sync_engine",
    "verify_database",
]
