"""
AI Context Service for building conversation context.

Retrieves message history and AI memory to provide context for LLM responses.
"""

import logging
from datetime import datetime, timezone

from app.core.constants import MAX_CONTEXT_MESSAGES, MAX_MEMORY_ENTRIES
from app.interfaces.memory_retriever import IMemoryRetriever
from app.models.ai_entity import AIEntity
from app.models.ai_memory import AIMemory
from app.repositories.ai_memory_repository import IAIMemoryRepository
from app.repositories.message_repository import IMessageRepository

logger = logging.getLogger(__name__)


class AIContextService:
    """Service for building AI conversation context."""

    def __init__(
        self,
        message_repo: IMessageRepository,
        memory_repo: IAIMemoryRepository,
        memory_retriever: IMemoryRetriever | None = None,
    ):
        """
        Initialize AI context service.

        Args:
            message_repo: Message repository for fetching conversation history
            memory_repo: AI memory repository for persisting memory updates
            memory_retriever: Memory retriever implementation (optional, for enhanced retrieval)
        """
        self.message_repo = message_repo
        self.memory_repo = memory_repo
        self.memory_retriever = memory_retriever

    async def build_conversation_context(
        self,
        conversation_id: int,
        ai_entity: AIEntity,
        max_messages: int = MAX_CONTEXT_MESSAGES,
    ) -> list[dict[str, str]]:
        """
        Build conversation context for AI response generation.

        Args:
            conversation_id: Conversation ID to get messages from
            ai_entity: AI entity that will respond
            max_messages: Maximum number of recent messages to include

        Returns:
            List of message dicts with 'role' and 'content' keys
            Example: [{"role": "user", "content": "Alice: Hello"}, {"role": "user", "content": "You: Hi Alice!"}]
            Note: All messages use "user" role - AI is a participant, not an assistant
        """
        # Get recent messages from conversation
        messages, _ = await self.message_repo.get_conversation_messages(
            conversation_id=conversation_id,
            page=1,
            page_size=max_messages,
        )

        # Convert to LLM message format
        # All messages are treated as "user" role - the AI is a participant, not an assistant
        # The AI's personality comes from the system_prompt, not from role differentiation
        context_messages = []
        for msg in reversed(messages):  # Reverse to get chronological order
            # Include sender name for context (AI needs to know who said what)
            if msg.sender_user_id:
                sender_name = msg.sender_user.username
            elif msg.sender_ai_id:
                if msg.sender_ai_id == ai_entity.id:
                    sender_name = "You"  # AI's own previous messages
                else:
                    sender_name = msg.sender_ai.display_name  # Other AI entities
            else:
                sender_name = "Unknown"

            content = f"{sender_name}: {msg.content}"
            context_messages.append({"role": "user", "content": content})

        logger.info(
            f"Built conversation context for AI '{ai_entity.name}' in conversation {conversation_id}: "
            f"{len(context_messages)} messages"
        )

        return context_messages

    async def build_room_context(
        self,
        room_id: int,
        ai_entity: AIEntity,
        max_messages: int = MAX_CONTEXT_MESSAGES,
    ) -> list[dict[str, str]]:
        """
        Build room message context for AI response generation.

        Args:
            room_id: Room ID to get messages from
            ai_entity: AI entity that will respond
            max_messages: Maximum number of recent messages to include

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        # Get recent messages from room
        messages, _ = await self.message_repo.get_room_messages(
            room_id=room_id,
            page=1,
            page_size=max_messages,
        )

        # Convert to LLM message format
        # All messages are treated as "user" role - the AI is a chat participant
        context_messages = []
        for msg in reversed(messages):  # Reverse to get chronological order
            # Include sender name for context
            if msg.sender_user_id:
                sender_name = msg.sender_user.username
            elif msg.sender_ai_id:
                if msg.sender_ai_id == ai_entity.id:
                    sender_name = "You"  # AI's own previous messages
                else:
                    sender_name = msg.sender_ai.display_name  # Other AI entities
            else:
                sender_name = "Unknown"

            content = f"{sender_name}: {msg.content}"
            context_messages.append({"role": "user", "content": content})

        logger.info(f"Built room context for AI '{ai_entity.name}' in room {room_id}: {len(context_messages)} messages")

        return context_messages

    async def get_ai_memories(
        self,
        ai_entity_id: int,
        keywords: list[str] | None = None,
        max_entries: int = MAX_MEMORY_ENTRIES,
    ) -> str:
        """
        Retrieve AI entity's memories as formatted context.

        Uses injected memory retriever for enhanced retrieval strategy.
        Falls back to direct repository access if no retriever provided.

        Process:
        1. Retrieve candidates (over-fetch for filtering)
        2. Filter and rank candidates
        3. Update access tracking
        4. Format for LLM context

        Args:
            ai_entity_id: AI entity ID
            keywords: Optional keywords for keyword-based filtering
            max_entries: Maximum number of memory entries to retrieve

        Returns:
            Formatted memory context string
        """
        # Retrieve memory candidates
        if self.memory_retriever:
            # Use retriever for enhanced retrieval (keyword-based or vector)
            # Over-fetch candidates (4x) for better filtering
            candidates = await self.memory_retriever.retrieve_candidates(
                entity_id=ai_entity_id,
                keywords=keywords,
                limit=max_entries * 4,
            )
        else:
            # Fallback: Direct repository access
            candidates = await self.memory_repo.get_entity_memories(
                entity_id=ai_entity_id,
                limit=max_entries * 4,
            )

        if not candidates:
            return ""

        # Filter and rank candidates
        memories = await self._filter_and_rank(candidates, max_entries)

        if not memories:
            return ""

        # Update access tracking for selected memories
        await self._update_access_tracking(memories)

        # Format memories as context
        memory_lines = ["# Previous Memories:"]
        for memory in memories:
            importance_marker = "!" * int(memory.importance_score)  # Visual importance indicator
            memory_lines.append(f"{importance_marker} {memory.summary}")

        memory_context = "\n".join(memory_lines)

        logger.info(
            f"Retrieved {len(memories)} memories for AI entity {ai_entity_id} "
            f"(keywords: {keywords}, importance scores: {[m.importance_score for m in memories]})"
        )

        return memory_context

    async def _filter_and_rank(
        self,
        candidates: list[AIMemory],
        limit: int,
    ) -> list[AIMemory]:
        """
        Filter and rank memory candidates.

        Current implementation: Simple importance-based ranking.
        Future: LLM-based relevance verification.

        Args:
            candidates: List of memory candidates
            limit: Maximum number of memories to return

        Returns:
            Filtered and ranked list of memories
        """
        # Sort by importance score (descending)
        ranked = sorted(
            candidates,
            key=lambda m: m.importance_score,
            reverse=True,
        )

        # Return top N
        return ranked[:limit]

    async def _update_access_tracking(self, memories: list[AIMemory]) -> None:
        """
        Update access tracking for selected memories.

        Increments access_count and updates last_accessed timestamp.

        Args:
            memories: List of memories to update
        """
        now = datetime.now(timezone.utc)

        for memory in memories:
            memory.access_count = (memory.access_count or 0) + 1
            memory.last_accessed = now

            # Update in database
            await self.memory_repo.update(
                memory_id=memory.id,
                access_count=memory.access_count,
                last_accessed=memory.last_accessed,
            )

        logger.debug(f"Updated access tracking for {len(memories)} memories")

    async def build_full_context(
        self,
        conversation_id: int | None,
        room_id: int | None,
        ai_entity: AIEntity,
        include_memories: bool = True,
    ) -> tuple[list[dict[str, str]], str | None]:
        """
        Build complete context including messages and memories.

        Args:
            conversation_id: Conversation ID (for private/group chats)
            room_id: Room ID (for public room messages)
            ai_entity: AI entity that will respond
            include_memories: Whether to include AI memories in system prompt

        Returns:
            Tuple of (message_context, memory_context)
            - message_context: List of message dicts
            - memory_context: Formatted memory string or None

        Raises:
            ValueError: If both conversation_id and room_id are None
        """
        # Get message context
        if conversation_id:
            messages = await self.build_conversation_context(conversation_id, ai_entity)
        elif room_id:
            messages = await self.build_room_context(room_id, ai_entity)
        else:
            raise ValueError("Either conversation_id or room_id must be provided")

        # Get memory context if enabled
        memory_context = None
        if include_memories:
            memory_context = await self.get_ai_memories(ai_entity.id)

        return messages, memory_context
