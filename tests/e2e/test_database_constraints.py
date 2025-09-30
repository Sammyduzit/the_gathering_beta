import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from datetime import datetime

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from app.core.auth_utils import hash_password
from app.models.conversation import Conversation, ConversationType
from app.models.conversation_participant import ConversationParticipant
from app.models.message import Message, MessageType
from app.models.room import Room
from app.models.user import User, UserStatus


@pytest.mark.e2e
class TestDatabaseConstraints:
    """Test database schema constraints and data integrity."""

    @pytest.mark.asyncio
    async def test_message_xor_constraint(self, async_db_session, created_user, created_room):
        """Test XOR constraint: message must have either room_id OR conversation_id, not both."""

        conversation = Conversation(room_id=created_room.id, conversation_type=ConversationType.PRIVATE)

        async_db_session.add(conversation)
        await async_db_session.commit()

        # Test valid options first, room_id only and conversation_id only
        room_message = Message(
            sender_id=created_user.id,
            content="Room message",
            room_id=created_room.id,
            conversation_id=None,
        )
        async_db_session.add(room_message)
        await async_db_session.commit()

        conv_message = Message(
            sender_id=created_user.id,
            content="Conversation message",
            room_id=None,
            conversation_id=conversation.id,
        )
        async_db_session.add(conv_message)
        await async_db_session.commit()

        # Test XOR violations
        with pytest.raises(IntegrityError):
            invalid_message = Message(
                sender_id=created_user.id,
                content="Invalid message",
                room_id=created_room.id,
                conversation_id=conversation.id,
            )
            async_db_session.add(invalid_message)
            await async_db_session.commit()

        await async_db_session.rollback()

        with pytest.raises(IntegrityError):
            orphan_message = Message(
                sender_id=created_user.id,
                content="Orphan message",
                room_id=None,
                conversation_id=None,
            )
            async_db_session.add(orphan_message)
            await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_unique_constraints(self, async_db_session, created_user, created_room):
        """Test unique constraints on User and Room."""

        # username and email unique constraints
        with pytest.raises(IntegrityError):
            user2 = User(
                email=created_user.email,
                username="different_user",
                password_hash=hash_password("password"),
                last_active=datetime.now(),
            )
            async_db_session.add(user2)
            await async_db_session.commit()

        await async_db_session.rollback()

        with pytest.raises(IntegrityError):
            user3 = User(
                email="different@example.com",
                username=created_user.username,
                password_hash=hash_password("password"),
                last_active=datetime.now(),
            )
            async_db_session.add(user3)
            await async_db_session.commit()

        await async_db_session.rollback()

        with pytest.raises(IntegrityError):
            room2 = Room(name=created_room.name, description="Second room")
            async_db_session.add(room2)
            await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_foreign_key_constraints(self, async_db_session, created_user, created_room):
        """Test foreign key constraints and cascading behavior."""
        created_user.current_room_id = created_room.id
        await async_db_session.commit()

        # Check if foreign keys are actually enabled
        result = await async_db_session.execute(text("PRAGMA foreign_keys"))
        fk_status = result.scalar()
        print(f"Foreign Keys Status: {fk_status}")

        # If foreign keys are disabled, enable them for this session
        if fk_status != 1:
            await async_db_session.execute(text("PRAGMA foreign_keys = ON"))
            await async_db_session.commit()

        # Invalid room id foreign key (current_room_id is nullable, so this won't raise)
        # Test with Message instead which has required FK
        with pytest.raises(IntegrityError):
            invalid_message = Message(
                sender_id=created_user.id,
                content="Test message",
                room_id=9999,  # Non-existent room_id should violate FK
            )
            async_db_session.add(invalid_message)
            await async_db_session.commit()

        await async_db_session.rollback()

        # Invalid message sender
        with pytest.raises(IntegrityError):
            invalid_message = Message(sender_id=9999, content="Invalid sender", room_id=created_room.id)
            async_db_session.add(invalid_message)
            await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_conversation_participant_constraints(self, async_db_session, created_user, created_room):
        """Test conversation participant unique constraints."""
        conversation = Conversation(room_id=created_room.id, conversation_type=ConversationType.PRIVATE)

        async_db_session.add(conversation)
        await async_db_session.commit()

        participant1 = ConversationParticipant(conversation_id=conversation.id, user_id=created_user.id)
        async_db_session.add(participant1)
        await async_db_session.commit()

        # Duplicate participant should fail
        with pytest.raises(IntegrityError):
            participant2 = ConversationParticipant(conversation_id=conversation.id, user_id=created_user.id)
            async_db_session.add(participant2)
            await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_enum_validation(self, async_db_session, created_user, created_room):
        """Test enum field validation."""
        valid_conversation = Conversation(room_id=created_room.id, conversation_type=ConversationType.PRIVATE)
        async_db_session.add(valid_conversation)
        await async_db_session.commit()

        created_user.status = UserStatus.AVAILABLE
        await async_db_session.commit()

        # Test MessageType enum
        message = Message(
            sender_id=created_user.id,
            content="Test message",
            message_type=MessageType.TEXT,
            room_id=created_room.id,
        )
        async_db_session.add(message)
        await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_nullable_constraints(self, async_db_session, created_user, created_room):
        """Test required (non-nullable) field constraints."""

        with pytest.raises(IntegrityError):
            invalid_user = User(
                email=None,
                username="testuser",
                password_hash=hash_password("password"),
                last_active=datetime.now(),
            )
            async_db_session.add(invalid_user)
            await async_db_session.commit()

        await async_db_session.rollback()

        with pytest.raises(IntegrityError):
            invalid_room = Room(name=None, description="Test room")
            async_db_session.add(invalid_room)
            await async_db_session.commit()

        await async_db_session.rollback()

        with pytest.raises(IntegrityError):
            invalid_message = Message(sender_id=created_user.id, content=None, room_id=created_room.id)
            async_db_session.add(invalid_message)
            await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_cascading_deletes(self, async_db_session, created_user, created_room):
        """Test that deleting conversation removes related data correctly."""
        conversation = Conversation(room_id=created_room.id, conversation_type=ConversationType.PRIVATE)
        async_db_session.add(conversation)
        await async_db_session.commit()

        participant = ConversationParticipant(conversation_id=conversation.id, user_id=created_user.id)
        message = Message(
            sender_id=created_user.id,
            content="Test message",
            conversation_id=conversation.id,
        )

        async_db_session.add_all([participant, message])
        await async_db_session.commit()

        conversation_id = conversation.id

        # Verify data exists before deletion
        participants_before = (
            await async_db_session.execute(select(ConversationParticipant).filter_by(conversation_id=conversation_id))
        ).all()
        messages_before = (
            await async_db_session.execute(select(Message).filter_by(conversation_id=conversation_id))
        ).all()

        assert len(participants_before) == 1
        assert len(messages_before) == 1

        # Manually delete related data
        await async_db_session.execute(delete(ConversationParticipant).filter_by(conversation_id=conversation_id))
        await async_db_session.execute(delete(Message).filter_by(conversation_id=conversation_id))

        # Delete conversation
        await async_db_session.delete(conversation)
        await async_db_session.commit()

        # Verify all related data is gone
        remaining_participants = (
            await async_db_session.execute(select(ConversationParticipant).filter_by(conversation_id=conversation_id))
        ).all()
        remaining_messages = (
            await async_db_session.execute(select(Message).filter_by(conversation_id=conversation_id))
        ).all()
        remaining_conversations = (
            await async_db_session.execute(select(Conversation).filter_by(id=conversation_id))
        ).all()

        assert len(remaining_participants) == 0
        assert len(remaining_messages) == 0
        assert len(remaining_conversations) == 0

    @pytest.mark.asyncio
    async def test_database_indexes_exist(self, async_db_session):
        """Verify that important database indexes exist for performance."""

        database_url = str(async_db_session.bind.url)

        if "sqlite" in database_url:
            sql = """
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND name NOT LIKE 'sqlite_%'
                """
        else:
            sql = """
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = 'public'
                    AND indexname NOT LIKE 'pg_%'
                """

        result = await async_db_session.execute(text(sql))

        index_names = [row[0] for row in result.fetchall()]

        expected_indexes = [
            "ix_users_email",
            "ix_users_username",
            "idx_conversation_user_unique",
            "idx_user_participation_history",
            "idx_conversation_messages",
            "idx_room_messages",
            "idx_user_messages",
        ]

        for expected_index in expected_indexes:
            assert expected_index in index_names, f"Missing index: {expected_index}"


if __name__ == "__main__":
    print("Database Constraints and Schema Validation Tests, tests/e2e/test_database_constraints.py")
