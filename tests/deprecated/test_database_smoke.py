"""
Integration smoke tests for database connectivity and basic operations.

These tests verify that the database connection, schema creation,
and basic CRUD operations work correctly with PostgreSQL.
"""

import pytest
from sqlalchemy import text


@pytest.mark.integration
class TestDatabaseSmoke:
    """Smoke tests for database connectivity."""

    async def test_database_connection(self, db_session):
        """Verify PostgreSQL database connection is working."""
        result = await db_session.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        assert row[0] == 1

    async def test_database_schema_exists(self, db_session):
        """Verify all required tables exist in the database."""
        # Check for main tables
        result = await db_session.execute(
            text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
        )
        tables = [row[0] for row in result.fetchall()]

        # Verify essential tables exist
        required_tables = ['users', 'rooms', 'messages', 'conversations']
        for table in required_tables:
            assert table in tables, f"Required table '{table}' not found in database"

    async def test_create_user_basic(self, user_factory, db_session):
        """Verify basic user creation works."""
        user = await user_factory.create(
            db_session,
            username="smoke_test_user",
            email="smoke@test.com"
        )

        assert user.id is not None
        assert user.username == "smoke_test_user"
        assert user.email == "smoke@test.com"

    async def test_create_room_basic(self, room_factory, db_session):
        """Verify basic room creation works."""
        room = await room_factory.create(
            db_session,
            name="Smoke Test Room"
        )

        assert room.id is not None
        assert room.name == "Smoke Test Room"
