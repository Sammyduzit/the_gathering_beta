"""
Database setup strategies for different test types.

This module provides clean abstractions for database configuration across
unit, integration, and E2E tests with proper isolation and cleanup.
"""

import os
from enum import Enum
from typing import AsyncGenerator

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

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


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create test database engine for the entire test session.

    This fixture automatically selects the appropriate database strategy
    based on environment variables and test type.
    """
    strategy = DatabaseStrategy.from_env()
    engine = create_test_engine(strategy)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_schema(test_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """
    Create database schema once per test session.

    For SQLite: Creates schema for each engine (in-memory)
    For PostgreSQL: Creates schema once and cleans up after session
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Only drop tables for PostgreSQL (SQLite is in-memory)
    strategy = DatabaseStrategy.from_env()
    if strategy.is_postgresql:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine: AsyncEngine, test_schema) -> AsyncGenerator[AsyncSession, None]:
    """
    Create isolated database session for each test with automatic cleanup.

    This fixture provides transaction isolation - each test gets a fresh
    transaction that is automatically rolled back after the test completes.
    """
    session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with session_maker() as session:
        # Start a transaction for test isolation
        transaction = await session.begin()

        try:
            yield session
        finally:
            # Always rollback to ensure clean state
            await transaction.rollback()


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