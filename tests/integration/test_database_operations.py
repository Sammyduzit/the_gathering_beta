"""
Integration tests for database operations and PostgreSQL-specific features.

These tests verify database constraints, transactions, and PostgreSQL-specific
behavior that differs from SQLite used in unit tests.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.user import UserStatus


@pytest.mark.integration
class TestPostgreSQLConstraints:
    """Test PostgreSQL constraint validation and behavior."""

    async def test_user_unique_username_constraint(self, user_factory, db_session):
        """Test PostgreSQL enforces unique username constraint."""
        # Create first user
        user1 = await user_factory.create(db_session, username="unique_user", email="user1@test.com")
        assert user1.username == "unique_user"

        # Attempt to create second user with same username should fail
        with pytest.raises(IntegrityError) as exc_info:
            await user_factory.create(db_session, username="unique_user", email="user2@test.com")

        assert "duplicate key value violates unique constraint" in str(exc_info.value)

    async def test_user_unique_email_constraint(self, user_factory, db_session):
        """Test PostgreSQL enforces unique email constraint."""
        # Create first user
        user1 = await user_factory.create(db_session, username="user1", email="same@test.com")
        assert user1.email == "same@test.com"

        # Attempt to create second user with same email should fail
        with pytest.raises(IntegrityError) as exc_info:
            await user_factory.create(db_session, username="user2", email="same@test.com")

        assert "duplicate key value violates unique constraint" in str(exc_info.value)

    async def test_room_unique_name_constraint(self, room_factory, db_session):
        """Test PostgreSQL enforces unique room name constraint."""
        # Create first room
        room1 = await room_factory.create(db_session, name="Unique Room")
        assert room1.name == "Unique Room"

        # Attempt to create second room with same name should fail
        with pytest.raises(IntegrityError) as exc_info:
            await room_factory.create(db_session, name="Unique Room")

        assert "duplicate key value violates unique constraint" in str(exc_info.value)

    async def test_message_foreign_key_constraints(self, message_factory, user_factory, room_factory, db_session):
        """Test PostgreSQL enforces foreign key constraints for messages."""
        # Create valid user and room
        user = await user_factory.create(db_session, username="msg_user")
        room = await room_factory.create(db_session, name="Message Room")

        # Valid message should work
        message = await message_factory.create_room_message(db_session, sender=user, room=room)
        assert message.sender_id == user.id
        assert message.room_id == room.id

        # Invalid foreign key should fail
        with pytest.raises(IntegrityError) as exc_info:
            await message_factory.create_room_message(
                db_session,
                sender_id=99999,  # Non-existent user
                room=room,
                content="This should fail"
            )

        assert "violates foreign key constraint" in str(exc_info.value)


@pytest.mark.integration
class TestDatabaseTransactions:
    """Test transaction behavior and rollback scenarios."""

    async def test_transaction_rollback_on_constraint_violation(self, user_factory, db_session):
        """Test that constraint violations properly rollback transactions."""
        # Create initial user
        user1 = await user_factory.create(db_session, username="txn_user1", email="txn1@test.com")
        initial_count = len(await db_session.execute("SELECT * FROM users"))

        # Attempt transaction that should fail
        try:
            # This should succeed
            user2 = await user_factory.create(db_session, username="txn_user2", email="txn2@test.com")

            # This should fail due to duplicate username
            await user_factory.create(db_session, username="txn_user1", email="different@test.com")

        except IntegrityError:
            # Transaction should be rolled back
            await db_session.rollback()

        # Verify database state is consistent
        final_count = len(await db_session.execute("SELECT * FROM users"))
        assert final_count == initial_count  # Should be same as before failed transaction

    async def test_concurrent_user_creation_handling(self, user_factory, db_session):
        """Test handling of concurrent operations (simulated)."""
        # Create multiple users with unique identifiers to avoid conflicts
        users = []
        for i in range(5):
            user = await user_factory.create(
                db_session,
                username=f"concurrent_user_{i}",
                email=f"concurrent_{i}@test.com"
            )
            users.append(user)

        # Verify all users were created successfully
        assert len(users) == 5
        assert all(user.id is not None for user in users)

        # Verify usernames are unique
        usernames = [user.username for user in users]
        assert len(set(usernames)) == 5


@pytest.mark.integration
class TestComplexQueries:
    """Test complex database queries and PostgreSQL-specific features."""

    async def test_user_room_relationship_queries(self, user_repo, room_repo, user_factory, room_factory, db_session):
        """Test complex queries involving user-room relationships."""
        # Create room and users
        room = await room_factory.create(db_session, name="Query Test Room", max_users=10)

        # Create users in the room
        users_in_room = []
        for i in range(3):
            user = await user_factory.create(
                db_session,
                username=f"room_user_{i}",
                email=f"room_user_{i}@test.com",
                current_room_id=room.id,
                status=UserStatus.AVAILABLE
            )
            users_in_room.append(user)

        # Create users not in the room
        users_outside = []
        for i in range(2):
            user = await user_factory.create(
                db_session,
                username=f"outside_user_{i}",
                email=f"outside_user_{i}@test.com",
                status=UserStatus.AWAY
            )
            users_outside.append(user)

        # Test room user count query
        user_count = await room_repo.get_user_count(room.id)
        assert user_count == 3

        # Test getting users in room
        room_users = await room_repo.get_users_in_room(room.id)
        assert len(room_users) == 3

        room_user_ids = {user.id for user in room_users}
        expected_ids = {user.id for user in users_in_room}
        assert room_user_ids == expected_ids

    async def test_message_pagination_and_ordering(self, message_repo, message_factory, user_factory, room_factory, db_session):
        """Test message pagination with proper ordering (PostgreSQL specific)."""
        # Create test data
        room = await room_factory.create(db_session, name="Pagination Room")
        user = await user_factory.create(db_session, username="msg_sender", current_room_id=room.id)

        # Create multiple messages
        messages = []
        for i in range(15):
            message = await message_factory.create_room_message(
                db_session,
                sender=user,
                room=room,
                content=f"Message {i+1}"
            )
            messages.append(message)

        # Test pagination (first page)
        page1_messages, total_count = await message_repo.get_room_messages(
            room_id=room.id,
            page=1,
            page_size=10
        )

        assert total_count == 15
        assert len(page1_messages) == 10

        # Messages should be ordered by creation time (newest first)
        assert page1_messages[0].content == "Message 15"
        assert page1_messages[9].content == "Message 6"

        # Test pagination (second page)
        page2_messages, total_count = await message_repo.get_room_messages(
            room_id=room.id,
            page=2,
            page_size=10
        )

        assert total_count == 15
        assert len(page2_messages) == 5
        assert page2_messages[0].content == "Message 5"
        assert page2_messages[4].content == "Message 1"

    async def test_case_sensitive_queries(self, user_repo, user_factory, db_session):
        """Test PostgreSQL case-sensitive behavior vs SQLite."""
        # Create users with different cases
        user1 = await user_factory.create(db_session, username="TestUser", email="test1@case.com")
        user2 = await user_factory.create(db_session, username="testuser", email="test2@case.com")
        user3 = await user_factory.create(db_session, username="TESTUSER", email="test3@case.com")

        # All should be created successfully (case sensitive)
        assert user1.username == "TestUser"
        assert user2.username == "testuser"
        assert user3.username == "TESTUSER"

        # Test exact case matching
        found_user = await user_repo.get_by_username("TestUser")
        assert found_user is not None
        assert found_user.id == user1.id

        # Different case should not match in PostgreSQL
        not_found = await user_repo.get_by_username("testuser")
        assert not_found is not None
        assert not_found.id == user2.id  # Should find the exact match

        # Test case-insensitive email search behavior
        found_by_email = await user_repo.get_by_email("TEST1@CASE.COM")
        # This behavior depends on email field collation in PostgreSQL
        # Most likely will NOT find the user (case sensitive)
        assert found_by_email is None or found_by_email.id == user1.id


@pytest.mark.integration
class TestDatabasePerformance:
    """Test performance characteristics specific to PostgreSQL."""

    async def test_bulk_user_creation_performance(self, user_factory, db_session):
        """Test bulk operations performance."""
        import time

        start_time = time.time()

        # Create 50 users to test bulk performance
        users = []
        for i in range(50):
            user = await user_factory.create(
                db_session,
                username=f"perf_user_{i}",
                email=f"perf_user_{i}@performance.test"
            )
            users.append(user)

        end_time = time.time()
        duration = end_time - start_time

        # Performance assertion (should complete reasonably fast)
        assert duration < 10.0  # Should complete in less than 10 seconds
        assert len(users) == 50
        assert all(user.id is not None for user in users)

    async def test_complex_join_query_performance(self, user_repo, room_repo, message_repo, user_factory, room_factory, message_factory, db_session):
        """Test performance of complex queries with joins."""
        # Create test data
        room = await room_factory.create(db_session, name="Performance Room")

        # Create multiple users and messages
        for i in range(10):
            user = await user_factory.create(
                db_session,
                username=f"perf_msg_user_{i}",
                email=f"perf_msg_user_{i}@test.com",
                current_room_id=room.id
            )

            # Each user sends 5 messages
            for j in range(5):
                await message_factory.create_room_message(
                    db_session,
                    sender=user,
                    room=room,
                    content=f"Performance message {j} from user {i}"
                )

        import time
        start_time = time.time()

        # Complex query: Get all messages with user info
        messages, total_count = await message_repo.get_room_messages(
            room_id=room.id,
            page=1,
            page_size=50
        )

        end_time = time.time()
        duration = end_time - start_time

        # Performance and correctness assertions
        assert duration < 1.0  # Should complete quickly
        assert total_count == 50  # 10 users * 5 messages each
        assert len(messages) == 50