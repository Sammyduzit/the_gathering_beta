"""ARQ task functions for AI response generation."""

from uuid import uuid4

import structlog
from arq import Retry

from app.core.arq_db_manager import ARQDatabaseManager, db_session_context
from app.core.config import settings
from app.interfaces.ai_provider import AIProviderError
from app.interfaces.keyword_extractor import KeywordExtractionError
from app.interfaces.memory_summarizer import MemorySummarizationError
from app.models.ai_entity import AIEntity, AIEntityStatus
from app.providers.openai_provider import OpenAIProvider
from app.repositories.ai_entity_repository import AIEntityRepository
from app.repositories.ai_memory_repository import AIMemoryRepository
from app.repositories.message_repository import MessageRepository
from app.services.ai_context_service import AIContextService
from app.services.ai_response_service import AIResponseService
from app.services.heuristic_summarizer import HeuristicMemorySummarizer
from app.services.keyword_retriever import KeywordMemoryRetriever
from app.services.long_term_memory_service import LongTermMemoryService
from app.services.memory_builder_service import MemoryBuilderService
from app.services.openai_embedding_service import OpenAIEmbeddingService
from app.services.short_term_memory_service import ShortTermMemoryService
from app.services.text_chunking_service import TextChunkingService
from app.services.yake_extractor import YakeKeywordExtractor

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

            # Initialize memory retriever for context service
            memory_retriever = KeywordMemoryRetriever(memory_repo=memory_repo)
            context_service = AIContextService(
                message_repo=message_repo,
                memory_repo=memory_repo,
                memory_retriever=memory_retriever,
            )

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

            # Create short-term memory after AI response (inline, fast)
            if conversation_id and message.sender_user_id:
                try:
                    short_term_service = ShortTermMemoryService(memory_repo=memory_repo)

                    # Get recent messages for memory creation
                    recent_messages = await message_repo.get_conversation_messages(
                        conversation_id=conversation_id,
                        limit=20,
                    )

                    await short_term_service.create_short_term_memory(
                        entity_id=ai_entity.id,
                        user_id=message.sender_user_id,
                        conversation_id=conversation_id,
                        messages=recent_messages,
                    )

                    logger.debug(
                        "short_term_memory_created",
                        ai_entity_id=ai_entity.id,
                        user_id=message.sender_user_id,
                        conversation_id=conversation_id,
                    )
                except Exception as e:
                    # Non-critical: log warning, don't fail the task
                    logger.warning(
                        "short_term_memory_creation_failed",
                        error=str(e),
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


async def create_conversation_memory_task(
    ctx: dict,
    ai_entity_id: int,
    conversation_id: int,
    trigger_message_id: int,
) -> dict:
    """
    ARQ task: Create conversation memory after AI response.

    This is a **fire-and-forget** background task that doesn't block AI responses.
    Non-critical: Logs warning on failure, no retry.

    Args:
        ctx: ARQ context with db_manager
        ai_entity_id: AI entity ID that owns the memory
        conversation_id: Conversation ID to create memory from
        trigger_message_id: Message ID that triggered memory creation

    Returns:
        Dict with memory_id and keywords on success, or error on failure
    """
    job_id = str(uuid4())
    db_session_context.set(job_id)

    db_manager: ARQDatabaseManager = ctx["db_manager"]

    try:
        async for session in db_manager.get_session():
            message_repo = MessageRepository(session)
            memory_repo = AIMemoryRepository(session)
            entity_repo = AIEntityRepository(session)

            # Initialize memory builder service with default implementations
            keyword_extractor = YakeKeywordExtractor()
            summarizer = HeuristicMemorySummarizer()

            memory_builder = MemoryBuilderService(
                message_repo=message_repo,
                memory_repo=memory_repo,
                entity_repo=entity_repo,
                keyword_extractor=keyword_extractor,
                summarizer=summarizer,
            )

            # Create memory
            memory = await memory_builder.create_conversation_memory(
                ai_entity_id=ai_entity_id,
                conversation_id=conversation_id,
                trigger_message_id=trigger_message_id,
            )

            logger.info(
                "conversation_memory_created",
                memory_id=memory.id,
                ai_entity_id=ai_entity_id,
                conversation_id=conversation_id,
                keywords=memory.keywords,
            )

            return {
                "memory_id": memory.id,
                "keywords": memory.keywords,
                "importance_score": memory.importance_score,
            }

    except (KeywordExtractionError, MemorySummarizationError) as e:
        # Non-critical errors: log warning, don't retry
        logger.warning(
            "memory_creation_failed",
            error=str(e),
            ai_entity_id=ai_entity_id,
            conversation_id=conversation_id,
            reason="Extraction or summarization error",
        )
        return {"error": str(e), "skipped": True}

    except Exception as e:
        # Unexpected errors: log error, don't retry (non-critical task)
        logger.error(
            "unexpected_error_creating_memory",
            error=str(e),
            ai_entity_id=ai_entity_id,
            conversation_id=conversation_id,
        )
        return {"error": str(e), "skipped": True}


async def create_long_term_memory_task(
    ctx: dict,
    ai_entity_id: int,
    user_id: int,
    conversation_id: int,
) -> dict:
    """
    ARQ task: Create long-term memory archive from finalized conversation.

    This task:
    - Fetches ALL messages from conversation
    - Chunks text
    - Generates embeddings (batch)
    - Creates multiple AIMemory entries (one per chunk)

    Args:
        ctx: ARQ context with db_manager
        ai_entity_id: AI entity ID
        user_id: User ID for user-specific memory
        conversation_id: Conversation ID to archive

    Returns:
        Dict with memory count and IDs on success
    """
    job_id = str(uuid4())
    db_session_context.set(job_id)

    db_manager: ARQDatabaseManager = ctx["db_manager"]

    try:
        async for session in db_manager.get_session():
            message_repo = MessageRepository(session)
            memory_repo = AIMemoryRepository(session)

            # Initialize services
            embedding_service = OpenAIEmbeddingService(
                api_key=settings.openai_api_key,
                model=settings.embedding_model,
                dimensions=settings.embedding_dimensions,
            )
            chunking_service = TextChunkingService()
            long_term_service = LongTermMemoryService(
                memory_repo=memory_repo,
                message_repo=message_repo,
                embedding_service=embedding_service,
                chunking_service=chunking_service,
            )

            # Create long-term archive
            memories = await long_term_service.create_long_term_archive(
                entity_id=ai_entity_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )

            logger.info(
                "long_term_memory_created",
                ai_entity_id=ai_entity_id,
                user_id=user_id,
                conversation_id=conversation_id,
                memory_count=len(memories),
            )

            return {
                "memory_count": len(memories),
                "memory_ids": [m.id for m in memories],
            }

    except Exception as e:
        logger.error(
            "long_term_memory_creation_failed",
            error=str(e),
            ai_entity_id=ai_entity_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        raise Retry(defer=ctx["job_try"] * 10)  # Retry with backoff
