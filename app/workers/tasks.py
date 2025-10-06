"""ARQ task functions for AI response generation."""

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from arq import Retry

from app.core.arq_db_manager import ARQDatabaseManager, db_session_context
from app.core.config import settings
from app.interfaces.ai_provider import AIProviderError
from app.models.ai_entity import AIEntity
from app.providers.openai_provider import OpenAIProvider
from app.repositories.ai_entity_repository import AIEntityRepository
from app.repositories.ai_memory_repository import AIMemoryRepository
from app.repositories.message_repository import MessageRepository
from app.services.ai_context_service import AIContextService
from app.services.ai_response_service import AIResponseService

logger = structlog.get_logger(__name__)


async def generate_ai_room_response(
    ctx: dict,
    room_id: int,
    ai_entity_id: int,
    in_reply_to_message_id: int | None = None,
) -> dict:
    """
    ARQ task: Generate AI response for a room message.

    Args:
        ctx: ARQ context with db_manager
        room_id: Room ID to respond in
        ai_entity_id: AI entity that should respond
        in_reply_to_message_id: Optional message to reply to

    Returns:
        Dict with message_id and ai_entity_id

    Raises:
        Retry: On transient errors (max 3 attempts)
    """
    job_id = str(uuid4())
    db_session_context.set(job_id)

    db_manager: ARQDatabaseManager = ctx["db_manager"]

    try:
        async for session in db_manager.get_session():
            ai_entity_repo = AIEntityRepository(session)
            message_repo = MessageRepository(session)
            memory_repo = AIMemoryRepository(session)

            ai_entity = await ai_entity_repo.get_by_id(ai_entity_id)
            if not ai_entity:
                logger.error(f"AI entity {ai_entity_id} not found")
                return {"error": "AI entity not found"}

            from app.models.ai_entity import AIEntityStatus

            if ai_entity.status != AIEntityStatus.ONLINE:
                logger.warning(f"AI entity {ai_entity_id} is not active, skipping")
                return {"skipped": "AI entity not active"}

            ai_provider = OpenAIProvider(
                api_key=settings.openai_api_key,
                model_name=ai_entity.model_name or "gpt-4o-mini",
            )
            context_service = AIContextService(message_repo, memory_repo)
            response_service = AIResponseService(
                ai_provider=ai_provider,
                context_service=context_service,
                message_repo=message_repo,
            )

            message = await response_service.generate_room_response(
                room_id=room_id,
                ai_entity=ai_entity,
                include_memories=True,
            )

            logger.info(
                f"AI '{ai_entity.name}' generated room response {message.id} in room {room_id}"
            )

            return {
                "message_id": message.id,
                "ai_entity_id": ai_entity_id,
                "room_id": room_id,
            }

    except AIProviderError as e:
        logger.error(f"AI provider error in room {room_id}: {e}")
        raise Retry(defer=ctx["job_try"] * 5)

    except Exception as e:
        logger.exception(f"Unexpected error generating AI room response: {e}")
        raise Retry(defer=ctx["job_try"] * 5)


async def generate_ai_conversation_response(
    ctx: dict,
    conversation_id: int,
    ai_entity_id: int,
    in_reply_to_message_id: int | None = None,
) -> dict:
    """
    ARQ task: Generate AI response for a conversation message.

    Args:
        ctx: ARQ context with db_manager
        conversation_id: Conversation ID to respond in
        ai_entity_id: AI entity that should respond
        in_reply_to_message_id: Optional message to reply to

    Returns:
        Dict with message_id and ai_entity_id

    Raises:
        Retry: On transient errors (max 3 attempts)
    """
    job_id = str(uuid4())
    db_session_context.set(job_id)

    db_manager: ARQDatabaseManager = ctx["db_manager"]

    try:
        async for session in db_manager.get_session():
            ai_entity_repo = AIEntityRepository(session)
            message_repo = MessageRepository(session)
            memory_repo = AIMemoryRepository(session)

            ai_entity = await ai_entity_repo.get_by_id(ai_entity_id)
            if not ai_entity:
                logger.error(f"AI entity {ai_entity_id} not found")
                return {"error": "AI entity not found"}

            from app.models.ai_entity import AIEntityStatus

            if ai_entity.status != AIEntityStatus.ONLINE:
                logger.warning(f"AI entity {ai_entity_id} is not active, skipping")
                return {"skipped": "AI entity not active"}

            ai_provider = OpenAIProvider(
                api_key=settings.openai_api_key,
                model_name=ai_entity.model_name or "gpt-4o-mini",
            )
            context_service = AIContextService(message_repo, memory_repo)
            response_service = AIResponseService(
                ai_provider=ai_provider,
                context_service=context_service,
                message_repo=message_repo,
            )

            message = await response_service.generate_conversation_response(
                conversation_id=conversation_id,
                ai_entity=ai_entity,
                include_memories=True,
            )

            logger.info(
                f"AI '{ai_entity.name}' generated conversation response {message.id} in conversation {conversation_id}"
            )

            return {
                "message_id": message.id,
                "ai_entity_id": ai_entity_id,
                "conversation_id": conversation_id,
            }

    except AIProviderError as e:
        logger.error(f"AI provider error in conversation {conversation_id}: {e}")
        raise Retry(defer=ctx["job_try"] * 5)

    except Exception as e:
        logger.exception(f"Unexpected error generating AI conversation response: {e}")
        raise Retry(defer=ctx["job_try"] * 5)
