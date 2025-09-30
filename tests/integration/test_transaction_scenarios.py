"""
Integration tests for complex transaction scenarios and business logic.

These tests verify multi-step business operations work correctly with
real database transactions and rollback scenarios.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.conversation import ConversationType
from app.models.user import UserStatus


@pytest.mark.integration
class TestComplexBusinessTransactions:
    """Test complex business workflows with transaction integrity."""

    async def test_room_creation_with_admin_workflow(self, room_service, user_factory, db_session):
        """Test complete room creation workflow with admin assignment."""
        # Create admin user
        admin = await user_factory.create_admin(db_session, username="room_admin", email="admin@room.test")

        # Admin creates room
        room = await room_service.create_room(
            name="Transaction Test Room",
            description="Testing transaction scenarios",
            max_users=5,
            is_translation_enabled=True
        )

        assert room.name == "Transaction Test Room"
        assert room.max_users == 5
        assert room.is_translation_enabled is True

        # Verify room exists in database
        from app.repositories.room_repository import RoomRepository
        room_repo = RoomRepository(db_session)
        saved_room = await room_repo.get_by_id(room.id)

        assert saved_room is not None
        assert saved_room.name == room.name
        assert saved_room.is_translation_enabled == room.is_translation_enabled

    async def test_conversation_creation_with_participants_validation(self, conversation_service, test_room_with_users):
        """Test conversation creation with proper participant validation."""
        scenario = test_room_with_users
        creator = scenario["users"][0]
        participant = scenario["users"][1]

        # Create private conversation
        conversation = await conversation_service.create_conversation(
            current_user=creator,
            participant_usernames=[participant.username],
            conversation_type="private"
        )

        assert conversation.conversation_type == ConversationType.PRIVATE_CHAT
        assert conversation.room_id == scenario["room"].id

        # Verify conversation participants
        participants = await conversation_service.get_participants(creator, conversation.id)

        assert len(participants) == 2
        participant_usernames = {p["username"] for p in participants}
        expected_usernames = {creator.username, participant.username}
        assert participant_usernames == expected_usernames

    async def test_message_with_translation_workflow_transaction(self, room_service, translation_service, test_room_with_users):
        """Test message sending with translation as atomic transaction."""
        scenario = test_room_with_users
        english_user = scenario["english_user"]
        room = scenario["room"]

        # Ensure room has translation enabled
        room.is_translation_enabled = True

        # Send message that should trigger translation
        message = await room_service.send_room_message(
            english_user,
            room.id,
            "Hello, this message should be translated automatically!"
        )

        assert message.content == "Hello, this message should be translated automatically!"
        assert message.sender_id == english_user.id
        assert message.room_id == room.id

        # Note: Translation happens in background, so we can't immediately verify
        # the translation result. This test verifies the message creation transaction succeeds.

    async def test_user_room_joining_with_capacity_limits(self, room_service, user_factory, room_factory, db_session):
        """Test user room joining with capacity limit enforcement."""
        # Create room with limited capacity
        room = await room_factory.create(db_session, name="Limited Room", max_users=2)

        # Create users
        user1 = await user_factory.create(db_session, username="room_user_1", email="user1@limit.test")
        user2 = await user_factory.create(db_session, username="room_user_2", email="user2@limit.test")
        user3 = await user_factory.create(db_session, username="room_user_3", email="user3@limit.test")

        # First user joins successfully
        result1 = await room_service.join_room(user1, room.id)
        assert result1["room_id"] == room.id
        assert result1["user_count"] == 1

        # Second user joins successfully (room at capacity)
        result2 = await room_service.join_room(user2, room.id)
        assert result2["room_id"] == room.id
        assert result2["user_count"] == 2

        # Third user should be rejected (room full)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await room_service.join_room(user3, room.id)

        assert exc_info.value.status_code == 409
        assert "is full" in str(exc_info.value.detail)

        # Verify user states
        assert user1.current_room_id == room.id
        assert user1.status == UserStatus.AVAILABLE
        assert user2.current_room_id == room.id
        assert user2.status == UserStatus.AVAILABLE
        assert user3.current_room_id is None  # Should not be in room


@pytest.mark.integration
class TestTransactionRollbackScenarios:
    """Test transaction rollback in error scenarios."""

    async def test_conversation_creation_rollback_on_invalid_participant(self, conversation_service, test_room_with_users):
        """Test conversation creation rolls back when participant validation fails."""
        scenario = test_room_with_users
        creator = scenario["users"][0]

        # Count conversations before attempt
        initial_conversations = await conversation_service.get_user_conversations(creator.id)
        initial_count = len(initial_conversations)

        # Attempt to create conversation with non-existent user
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await conversation_service.create_conversation(
                current_user=creator,
                participant_usernames=["nonexistent_user"],
                conversation_type="private"
            )

        assert exc_info.value.status_code == 400
        assert "not found" in str(exc_info.value.detail)

        # Verify no conversation was created (transaction rolled back)
        final_conversations = await conversation_service.get_user_conversations(creator.id)
        final_count = len(final_conversations)
        assert final_count == initial_count

    async def test_room_creation_rollback_on_duplicate_name(self, room_service, room_factory, db_session):
        """Test room creation rolls back on constraint violation."""
        # Create initial room
        existing_room = await room_factory.create(db_session, name="Duplicate Name Room")
        assert existing_room.name == "Duplicate Name Room"

        # Count rooms before attempt
        from app.repositories.room_repository import RoomRepository
        room_repo = RoomRepository(db_session)
        initial_rooms = await room_repo.get_active_rooms()
        initial_count = len(initial_rooms)

        # Attempt to create room with duplicate name
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await room_service.create_room(
                name="Duplicate Name Room",
                description="This should fail",
                max_users=10
            )

        assert exc_info.value.status_code == 409
        assert "already exists" in str(exc_info.value.detail)

        # Verify room count unchanged (transaction rolled back)
        final_rooms = await room_repo.get_active_rooms()
        final_count = len(final_rooms)
        assert final_count == initial_count

    async def test_message_sending_rollback_on_permission_error(self, room_service, user_factory, room_factory, db_session):
        """Test message sending rolls back when user lacks permission."""
        # Create room and users
        room = await room_factory.create(db_session, name="Permission Test Room")
        authorized_user = await user_factory.create(
            db_session,
            username="authorized_user",
            email="auth@test.com",
            current_room_id=room.id
        )
        unauthorized_user = await user_factory.create(
            db_session,
            username="unauthorized_user",
            email="unauth@test.com"
            # Note: not in the room
        )

        # Count messages before attempt
        from app.repositories.message_repository import MessageRepository
        message_repo = MessageRepository(db_session)
        initial_messages, initial_count = await message_repo.get_room_messages(room.id, page=1, page_size=100)

        # Unauthorized user attempts to send message
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await room_service.send_room_message(
                unauthorized_user,
                room.id,
                "This message should be blocked"
            )

        assert exc_info.value.status_code == 403
        assert "must be in room" in str(exc_info.value.detail)

        # Verify no message was created (transaction rolled back)
        final_messages, final_count = await message_repo.get_room_messages(room.id, page=1, page_size=100)
        assert final_count == initial_count


@pytest.mark.integration
class TestConcurrentOperationHandling:
    """Test handling of concurrent operations and race conditions."""

    async def test_concurrent_room_joining_simulation(self, room_service, user_factory, room_factory, db_session):
        """Test simulation of concurrent users joining room."""
        # Create room with limited capacity
        room = await room_factory.create(db_session, name="Concurrent Room", max_users=3)

        # Create multiple users
        users = []
        for i in range(5):
            user = await user_factory.create(
                db_session,
                username=f"concurrent_user_{i}",
                email=f"concurrent_{i}@test.com"
            )
            users.append(user)

        # Simulate concurrent joining (sequential for testing, but validates logic)
        successful_joins = 0
        failed_joins = 0

        for user in users:
            try:
                result = await room_service.join_room(user, room.id)
                successful_joins += 1
                assert result["room_id"] == room.id
            except Exception as e:
                failed_joins += 1
                # Should be room full error
                assert "is full" in str(e.detail) if hasattr(e, 'detail') else True

        # Verify capacity limits were enforced
        assert successful_joins == 3  # Room capacity
        assert failed_joins == 2  # Remaining users

        # Verify room user count
        from app.repositories.room_repository import RoomRepository
        room_repo = RoomRepository(db_session)
        final_user_count = await room_repo.get_user_count(room.id)
        assert final_user_count == 3

    async def test_message_ordering_consistency(self, room_service, user_factory, room_factory, db_session):
        """Test that message ordering remains consistent under load."""
        # Create room and user
        room = await room_factory.create(db_session, name="Ordering Room")
        user = await user_factory.create(
            db_session,
            username="message_sender",
            email="sender@order.test",
            current_room_id=room.id
        )

        # Send multiple messages in sequence
        messages = []
        for i in range(10):
            message = await room_service.send_room_message(
                user,
                room.id,
                f"Ordered message {i+1}"
            )
            messages.append(message)

        # Retrieve messages and verify ordering
        from app.repositories.message_repository import MessageRepository
        message_repo = MessageRepository(db_session)
        retrieved_messages, count = await message_repo.get_room_messages(
            room.id,
            page=1,
            page_size=20
        )

        assert count == 10
        assert len(retrieved_messages) == 10

        # Messages should be ordered by creation time (newest first in this implementation)
        assert retrieved_messages[0].content == "Ordered message 10"
        assert retrieved_messages[9].content == "Ordered message 1"

        # Verify all messages have sequential timestamps
        timestamps = [msg.sent_at for msg in reversed(retrieved_messages)]  # Reverse to get chronological order
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i-1]  # Should be non-decreasing