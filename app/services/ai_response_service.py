"""
AI Response Service - Orchestrates AI message generation.

This service coordinates:
1. Context building (message history + memories)
2. LLM response generation
3. Message persistence
"""

import random

import structlog

from app.interfaces.ai_provider import AIProviderError, IAIProvider
from app.models.ai_entity import AIEntity, AIResponseStrategy
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
        user_id: int | None = None,
        include_memories: bool = True,
        in_reply_to_message_id: int | None = None,
    ) -> Message:
        """
        Generate AI response for a conversation message.

        Args:
            conversation_id: Conversation ID to respond in
            ai_entity: AI entity that should respond
            user_id: User ID for personalized memory retrieval (optional)
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
                user_id=user_id,
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
        user_id: int | None = None,
        include_memories: bool = True,
        in_reply_to_message_id: int | None = None,
    ) -> Message:
        """
        Generate AI response for a room message.

        Args:
            room_id: Room ID to respond in
            ai_entity: AI entity that should respond
            user_id: User ID for personalized memory (optional, rooms use global memories)
            include_memories: Whether to include AI memories in context

        Returns:
            Created message with AI response

        Raises:
            AIProviderError: If LLM generation fails
        """
        try:
            # Build context (message history + memories)
            # Note: For rooms, user_id is optional (global memories only for now)
            messages, memory_context = await self.context_service.build_full_context(
                conversation_id=None,
                room_id=room_id,
                ai_entity=ai_entity,
                user_id=user_id or 0,  # Placeholder for rooms (TODO: room memory system)
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

            logger.info(f"AI '{ai_entity.name}' generated response in room {room_id}: {len(response_content)} chars")

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
        Determine if AI should respond to a message based on configured strategies.

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

        # Delegate to appropriate strategy handler
        if room_id:
            return await self._should_respond_in_room(ai_entity, latest_message, room_id)
        elif conversation_id:
            return await self._should_respond_in_conversation(ai_entity, latest_message, conversation_id)
        else:
            logger.warning("should_ai_respond called without room_id or conversation_id")
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

    async def _should_respond_in_room(self, ai_entity: AIEntity, message: Message, room_id: int) -> bool:
        """
        Determine if AI should respond in a room based on room response strategy.

        Args:
            ai_entity: AI entity to check
            message: Latest message
            room_id: Room ID

        Returns:
            True if AI should respond, False otherwise
        """
        strategy = ai_entity.room_response_strategy

        # NO_RESPONSE: Never respond (after graceful goodbye)
        if strategy == AIResponseStrategy.NO_RESPONSE:
            return False

        content = message.content.lower()
        ai_mentioned = ai_entity.name.lower() in content or ai_entity.display_name.lower() in content

        # ROOM_MENTION_ONLY: Only respond when mentioned
        if strategy == AIResponseStrategy.ROOM_MENTION_ONLY:
            if ai_mentioned:
                logger.info(f"AI '{ai_entity.name}' mentioned in room {room_id} - will respond")
                return True
            return False

        # ROOM_PROBABILISTIC: Respond based on probability (higher chance if mentioned)
        if strategy == AIResponseStrategy.ROOM_PROBABILISTIC:
            probability = ai_entity.response_probability
            if ai_mentioned:
                probability = 1.0  # Always respond when mentioned

            should_respond = random.random() < probability
            if should_respond:
                logger.info(
                    f"AI '{ai_entity.name}' probabilistic response triggered (p={probability}) in room {room_id}"
                )
            return should_respond

        # ROOM_ACTIVE: Respond to most messages (filter very short ones)
        if strategy == AIResponseStrategy.ROOM_ACTIVE:
            # Always respond if mentioned
            if ai_mentioned:
                return True

            # Filter very short messages (like "ok", "lol")
            if len(message.content.strip()) < 3:
                return False

            logger.info(f"AI '{ai_entity.name}' active response in room {room_id}")
            return True

        # Unknown strategy
        logger.warning(f"Unknown room response strategy: {strategy} for AI '{ai_entity.name}'")
        return False

    async def _should_respond_in_conversation(
        self, ai_entity: AIEntity, message: Message, conversation_id: int
    ) -> bool:
        """
        Determine if AI should respond in a conversation based on conversation response strategy.

        Args:
            ai_entity: AI entity to check
            message: Latest message
            conversation_id: Conversation ID

        Returns:
            True if AI should respond, False otherwise
        """
        strategy = ai_entity.conversation_response_strategy

        # NO_RESPONSE: Never respond (after graceful goodbye)
        if strategy == AIResponseStrategy.NO_RESPONSE:
            return False

        content = message.content.lower()
        ai_mentioned = ai_entity.name.lower() in content or ai_entity.display_name.lower() in content

        # CONV_EVERY_MESSAGE: Respond to every message
        if strategy == AIResponseStrategy.CONV_EVERY_MESSAGE:
            logger.info(f"AI '{ai_entity.name}' responding to every message in conversation {conversation_id}")
            return True

        # CONV_ON_QUESTIONS: Only respond to questions
        if strategy == AIResponseStrategy.CONV_ON_QUESTIONS:
            question_indicators = ["?", "what", "how", "why", "when", "where", "who", "can you", "could you"]
            is_question = any(indicator in content for indicator in question_indicators)

            if is_question:
                logger.info(f"Question detected in conversation {conversation_id} - AI '{ai_entity.name}' will respond")
                return True
            return False

        # CONV_SMART: Respond to questions OR mentions
        if strategy == AIResponseStrategy.CONV_SMART:
            question_indicators = ["?", "what", "how", "why", "when", "where", "who", "can you", "could you"]
            is_question = any(indicator in content for indicator in question_indicators)

            if ai_mentioned or is_question:
                logger.info(
                    f"AI '{ai_entity.name}' smart response in conversation {conversation_id} "
                    f"(mentioned={ai_mentioned}, question={is_question})"
                )
                return True
            return False

        # Unknown strategy
        logger.warning(f"Unknown conversation response strategy: {strategy} for AI '{ai_entity.name}'")
        return False
