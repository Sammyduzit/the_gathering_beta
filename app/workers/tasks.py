"""ARQ task functions for AI response generation."""

from uuid import uuid4

import structlog
from arq import Retry

from app.core.arq_db_manager import ARQDatabaseManager, db_session_context
from app.core.config import settings
from app.interfaces.ai_provider import AIProviderError
from app.models.ai_entity import AIEntity, AIEntityStatus
from app.providers.openai_provider import OpenAIProvider
from app.repositories.ai_entity_repository import AIEntityRepository
from app.repositories.ai_memory_repository import AIMemoryRepository
from app.repositories.message_repository import MessageRepository
from app.services.ai_context_service import AIContextService
from app.services.ai_response_service import AIResponseService

logger = structlog.get_logger(__name__)


def _validate_ai_can_respond(ai_entity: AIEntity, room_id: int | None) -> bool:
    """
    Validate that AI entity can respond in current context.

    Args:
        ai_entity: AI entity to validate
        room_id: Room ID if responding in room (None for conversations)

    Returns:
        True if AI can respond, False otherwise
    """
    # Check AI is ONLINE
    if ai_entity.status != AIEntityStatus.ONLINE:
        logger.warning(
            "ai_validation_failed",
            ai_entity_id=ai_entity.id,
            reason="AI not ONLINE",
            status=ai_entity.status,
        )
        return False

    # Check AI is still in room (if room_id provided)
    if room_id and ai_entity.current_room_id != room_id:
        logger.warning(
            "ai_validation_failed",
            ai_entity_id=ai_entity.id,
            reason="AI no longer in room",
            expected_room=room_id,
            actual_room=ai_entity.current_room_id,
        )
        return False

    return True


async def check_and_generate_ai_response(
    ctx: dict,
    message_id: int,
    room_id: int | None = None,
    conversation_id: int | None = None,
    ai_entity_id: int | None = None,
) -> dict:
    """
    Unified ARQ task: Check if AI should respond and generate response if needed.

    This task handles race conditions by:
    1. PRE-CHECK: Validate AI status and room presence before generation
    2. Strategy check: Use should_ai_respond() to check response strategy
    3. Generation: Generate response (5-30s)
    4. POST-CHECK: Re-validate AI still active before saving

    Args:
        ctx: ARQ context with db_manager
        message_id: Message ID that triggered this check
        room_id: Room ID (for room messages)
        conversation_id: Conversation ID (for conversation messages)
        ai_entity_id: AI entity ID (optional, can be looked up from room/conversation)

    Returns:
        Dict with ai_message_id on success or skipped reason

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

            # Get AI entity (from ID or lookup)
            ai_entity = None
            if ai_entity_id:
                ai_entity = await ai_entity_repo.get_by_id(ai_entity_id)
            elif room_id:
                ai_entity = await ai_entity_repo.get_ai_in_room(room_id)
            elif conversation_id:
                ai_entity = await ai_entity_repo.get_ai_in_conversation(conversation_id)

            if not ai_entity:
                logger.info(
                    "ai_response_skipped",
                    reason="No AI entity found",
                    room_id=room_id,
                    conversation_id=conversation_id,
                )
                return {"skipped": "No AI entity found"}

            # PRE-CHECK: Validate AI can respond (prevents race conditions)
            if not _validate_ai_can_respond(ai_entity, room_id):
                return {"skipped": "AI validation failed (pre-check)"}

            # Get the message that triggered this check
            message = await message_repo.get_by_id(message_id)
            if not message:
                logger.error("message_not_found", message_id=message_id)
                return {"error": "Message not found"}

            # Initialize AI provider and services
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

            # Check if AI should respond based on strategy
            should_respond = await response_service.should_ai_respond(
                ai_entity=ai_entity,
                latest_message=message,
                conversation_id=conversation_id,
                room_id=room_id,
            )

            if not should_respond:
                logger.info(
                    "ai_response_skipped",
                    reason="Strategy check failed",
                    ai_entity_id=ai_entity.id,
                    room_id=room_id,
                    conversation_id=conversation_id,
                )
                return {"skipped": "Strategy check failed"}

            # Generate response (5-30s duration)
            if room_id:
                ai_message = await response_service.generate_room_response(
                    room_id=room_id,
                    ai_entity=ai_entity,
                    include_memories=True,
                    in_reply_to_message_id=message_id,
                )
            else:
                ai_message = await response_service.generate_conversation_response(
                    conversation_id=conversation_id,
                    ai_entity=ai_entity,
                    include_memories=True,
                    in_reply_to_message_id=message_id,
                )

            # POST-CHECK: Re-validate AI still active (prevents race conditions)
            await session.refresh(ai_entity)
            if not _validate_ai_can_respond(ai_entity, room_id):
                # AI was set offline or left room during generation
                # Delete the generated message
                await message_repo.delete(ai_message.id)
                logger.warning(
                    "ai_response_cancelled",
                    reason="AI validation failed after generation (post-check)",
                    ai_entity_id=ai_entity.id,
                )
                return {"skipped": "AI validation failed (post-check)"}

            logger.info(
                "ai_response_generated",
                ai_entity_id=ai_entity.id,
                ai_message_id=ai_message.id,
                room_id=room_id,
                conversation_id=conversation_id,
            )

            return {
                "ai_message_id": ai_message.id,
                "ai_entity_id": ai_entity.id,
                "room_id": room_id,
                "conversation_id": conversation_id,
            }

    except AIProviderError as e:
        logger.error(
            "ai_provider_error",
            error=str(e),
            room_id=room_id,
            conversation_id=conversation_id,
        )
        raise Retry(defer=ctx["job_try"] * 5)

    except Exception as e:
        logger.exception(
            "unexpected_error_generating_ai_response",
            error=str(e),
            room_id=room_id,
            conversation_id=conversation_id,
        )
        raise Retry(defer=ctx["job_try"] * 5)
