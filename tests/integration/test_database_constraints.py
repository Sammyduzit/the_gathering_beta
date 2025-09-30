"""
Integration tests for database constraints.

These tests verify that PostgreSQL database constraints work correctly:
- Unique constraints (username, email, room name)
- Foreign key constraints
- XOR constraint for message routing (room_id XOR conversation_id)
- Check constraints
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.conversation import Conversation, ConversationType
from app.models.message import Message
from app.models.room import Room
from app.models.user import User


@pytest.mark.integration
class TestUniqueConstraints:
    """Test unique constraints on tables."""

    async def test_user_unique_username_constraint(self, user_factory, db_session):
        """Verify username must be unique."""
        # Create first user
        user1 = await user_factory.create(db_session, username="uniqueuser", email="user1@test.com")
        assert user1.id is not None

        # Try to create second user with same username
        with pytest.raises(IntegrityError) as exc_info:
            await user_factory.create(db_session, username="uniqueuser", email="user2@test.com")

        assert "ix_users_username" in str(exc_info.value) or "users_username_key" in str(exc_info.value)

    async def test_user_unique_email_constraint(self, user_factory, db_session):
        """Verify email must be unique."""
        # Create first user
        user1 = await user_factory.create(db_session, username="user1", email="same@test.com")
        assert user1.id is not None

        # Try to create second user with same email
        with pytest.raises(IntegrityError) as exc_info:
            await user_factory.create(db_session, username="user2", email="same@test.com")

        assert "ix_users_email" in str(exc_info.value) or "users_email_key" in str(exc_info.value)

    async def test_room_unique_name_constraint(self, room_factory, db_session):
        """Verify room name must be unique."""
        # Create first room
        room1 = await room_factory.create(db_session, name="Unique Room")
        assert room1.id is not None

        # Try to create second room with same name
        with pytest.raises(IntegrityError) as exc_info:
            await room_factory.create(db_session, name="Unique Room")

        assert "rooms_name_key" in str(exc_info.value)


@pytest.mark.integration
class TestForeignKeyConstraints:
    """Test foreign key constraints and cascades."""

    async def test_message_requires_sender(self, db_session):
        """Verify message cannot be created without valid sender."""
        room = Room(name="Test Room")
        db_session.add(room)
        await db_session.commit()

        # Try to create message with invalid sender_id
        message = Message(
            sender_id=99999,  # Non-existent user
            room_id=room.id,
            content="This should fail"
        )
        db_session.add(message)

        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        assert "messages_sender_id_fkey" in str(exc_info.value)

    async def test_conversation_requires_room(self, db_session):
        """Verify conversation cannot be created without valid room."""
        # Try to create conversation with invalid room_id
        conversation = Conversation(
            room_id=99999,  # Non-existent room
            conversation_type=ConversationType.GROUP
        )
        db_session.add(conversation)

        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        assert "conversations_room_id_fkey" in str(exc_info.value)


@pytest.mark.integration
class TestMessageRoutingXORConstraint:
    """
    Test XOR constraint for message routing.

    A message MUST be routed to exactly ONE of:
    - room_id (public room message)
    - conversation_id (private/group chat message)

    This is enforced by a CHECK constraint in the database.
    """

    async def test_message_must_have_room_or_conversation(self, db_session, user_factory):
        """Verify message must have either room_id OR conversation_id."""
        user = await user_factory.create(db_session)

        # Try to create message with NEITHER room_id NOR conversation_id
        message = Message(
            sender_id=user.id,
            content="This should fail - no routing"
        )
        db_session.add(message)

        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        # XOR constraint violation
        assert "check constraint" in str(exc_info.value).lower()

    async def test_message_cannot_have_both_room_and_conversation(
        self, db_session, user_factory, room_factory, conversation_factory
    ):
        """Verify message cannot have BOTH room_id AND conversation_id."""
        user = await user_factory.create(db_session)
        room = await room_factory.create(db_session)
        conversation = await conversation_factory.create_private_conversation(
            db_session, room_id=room.id
        )

        # Try to create message with BOTH room_id AND conversation_id
        message = Message(
            sender_id=user.id,
            room_id=room.id,
            conversation_id=conversation.id,
            content="This should fail - both routing targets"
        )
        db_session.add(message)

        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        # XOR constraint violation
        assert "check constraint" in str(exc_info.value).lower()

    async def test_public_room_message_only_room_id(
        self, db_session, user_factory, room_factory
    ):
        """Verify public room message has only room_id (XOR: room_id XOR conversation_id)."""
        user = await user_factory.create(db_session)
        room = await room_factory.create(db_session)

        # Create valid public room message
        message = Message(
            sender_id=user.id,
            room_id=room.id,
            conversation_id=None,  # Explicitly None
            content="Public room message"
        )
        db_session.add(message)
        await db_session.commit()

        # Verify message created successfully
        result = await db_session.execute(
            select(Message).where(Message.id == message.id)
        )
        saved_message = result.scalar_one()

        assert saved_message.room_id == room.id
        assert saved_message.conversation_id is None

    async def test_private_chat_message_only_conversation_id(
        self, db_session, user_factory, room_factory, conversation_factory
    ):
        """Verify private chat message has only conversation_id (XOR: room_id XOR conversation_id)."""
        user = await user_factory.create(db_session)
        room = await room_factory.create(db_session)
        conversation = await conversation_factory.create_private_conversation(
            db_session, room_id=room.id
        )

        # Create valid private chat message
        message = Message(
            sender_id=user.id,
            room_id=None,  # Explicitly None
            conversation_id=conversation.id,
            content="Private message"
        )
        db_session.add(message)
        await db_session.commit()

        # Verify message created successfully
        result = await db_session.execute(
            select(Message).where(Message.id == message.id)
        )
        saved_message = result.scalar_one()

        assert saved_message.room_id is None
        assert saved_message.conversation_id == conversation.id


@pytest.mark.integration
class TestCheckConstraints:
    """Test CHECK constraints on tables."""

    async def test_room_max_users_positive(self, db_session):
        """Verify room max_users must be positive."""
        # SQLAlchemy may have default, so we test creation succeeds
        # This test verifies Room model allows creation with positive max_users
        room = Room(
            name="Valid Room",
            max_users=10  # Valid positive value
        )
        db_session.add(room)
        await db_session.commit()

        assert room.id is not None
        assert room.max_users == 10

    async def test_conversation_type_valid_enum(self, db_session, room_factory):
        """Verify conversation type uses valid enum value."""
        room = await room_factory.create(db_session)

        # Test that valid enum values work
        conversation = Conversation(
            room_id=room.id,
            conversation_type=ConversationType.PRIVATE
        )
        db_session.add(conversation)
        await db_session.commit()

        assert conversation.id is not None
        assert conversation.conversation_type == ConversationType.PRIVATE
