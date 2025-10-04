"""Unit tests for AIContextService."""

import pytest

from app.models.ai_memory import AIMemory
from app.models.message import Message
from app.services.ai_context_service import AIContextService


@pytest.mark.unit
class TestAIContextService:
    """Unit tests for AI context service."""

    @pytest.fixture
    def service(self, mock_message_repo, mock_memory_repo):
        """Create service instance with mocked dependencies from conftest."""
        return AIContextService(
            message_repo=mock_message_repo,
            memory_repo=mock_memory_repo,
        )

    async def test_build_conversation_context(self, service, mock_message_repo, sample_ai_entity, sample_user):
        """Test building conversation context with message history."""
        # Arrange
        msg1 = Message(id=1, content="Hello", sender_user_id=2)
        msg1.sender_user = sample_user

        msg2 = Message(id=2, content="Hi testuser!", sender_ai_id=1)
        msg2.sender_ai = sample_ai_entity

        msg3 = Message(id=3, content="How are you?", sender_user_id=2)
        msg3.sender_user = sample_user

        # get_conversation_messages returns messages in REVERSE chronological order (newest first)
        mock_message_repo.get_conversation_messages.return_value = ([msg3, msg2, msg1], 3)

        # Act
        result = await service.build_conversation_context(
            conversation_id=1,
            ai_entity=sample_ai_entity,
            max_messages=20,
        )

        # Assert
        assert len(result) == 3
        # Messages should be in chronological order after reversal
        assert result[0]["content"] == "testuser: Hello"
        assert result[0]["role"] == "user"
        assert result[1]["content"] == "You: Hi testuser!"  # AI's own message
        assert result[1]["role"] == "user"
        assert result[2]["content"] == "testuser: How are you?"
        assert result[2]["role"] == "user"

        mock_message_repo.get_conversation_messages.assert_called_once_with(
            conversation_id=1,
            page=1,
            page_size=20,
        )

    async def test_build_room_context(self, service, mock_message_repo, sample_ai_entity, sample_user):
        """Test building room context with sender names."""
        # Arrange
        msg1 = Message(id=1, content="Hello room", sender_user_id=2)
        msg1.sender_user = sample_user

        msg2 = Message(id=2, content="Hi everyone!", sender_ai_id=1)
        msg2.sender_ai = sample_ai_entity

        # get_room_messages returns messages in REVERSE chronological order (newest first)
        mock_message_repo.get_room_messages.return_value = ([msg2, msg1], 2)

        # Act
        result = await service.build_room_context(
            room_id=1,
            ai_entity=sample_ai_entity,
            max_messages=20,
        )

        # Assert
        assert len(result) == 2
        assert result[0]["content"] == "testuser: Hello room"
        assert result[0]["role"] == "user"
        assert result[1]["content"] == "You: Hi everyone!"  # AI's own message
        assert result[1]["role"] == "user"

        mock_message_repo.get_room_messages.assert_called_once_with(
            room_id=1,
            page=1,
            page_size=20,
        )

    async def test_get_ai_memories(self, service, mock_memory_repo):
        """Test retrieving AI memories formatted as context."""
        # Arrange
        mem1 = AIMemory(
            id=1, entity_id=1, summary="User likes programming", memory_content={}, importance_score=3.0
        )
        mem2 = AIMemory(id=2, entity_id=1, summary="User mentioned cats", memory_content={}, importance_score=1.0)

        mock_memory_repo.get_entity_memories.return_value = [mem1, mem2]

        # Act
        result = await service.get_ai_memories(ai_entity_id=1, max_entries=10)

        # Assert
        assert "# Previous Memories:" in result
        assert "!!! User likes programming" in result  # 3 exclamation marks
        assert "! User mentioned cats" in result  # 1 exclamation mark

        mock_memory_repo.get_entity_memories.assert_called_once_with(
            entity_id=1,
            limit=10,
            order_by_importance=True,
        )

    async def test_get_ai_memories_empty(self, service, mock_memory_repo):
        """Test retrieving memories when none exist."""
        # Arrange
        mock_memory_repo.get_entity_memories.return_value = []

        # Act
        result = await service.get_ai_memories(ai_entity_id=1)

        # Assert
        assert result == ""

    async def test_build_full_context_conversation(
        self, service, mock_message_repo, mock_memory_repo, sample_ai_entity, sample_user
    ):
        """Test building full context for conversation with memories."""
        # Arrange
        msg = Message(id=1, content="Hello", sender_user_id=2)
        msg.sender_user = sample_user
        mock_message_repo.get_conversation_messages.return_value = ([msg], 1)

        mem = AIMemory(id=1, entity_id=1, summary="Test memory", memory_content={}, importance_score=2.0)
        mock_memory_repo.get_entity_memories.return_value = [mem]

        # Act
        messages, memory_context = await service.build_full_context(
            conversation_id=1,
            room_id=None,
            ai_entity=sample_ai_entity,
            include_memories=True,
        )

        # Assert
        assert len(messages) == 1
        assert messages[0]["content"] == "testuser: Hello"
        assert memory_context is not None
        assert "!! Test memory" in memory_context

    async def test_build_full_context_room(
        self, service, mock_message_repo, mock_memory_repo, sample_ai_entity, sample_user
    ):
        """Test building full context for room."""
        # Arrange
        msg = Message(id=1, content="Hello room", sender_user_id=2)
        msg.sender_user = sample_user
        mock_message_repo.get_room_messages.return_value = ([msg], 1)

        mock_memory_repo.get_entity_memories.return_value = []

        # Act
        messages, memory_context = await service.build_full_context(
            conversation_id=None,
            room_id=1,
            ai_entity=sample_ai_entity,
            include_memories=True,
        )

        # Assert
        assert len(messages) == 1
        assert messages[0]["content"] == "testuser: Hello room"
        assert memory_context == ""  # No memories

    async def test_build_full_context_no_memories(
        self, service, mock_message_repo, mock_memory_repo, sample_ai_entity, sample_user
    ):
        """Test building context without memories when disabled."""
        # Arrange
        msg = Message(id=1, content="Hello", sender_user_id=2)
        msg.sender_user = sample_user
        mock_message_repo.get_conversation_messages.return_value = ([msg], 1)

        # Act
        messages, memory_context = await service.build_full_context(
            conversation_id=1,
            room_id=None,
            ai_entity=sample_ai_entity,
            include_memories=False,
        )

        # Assert
        assert len(messages) == 1
        assert memory_context is None
        mock_memory_repo.get_entity_memories.assert_not_called()

    async def test_build_full_context_requires_id(self, service, sample_ai_entity):
        """Test that build_full_context requires either conversation_id or room_id."""
        # Act & Assert
        with pytest.raises(ValueError, match="Either conversation_id or room_id must be provided"):
            await service.build_full_context(
                conversation_id=None,
                room_id=None,
                ai_entity=sample_ai_entity,
            )
