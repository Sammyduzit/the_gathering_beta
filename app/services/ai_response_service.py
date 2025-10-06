"""
AI Response Service - Orchestrates AI message generation.

This service coordinates:
1. Context building (message history + memories)
2. LLM response generation
3. Message persistence
"""

import structlog

from app.interfaces.ai_provider import AIProviderError, IAIProvider
from app.models.ai_entity import AIEntity
from app.models.message import Message
from app.repositories.message_repository import IMessageRepository
from app.services.ai_context_service import AIContextService

logger = structlog.get_logger(__name__)


class AIResponseService:
    """Service for generating and managing AI responses."""

    def __init__(
        self,
        ai_provider: IAIProvider,
        context_service: AIContextService,
        message_repo: IMessageRepository,
    ):
        self.ai_provider = ai_provider
        self.context_service = context_service
        self.message_repo = message_repo

    async def generate_conversation_response(
        self,
        conversation_id: int,
        ai_entity: AIEntity,
        include_memories: bool = True,
        in_reply_to_message_id: int | None = None,
    ) -> Message:
        """
        Generate AI response for a conversation message.

        Args:
            conversation_id: Conversation ID to respond in
            ai_entity: AI entity that should respond
            include_memories: Whether to include AI memories in context

        Returns:
            Created message with AI response

        Raises:
            AIProviderError: If LLM generation fails
        """
        try:
            # Build context (message history + memories)
            messages, memory_context = await self.context_service.build_full_context(
                conversation_id=conversation_id,
                room_id=None,
                ai_entity=ai_entity,
                include_memories=include_memories,
            )

            # Enhance system prompt with memories if available
            system_prompt = ai_entity.system_prompt
            if memory_context:
                system_prompt = f"{system_prompt}\n\n{memory_context}"

            # Generate response from LLM
            response_content = await self.ai_provider.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                temperature=ai_entity.temperature,
                max_tokens=ai_entity.max_tokens,
            )

            # Save AI response as message
            message = await self.message_repo.create_conversation_message(
                conversation_id=conversation_id,
                content=response_content,
                sender_ai_id=ai_entity.id,
                in_reply_to_message_id=in_reply_to_message_id,
            )

            logger.info(
                f"AI '{ai_entity.name}' generated response in conversation {conversation_id}: "
                f"{len(response_content)} chars"
            )

            return message

        except Exception as e:
            logger.error(f"Failed to generate AI response for conversation {conversation_id}: {e}")
            raise AIProviderError(f"AI response generation failed: {str(e)}", original_error=e)

    async def generate_room_response(
        self,
        room_id: int,
        ai_entity: AIEntity,
        include_memories: bool = True,
        in_reply_to_message_id: int | None = None,
    ) -> Message:
        """
        Generate AI response for a room message.

        Args:
            room_id: Room ID to respond in
            ai_entity: AI entity that should respond
            include_memories: Whether to include AI memories in context

        Returns:
            Created message with AI response

        Raises:
            AIProviderError: If LLM generation fails
        """
        try:
            # Build context (message history + memories)
            messages, memory_context = await self.context_service.build_full_context(
                conversation_id=None,
                room_id=room_id,
                ai_entity=ai_entity,
                include_memories=include_memories,
            )

            # Enhance system prompt with memories if available
            system_prompt = ai_entity.system_prompt
            if memory_context:
                system_prompt = f"{system_prompt}\n\n{memory_context}"

            # Generate response from LLM
            response_content = await self.ai_provider.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                temperature=ai_entity.temperature,
                max_tokens=ai_entity.max_tokens,
            )

            # Save AI response as message
            message = await self.message_repo.create_room_message(
                room_id=room_id,
                content=response_content,
                sender_ai_id=ai_entity.id,
                in_reply_to_message_id=in_reply_to_message_id,
            )

            logger.info(
                f"AI '{ai_entity.name}' generated response in room {room_id}: {len(response_content)} chars"
            )

            return message

        except Exception as e:
            logger.error(f"Failed to generate AI response for room {room_id}: {e}")
            raise AIProviderError(f"AI response generation failed: {str(e)}", original_error=e)

    async def should_ai_respond(
        self,
        ai_entity: AIEntity,
        latest_message: Message,
        conversation_id: int | None = None,
        room_id: int | None = None,
    ) -> bool:
        """
        Determine if AI should respond to a message.

        Currently uses simple heuristics:
        - AI was mentioned by name
        - Direct question patterns
        - Random engagement for natural conversation

        Future: Could use LLM to decide whether to respond.

        Args:
            ai_entity: AI entity to check
            latest_message: Latest message in the conversation
            conversation_id: Conversation ID (for private/group chats)
            room_id: Room ID (for public rooms)

        Returns:
            True if AI should respond, False otherwise
        """
        # Don't respond to own messages
        if latest_message.sender_ai_id == ai_entity.id:
            return False

        content = latest_message.content.lower()

        # Check if AI was mentioned by name or display name
        if ai_entity.name.lower() in content or ai_entity.display_name.lower() in content:
            logger.info(f"AI '{ai_entity.name}' mentioned in message - will respond")
            return True

        # Check for question patterns
        question_indicators = ["?", "what", "how", "why", "when", "where", "who"]
        if any(indicator in content for indicator in question_indicators):
            # In conversations, respond to questions more frequently
            if conversation_id:
                logger.info(f"Question detected in conversation - AI '{ai_entity.name}' will respond")
                return True

        # In rooms, be more selective (don't spam)
        if room_id:
            # Only respond if directly engaged
            return False

        # In conversations, respond more naturally
        # Future: Use LLM to determine response probability
        return False

    async def check_provider_availability(self) -> bool:
        """
        Check if AI provider is available and configured.

        Returns:
            True if provider is available, False otherwise
        """
        if not self.ai_provider:
            logger.warning("AI provider not configured")
            return False

        try:
            return await self.ai_provider.check_availability()
        except Exception as e:
            logger.error(f"AI provider availability check failed: {e}")
            return False
