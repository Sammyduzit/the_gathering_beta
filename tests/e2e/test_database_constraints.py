import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


from app.models.user import User, UserStatus
from app.models.room import Room
from app.models.conversation import Conversation, ConversationType
from app.models.conversation_participant import ConversationParticipant
from app.models.message import Message, MessageType
from app.core.auth_utils import hash_password


class TestDatabaseConstraints:
    """Test database schema constraints and data integrity."""

    def test_message_xor_constraint(self, db_session, created_user, created_room):
        """Test XOR constraint: message must have either room_id OR conversation_id, not both."""

        conversation = Conversation(room_id=created_room.id, conversation_type=ConversationType.PRIVATE)

        db_session.add(conversation)
        db_session.commit()

        # Test valid options first, room_id only and conversation_id only
        room_message = Message(
            sender_id=created_user.id,
            content="Room message",
            room_id=created_room.id,
            conversation_id=None
        )
        db_session.add(room_message)
        db_session.commit()

        conv_message = Message(
            sender_id=created_user.id,
            content="Conversation message",
            room_id=None,
            conversation_id=conversation.id
        )
        db_session.add(conv_message)
        db_session.commit()

        # Test XOR violations
        with pytest.raises(IntegrityError):
            invalid_message = Message(
                sender_id=created_user.id,
                content="Invalid message",
                room_id=created_room.id,
                conversation_id=conversation.id
            )
            db_session.add(invalid_message)
            db_session.commit()

        db_session.rollback()

        with pytest.raises(IntegrityError):
            orphan_message = Message(
                sender_id=created_user.id,
                content="Orphan message",
                room_id=None,
                conversation_id=None
            )
            db_session.add(orphan_message)
            db_session.commit()

    def test_unique_constraints(self, db_session, created_user, created_room):
        """Test unique constraints on User and Room."""

        # username and email unique constraints
        with pytest.raises(IntegrityError):
            user2 = User(
                email=created_user.email,
                username="different_user",
                password_hash=hash_password("password"),
                last_active=datetime.now()
            )
            db_session.add(user2)
            db_session.commit()

        db_session.rollback()

        with pytest.raises(IntegrityError):
            user3 = User(
                email="different@example.com",
                username=created_user.username,
                password_hash=hash_password("password"),
                last_active=datetime.now()
            )
            db_session.add(user3)
            db_session.commit()

        db_session.rollback()

        with pytest.raises(IntegrityError):
            room2 = Room(name=created_room.name, description="Second room")
            db_session.add(room2)
            db_session.commit()

    def test_foreign_key_constraints(self, db_session, created_user, created_room):
        """Test foreign key constraints and cascading behavior."""
        created_user.current_room_id = created_room.id
        db_session.commit()

        # Invalid room id foreign key
        with pytest.raises(IntegrityError):
            created_user.current_room_id = 9999
            db_session.commit()

        db_session.rollback()

        # Invalid message sender
        with pytest.raises(IntegrityError):
            invalid_message = Message(
                sender_id=9999,
                content="Invalid sender",
                room_id=created_room.id
            )
            db_session.add(invalid_message)
            db_session.commit()

    def test_conversation_participant_constraints(self, db_session, created_user, created_room):
        """Test conversation participant unique constraints."""
        conversation = Conversation(room_id=created_room.id, conversation_type=ConversationType.PRIVATE)

        db_session.add(conversation)
        db_session.commit()

        participant1 = ConversationParticipant(
            conversation_id=conversation.id,
            user_id=created_user.id
        )
        db_session.add(participant1)
        db_session.commit()

        # Duplicate participant should fail
        with pytest.raises(IntegrityError):
            participant2 = ConversationParticipant(
                conversation_id=conversation.id,
                user_id=created_user.id
            )
            db_session.add(participant2)
            db_session.commit()

    def test_enum_validation(self, db_session, created_user, created_room):
        """Test enum field validation."""
        valid_conversation = Conversation(
            room_id=created_room.id,
            conversation_type=ConversationType.PRIVATE
        )
        db_session.add(valid_conversation)
        db_session.commit()

        created_user.status = UserStatus.AVAILABLE
        db_session.commit()

        # Test MessageType enum
        message = Message(
            sender_id=created_user.id,
            content="Test message",
            message_type=MessageType.TEXT,
            room_id=created_room.id
        )
        db_session.add(message)
        db_session.commit()

    def test_nullable_constraints(self, db_session, created_user, created_room):
        """Test required (non-nullable) field constraints."""

        with pytest.raises(IntegrityError):
            invalid_user = User(
                email=None,
                username="testuser",
                password_hash=hash_password("password"),
                last_active=datetime.now()
            )
            db_session.add(invalid_user)
            db_session.commit()

        db_session.rollback()

        with pytest.raises(IntegrityError):
            invalid_room = Room(
                name=None,
                description="Test room"
            )
            db_session.add(invalid_room)
            db_session.commit()

        db_session.rollback()

        with pytest.raises(IntegrityError):
            invalid_message = Message(
                sender_id=created_user.id,
                content=None,
                room_id=created_room.id
            )
            db_session.add(invalid_message)
            db_session.commit()

    def test_cascading_deletes(self, db_session, created_user, created_room):
        """Test that deleting conversation removes related data correctly."""
        conversation = Conversation(room_id=created_room.id, conversation_type=ConversationType.PRIVATE)
        db_session.add(conversation)
        db_session.commit()

        participant = ConversationParticipant(
            conversation_id=conversation.id,
            user_id=created_user.id
        )
        message = Message(
            sender_id=created_user.id,
            content="Test message",
            conversation_id=conversation.id
        )

        db_session.add_all([participant, message])
        db_session.commit()

        conversation_id = conversation.id

        # Verify data exists before deletion
        participants_before = db_session.query(ConversationParticipant).filter_by(
            conversation_id=conversation_id
        ).count()
        messages_before = db_session.query(Message).filter_by(
            conversation_id=conversation_id
        ).count()

        assert participants_before == 1
        assert messages_before == 1

        # Manually delete related data
        db_session.query(ConversationParticipant).filter_by(
            conversation_id=conversation_id
        ).delete()
        db_session.query(Message).filter_by(
            conversation_id=conversation_id
        ).delete()

        # Delete conversation
        db_session.delete(conversation)
        db_session.commit()

        # Verify all related data is gone
        remaining_participants = db_session.query(ConversationParticipant).filter_by(
            conversation_id=conversation_id
        ).count()
        remaining_messages = db_session.query(Message).filter_by(
            conversation_id=conversation_id
        ).count()
        remaining_conversations = db_session.query(Conversation).filter_by(
            id=conversation_id
        ).count()

        assert remaining_participants == 0
        assert remaining_messages == 0
        assert remaining_conversations == 0

    def test_database_indexes_exist(self, db_session):
        """Verify that important database indexes exist for performance."""

        result = db_session.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name NOT LIKE 'sqlite_%'
        """))

        index_names = [row[0] for row in result.fetchall()]

        expected_indexes = [
            'ix_users_email',
            'ix_users_username',
            'idx_conversation_user_unique',
            'idx_user_participation_history',
            'idx_conversation_messages',
            'idx_room_messages',
            'idx_user_messages'
        ]

        for expected_index in expected_indexes:
            assert expected_index in index_names, f"Missing index: {expected_index}"


if __name__ == "__main__":
    print("Database Constraints and Schema Validation Tests, tests/e2e/test_database_constraints.py")
