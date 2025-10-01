"""
Database setup strategies for different test types.

Modernized for pytest-asyncio 1.2.0 (October 2025)
- No event_loop fixture (removed in 1.x)
- Uses loop_scope parameter instead
- Function-scoped as default for maximum isolation

This module provides clean abstractions for database configuration across
unit, integration, and E2E tests with proper isolation and cleanup.
"""

import os
from enum import Enum

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool, NullPool

from app.core.database import Base


class DatabaseStrategy(Enum):
    """Database connection strategies for different test types."""

    UNIT = "sqlite+aiosqlite:///:memory:"
    INTEGRATION = "postgresql+asyncpg://postgres:postgres@localhost:5432/the_gathering_test"
    E2E = "postgresql+asyncpg://postgres:postgres@localhost:5432/the_gathering_test"

    @classmethod
    def from_env(cls) -> "DatabaseStrategy":
        """Determine strategy from environment variables."""
        if os.getenv("CI"):
            # CI environment always uses PostgreSQL
            return cls.E2E

        test_type = os.getenv("TEST_TYPE", "unit").lower()
        strategy_map = {
            "unit": cls.UNIT,
            "integration": cls.INTEGRATION,
            "e2e": cls.E2E,
        }
        return strategy_map.get(test_type, cls.UNIT)

    @property
    def is_sqlite(self) -> bool:
        """Check if this strategy uses SQLite."""
        return "sqlite" in self.value

    @property
    def is_postgresql(self) -> bool:
        """Check if this strategy uses PostgreSQL."""
        return "postgresql" in self.value


def create_test_engine(strategy: DatabaseStrategy) -> AsyncEngine:
    """
    Create async database engine for testing with appropriate configuration.

    Args:
        strategy: Database strategy to use

    Returns:
        Configured async engine
    """
    if strategy.is_sqlite:
        # SQLite configuration for fast unit tests
        engine = create_async_engine(
            strategy.value,
            poolclass=StaticPool,
            echo=False,
            future=True,
            connect_args={"check_same_thread": False}
        )

        # Enable foreign key constraints for SQLite
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    else:
        # PostgreSQL configuration for integration/E2E tests
        # Use NullPool to prevent asyncpg event loop binding issues
        # Each transaction gets a fresh connection, avoiding "attached to different loop" errors
        if strategy == DatabaseStrategy.INTEGRATION:
            engine = create_async_engine(
                strategy.value,
                poolclass=NullPool,  # No pooling for integration tests
                echo=False,
                future=True,
            )
        else:
            # E2E tests can use connection pooling (HTTP layer overhead is higher anyway)
            engine = create_async_engine(
                strategy.value,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
                future=True,
                pool_size=5,
                max_overflow=10
            )

    return engine


# NOTE: These generic fixtures are no longer used
# Each test type (unit/integration/e2e) defines its own fixtures in conftest.py
# This provides better Separation of Concerns and clarity


def create_test_session(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    Create session maker for manual session management.

    Useful for complex test scenarios that need manual transaction control.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )


# Database URL helpers for explicit configuration
def get_unit_db_url() -> str:
    """Get database URL for unit tests."""
    return DatabaseStrategy.UNIT.value


def get_integration_db_url() -> str:
    """Get database URL for integration tests."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return DatabaseStrategy.INTEGRATION.value

    # Convert to async if needed
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    return db_url


def get_e2e_db_url() -> str:
    """Get database URL for E2E tests."""
    return get_integration_db_url()  # Same as integration for now


def require_postgresql() -> None:
    """
    Ensure PostgreSQL is available for integration/E2E tests.

    Raises:
        RuntimeError: If PostgreSQL is not available
    """
    strategy = DatabaseStrategy.from_env()
    if strategy.is_sqlite:
        raise RuntimeError(
            "This test requires PostgreSQL. "
            "Set TEST_TYPE=integration or TEST_TYPE=e2e, "
            "or ensure DATABASE_URL points to PostgreSQL."
        )