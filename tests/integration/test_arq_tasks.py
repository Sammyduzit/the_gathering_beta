"""Integration tests for ARQ worker tasks."""

import pytest

from app.models.ai_entity import AIEntity, AIEntityStatus, AIResponseStrategy
from app.repositories.ai_memory_repository import AIMemoryRepository
from app.workers.tasks import create_conversation_memory_task
from tests.fixtures import ConversationFactory, MessageFactory, RoomFactory, UserFactory


class DummyDBManager:
    """Minimal db_manager stub exposing get_session for ARQ task context."""

    def __init__(self, session):
        self._session = session

    async def get_session(self):
        yield self._session


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_conversation_memory_task(db_session):
    """Ensure ARQ task persists a conversation memory in the database."""
    room = await RoomFactory.create(db_session)
    conversation = await ConversationFactory.create_private_conversation(db_session, room=room)
    user = await UserFactory.create(db_session)

    ai_entity = AIEntity(
        username="arq_tester",
        description="Integration AI",
        system_prompt="Summarize conversations for testing.",
        model_name="gpt-4o-mini",
        temperature=0.7,
        max_tokens=256,
        status=AIEntityStatus.ONLINE,
        room_response_strategy=AIResponseStrategy.ROOM_MENTION_ONLY,
        conversation_response_strategy=AIResponseStrategy.CONV_ON_QUESTIONS,
    )
    db_session.add(ai_entity)
    await db_session.commit()
    await db_session.refresh(ai_entity)

    # Seed conversation messages
    last_message = await MessageFactory.create_conversation_message(
        db_session,
        sender=user,
        conversation=conversation,
        content="Testing ARQ memory creation.",
    )

    ctx = {"db_manager": DummyDBManager(db_session)}

    result = await create_conversation_memory_task(
        ctx=ctx,
        ai_entity_id=ai_entity.id,
        conversation_id=conversation.id,
        trigger_message_id=last_message.id,
    )

    assert "memory_id" in result
    assert result["memory_id"] is not None

    memory_repo = AIMemoryRepository(db_session)
    stored_memory = await memory_repo.get_by_id(result["memory_id"])

    assert stored_memory is not None
    assert stored_memory.entity_id == ai_entity.id
    assert stored_memory.conversation_id == conversation.id
    assert stored_memory.summary
