"""AI Facade - Simplified AI service initialization helper."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.providers.openai_provider import OpenAIProvider
from app.repositories.ai_cooldown_repository import AICooldownRepository
from app.repositories.ai_entity_repository import AIEntityRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.services.ai_context_service import AIContextService
from app.services.ai_entity_service import AIEntityService
from app.services.ai_response_service import AIResponseService


def create_ai_facade_with_session(session: AsyncSession, model: str = "gpt-4o-mini") -> dict:
    """
    Create all AI-related services with a single session.

    This helper simplifies AI service initialization by creating
    all repositories and services with shared session context.

    Args:
        session: SQLAlchemy async session
        model: LLM model name (default: gpt-4o-mini)

    Returns:
        Dict with ai_response_service, ai_entity_service, and ai_context_service
    """
    ai_entity_repo = AIEntityRepository(session)
    message_repo = MessageRepository(session)
    conversation_repo = ConversationRepository(session)
    cooldown_repo = AICooldownRepository(session)

    ai_provider = OpenAIProvider(
        api_key=settings.openai_api_key,
        model_name=model,
    )
    ai_context_service = AIContextService(message_repo)

    ai_response_service = AIResponseService(
        ai_provider=ai_provider,
        context_service=ai_context_service,
        message_repo=message_repo,
    )

    ai_entity_service = AIEntityService(
        ai_entity_repo=ai_entity_repo,
        conversation_repo=conversation_repo,
        cooldown_repo=cooldown_repo,
    )

    return {
        "ai_response_service": ai_response_service,
        "ai_entity_service": ai_entity_service,
        "ai_context_service": ai_context_service,
    }
