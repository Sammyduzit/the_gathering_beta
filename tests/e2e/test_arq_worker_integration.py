"""End-to-end integration tests for ARQ worker tasks."""

import pytest
import openai_responses
from uuid import uuid4

from app.core.arq_db_manager import ARQDatabaseManager, db_session_context
from app.workers.tasks import generate_ai_conversation_response, generate_ai_room_response


@pytest.mark.skip(reason="TODO: Fix openai-responses mocking for LangChain ChatOpenAI")
@openai_responses.mock()
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_generate_ai_room_response_task(created_room, created_ai_entity):
    """Test ARQ task generates AI response for room message with mocked OpenAI."""
    db_manager = ARQDatabaseManager()
    await db_manager.connect()

    job_id = str(uuid4())
    db_session_context.set(job_id)

    ctx = {"db_manager": db_manager, "job_try": 1}

    result = await generate_ai_room_response(
        ctx=ctx,
        room_id=created_room.id,
        ai_entity_id=created_ai_entity.id,
    )

    assert "message_id" in result
    assert result["ai_entity_id"] == created_ai_entity.id
    assert result["room_id"] == created_room.id

    await db_manager.disconnect()


@pytest.mark.skip(reason="TODO: Fix openai-responses mocking for LangChain ChatOpenAI")
@openai_responses.mock()
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_generate_ai_conversation_response_task(created_conversation, created_ai_entity):
    """Test ARQ task generates AI response for conversation with mocked OpenAI."""
    db_manager = ARQDatabaseManager()
    await db_manager.connect()

    job_id = str(uuid4())
    db_session_context.set(job_id)

    ctx = {"db_manager": db_manager, "job_try": 1}

    result = await generate_ai_conversation_response(
        ctx=ctx,
        conversation_id=created_conversation.id,
        ai_entity_id=created_ai_entity.id,
    )

    assert "message_id" in result
    assert result["ai_entity_id"] == created_ai_entity.id
    assert result["conversation_id"] == created_conversation.id

    await db_manager.disconnect()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_room_response_skips_inactive_entity(created_room, created_ai_entity, async_db_session):
    """Test ARQ task skips response if AI entity is inactive."""
    from app.models.ai_entity import AIEntityStatus
    from app.repositories.ai_entity_repository import AIEntityRepository
    from sqlalchemy import select

    # Re-fetch entity in current session
    ai_repo = AIEntityRepository(async_db_session)
    ai_entity = await async_db_session.scalar(
        select(type(created_ai_entity)).where(type(created_ai_entity).id == created_ai_entity.id)
    )

    # Set AI entity to inactive
    ai_entity.status = AIEntityStatus.OFFLINE
    await ai_repo.update(ai_entity)

    db_manager = ARQDatabaseManager()
    await db_manager.connect()

    job_id = str(uuid4())
    db_session_context.set(job_id)

    ctx = {"db_manager": db_manager, "job_try": 1}

    result = await generate_ai_room_response(
        ctx=ctx,
        room_id=created_room.id,
        ai_entity_id=created_ai_entity.id,
    )

    assert "skipped" in result
    assert result["skipped"] == "AI entity not active"

    await db_manager.disconnect()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_response_handles_nonexistent_entity(created_room):
    """Test ARQ task handles nonexistent AI entity gracefully."""
    db_manager = ARQDatabaseManager()
    await db_manager.connect()

    job_id = str(uuid4())
    db_session_context.set(job_id)

    ctx = {"db_manager": db_manager, "job_try": 1}

    result = await generate_ai_room_response(
        ctx=ctx,
        room_id=created_room.id,
        ai_entity_id=99999,
    )

    assert "error" in result
    assert result["error"] == "AI entity not found"

    await db_manager.disconnect()
