"""
Dependency injection for AI-related services.

Provides factory functions for AI service instances with proper dependency wiring.
"""

import logging

from app.dependencies.provider_dependencies import get_ai_provider
from app.repositories.ai_cooldown_repository import AICooldownRepository
from app.repositories.ai_memory_repository import AIMemoryRepository
from app.repositories.message_repository import MessageRepository
from app.services.ai_context_service import AIContextService
from app.services.ai_response_service import AIResponseService
from app.services.keyword_retriever import KeywordMemoryRetriever

logger = logging.getLogger(__name__)


def get_ai_context_service(
    message_repo: MessageRepository,
    memory_repo: AIMemoryRepository,
) -> AIContextService:
    """
    Get AIContextService instance with injected dependencies.

    Args:
        message_repo: Message repository for retrieving conversation history
        memory_repo: AI memory repository for retrieving AI memories

    Returns:
        Configured AIContextService instance with memory retriever
    """
    # Initialize memory retriever with repository
    memory_retriever = KeywordMemoryRetriever(memory_repo=memory_repo)

    return AIContextService(
        message_repo=message_repo,
        memory_repo=memory_repo,
        memory_retriever=memory_retriever,
    )


def get_ai_response_service(
    context_service: AIContextService,
    message_repo: MessageRepository,
    cooldown_repo: AICooldownRepository,
) -> AIResponseService | None:
    """
    Get AIResponseService instance with injected dependencies.

    Args:
        context_service: AI context service for building conversation context
        message_repo: Message repository for saving AI responses
        cooldown_repo: AI cooldown repository for rate limiting

    Returns:
        Configured AIResponseService instance or None if AI provider unavailable
    """
    ai_provider = get_ai_provider()

    if not ai_provider:
        logger.warning("AI provider not available - AIResponseService will not be initialized")
        return None

    return AIResponseService(
        ai_provider=ai_provider,
        context_service=context_service,
        message_repo=message_repo,
        cooldown_repo=cooldown_repo,
    )
