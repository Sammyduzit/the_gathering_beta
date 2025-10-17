import yake

from app.models.ai_memory import AIMemory
from app.models.message import Message
from app.repositories.ai_memory_repository import AIMemoryRepository


class ShortTermMemoryService:
    """Service for creating short-term conversation memories."""

    def __init__(self, memory_repo: AIMemoryRepository):
        self.memory_repo = memory_repo
        self.keyword_extractor = yake.KeywordExtractor(
            lan="en",
            n=2,
            dedupLim=0.9,
            top=10,
        )

    async def create_short_term_memory(
        self,
        entity_id: int,
        user_id: int,
        conversation_id: int,
        messages: list[Message],
    ) -> AIMemory:
        """
        Create short-term memory from recent conversation messages.

        - Takes last 20 messages
        - Filters only user messages (no system, no AI)
        - Extracts keywords (YAKE)
        - Creates simple summary
        - NO embedding (fast!)

        Args:
            entity_id: AI entity ID
            user_id: User ID for user-specific memory
            conversation_id: Conversation ID
            messages: List of recent messages

        Returns:
            Created AIMemory instance
        """
        # Get last 20 messages
        recent = messages[-20:] if len(messages) > 20 else messages

        # Filter: Only user messages (not system, not AI)
        user_messages = [m for m in recent if m.sender_user_id is not None and m.message_type != "system"]

        if not user_messages:
            # No user messages, create minimal memory
            memory = AIMemory(
                entity_id=entity_id,
                user_id=user_id,
                conversation_id=conversation_id,
                summary="No recent user messages",
                memory_content={"message_count": 0},
                keywords=[],
                importance_score=0.5,
                embedding=None,  # No embedding for short-term
                memory_metadata={"type": "short_term"},
            )
            return await self.memory_repo.create(memory)

        # Combine user message content for keyword extraction
        combined_text = " ".join([m.content for m in user_messages])

        # Extract keywords
        keywords = self._extract_keywords(combined_text)

        # Create simple summary (first 200 chars of first user message)
        first_message = user_messages[0].content
        summary = first_message[:200] + "..." if len(first_message) > 200 else first_message

        # Create memory
        memory = AIMemory(
            entity_id=entity_id,
            user_id=user_id,
            conversation_id=conversation_id,
            summary=summary,
            memory_content={
                "message_count": len(user_messages),
                "last_messages": [
                    {"sender": m.sender_user_id, "content": m.content}
                    for m in user_messages[-5:]  # Store last 5
                ],
            },
            keywords=keywords,
            importance_score=1.0,
            embedding=None,  # No embedding for short-term
            memory_metadata={"type": "short_term"},
        )

        return await self.memory_repo.create(memory)

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text using YAKE."""
        if not text or not text.strip():
            return []

        try:
            keywords = self.keyword_extractor.extract_keywords(text)
            return [kw[0] for kw in keywords]
        except Exception:
            return []
