"""
Integration tests for database transactions and rollback behavior.

Tests verify that transactions are properly isolated and rolled back on errors.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.room import Room
from app.models.user import User


@pytest.mark.integration
class TestTransactionRollback:
    """Test transaction rollback on errors."""

    async def test_rollback_on_integrity_error(self, db_session, user_factory):
        """Verify transaction rolls back on integrity error."""
        # Create first user
        user1 = await user_factory.create(db_session, username="unique", email="user1@test.com")
        user1_id = user1.id

        # Start a new "transaction" by trying to create duplicate
        try:
            # This should fail due to unique constraint
            user2 = User(
                username="unique",  # Duplicate username
                email="user2@test.com",
                password_hash="hash"
            )
            db_session.add(user2)
            await db_session.commit()
        except IntegrityError:
            await db_session.rollback()

        # Verify original user still exists and no partial state
        result = await db_session.execute(
            select(User).where(User.username == "unique")
        )
        users = result.scalars().all()

        assert len(users) == 1
        assert users[0].id == user1_id
        assert users[0].email == "user1@test.com"

    async def test_transaction_isolation(self, db_session, user_factory):
        """Verify each test gets isolated transaction."""
        # Create user in this test
        user = await user_factory.create(db_session, username="isolated_user")

        # Verify user exists in this transaction
        result = await db_session.execute(
            select(User).where(User.username == "isolated_user")
        )
        assert result.scalar_one_or_none() is not None

    async def test_transaction_isolation_verification(self, db_session):
        """Verify user from previous test does NOT exist (transaction was rolled back)."""
        # This test runs AFTER test_transaction_isolation
        # User should NOT exist because transaction was rolled back
        result = await db_session.execute(
            select(User).where(User.username == "isolated_user")
        )
        assert result.scalar_one_or_none() is None

    async def test_nested_transaction_rollback(self, db_session, room_factory, user_factory):
        """Test rollback in nested operations."""
        # Create room
        room = await room_factory.create(db_session, name="Rollback Test Room")

        # Start nested operation
        try:
            # Create user with this room
            user = User(
                username="testuser",
                email="test@test.com",
                password_hash="hash",
                current_room_id=room.id
            )
            db_session.add(user)

            # Create duplicate room (should fail)
            duplicate_room = Room(
                name="Rollback Test Room"  # Duplicate name
            )
            db_session.add(duplicate_room)

            await db_session.commit()
        except IntegrityError:
            await db_session.rollback()

        # Verify rollback: room still exists, but user was not created
        result = await db_session.execute(
            select(Room).where(Room.name == "Rollback Test Room")
        )
        rooms = result.scalars().all()
        assert len(rooms) == 1  # Original room still exists

        result = await db_session.execute(
            select(User).where(User.username == "testuser")
        )
        users = result.scalars().all()
        assert len(users) == 0  # User was rolled back


@pytest.mark.integration
class TestTransactionCommit:
    """Test successful transaction commits."""

    async def test_commit_persists_data(self, db_session, user_factory, room_factory):
        """Verify committed data persists correctly."""
        # Create multiple related objects
        room = await room_factory.create(db_session, name="Persist Room")
        user1 = await user_factory.create(
            db_session, username="persist_user1", current_room_id=room.id
        )
        user2 = await user_factory.create(
            db_session, username="persist_user2", current_room_id=room.id
        )

        # Verify all persisted
        result = await db_session.execute(select(Room).where(Room.id == room.id))
        assert result.scalar_one() is not None

        result = await db_session.execute(
            select(User).where(User.current_room_id == room.id)
        )
        room_users = result.scalars().all()
        assert len(room_users) == 2

    async def test_bulk_insert_commit(self, db_session):
        """Test bulk insert and commit."""
        # Create multiple users in one transaction
        users = [
            User(
                username=f"bulk_user_{i}",
                email=f"bulk{i}@test.com",
                password_hash="hash"
            )
            for i in range(5)
        ]

        db_session.add_all(users)
        await db_session.commit()

        # Verify all committed
        result = await db_session.execute(
            select(User).where(User.username.like("bulk_user_%"))
        )
        saved_users = result.scalars().all()
        assert len(saved_users) == 5
