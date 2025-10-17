"""
Memory Builder Service for creating conversation memories.

Orchestrates memory creation process by:
1. Fetching conversation messages
2. Generating summaries using injected summarizer
3. Extracting keywords using injected extractor
4. Building memory content structure
5. Optionally generating embeddings
6. Persisting memory to database
"""

from datetime import datetime, timezone

import structlog

from app.interfaces.keyword_extractor import IKeywordExtractor
from app.interfaces.memory_summarizer import IMemorySummarizer
from app.models.ai_memory import AIMemory
from app.repositories.ai_entity_repository import IAIEntityRepository
from app.repositories.ai_memory_repository import IAIMemoryRepository
from app.repositories.message_repository import IMessageRepository

logger = structlog.get_logger(__name__)


class MemoryBuilderService:
    """Service for building and creating conversation memories."""

    def __init__(
        self,
        message_repo: IMessageRepository,
        memory_repo: IAIMemoryRepository,
        entity_repo: IAIEntityRepository,
        keyword_extractor: IKeywordExtractor,
        summarizer: IMemorySummarizer,
    ):
        """
        Initialize memory builder service with dependencies.

        Args:
            message_repo: Message repository for fetching conversation messages
            memory_repo: AI memory repository for persisting memories
            entity_repo: AI entity repository for fetching entity details
            keyword_extractor: Keyword extraction implementation (e.g., YAKE, LLM)
            summarizer: Summary generation implementation (e.g., Heuristic, LLM)
        """
        self.message_repo = message_repo
        self.memory_repo = memory_repo
        self.entity_repo = entity_repo
        self.keyword_extractor = keyword_extractor
        self.summarizer = summarizer

    async def create_conversation_memory(
        self,
        ai_entity_id: int,
        conversation_id: int,
        trigger_message_id: int,
    ) -> AIMemory:
        """
        Create memory from conversation messages.

        Process:
        1. Fetch last 20 messages from conversation
        2. Generate summary using configured summarizer
        3. Extract keywords using configured extractor
        4. Build memory content structure
        5. Calculate importance score
        6. Persist memory to database

        Args:
            ai_entity_id: AI entity ID that owns the memory
            conversation_id: Conversation ID to create memory from
            trigger_message_id: Message ID that triggered memory creation

        Returns:
            Created AIMemory instance

        Raises:
            ValueError: If no messages found or entity not found
            MemorySummarizationError: If summarization fails
            KeywordExtractionError: If keyword extraction fails
        """
        logger.info(
            "creating_conversation_memory",
            ai_entity_id=ai_entity_id,
            conversation_id=conversation_id,
            trigger_message_id=trigger_message_id,
        )

        # Fetch AI entity for contextualized summary
        entity = await self.entity_repo.get_by_id(ai_entity_id)
        if not entity:
            raise ValueError(f"AI entity {ai_entity_id} not found")

        # Fetch last 20 messages from conversation
        messages, _ = await self.message_repo.get_conversation_messages(
            conversation_id=conversation_id,
            page=1,
            page_size=20,
        )

        if not messages:
            raise ValueError(f"No messages found for conversation {conversation_id}")

        logger.debug(
            "fetched_conversation_messages",
            conversation_id=conversation_id,
            message_count=len(messages),
        )

        # Generate summary
        summary = await self.summarizer.summarize(messages, ai_entity=entity)

        # Extract keywords from summary
        keywords = await self.keyword_extractor.extract_keywords(
            text=summary,
            max_keywords=10,
            language="en",
        )

        # Build memory content structure
        memory_content = self._build_memory_content(messages)

        # Calculate importance score (simple for now)
        importance_score = self._calculate_importance(messages)

        # Create memory instance
        memory = AIMemory(
            entity_id=ai_entity_id,
            conversation_id=conversation_id,
            summary=summary,
            memory_content=memory_content,
            keywords=keywords,
            importance_score=importance_score,
            created_at=datetime.now(timezone.utc),
        )

        # Persist to database
        created_memory = await self.memory_repo.create(memory)

        logger.info(
            "created_conversation_memory",
            memory_id=created_memory.id,
            ai_entity_id=ai_entity_id,
            conversation_id=conversation_id,
            keywords=keywords,
            importance_score=importance_score,
        )

        return created_memory

    def _build_memory_content(self, messages: list) -> dict:
        """
        Build memory content structure from messages.

        Args:
            messages: List of Message instances

        Returns:
            Dictionary with structured memory content:
            {
                'participants': List of participant names,
                'topic': First user message preview,
                'key_facts': Extracted facts (placeholder),
                'context': Conversation context,
                'message_count': Number of messages,
                'last_message_id': ID of last message
            }
        """
        # Extract unique participants
        participants = set()
        for msg in messages:
            if msg.sender_user_id and hasattr(msg, "sender_user") and msg.sender_user:
                participants.add(msg.sender_user.username)
            elif msg.sender_ai_id and hasattr(msg, "sender_ai") and msg.sender_ai:
                participants.add(msg.sender_ai.display_name)

        # Determine topic from first user message
        topic = "general conversation"
        for msg in messages:
            if msg.sender_user_id and msg.content:
                topic = msg.content[:100]
                if len(msg.content) > 100:
                    topic += "..."
                break

        # Build content structure
        content = {
            "participants": sorted(list(participants)),
            "topic": topic,
            "key_facts": [],  # Placeholder for future LLM extraction
            "context": f"Conversation with {len(messages)} messages",
            "message_count": len(messages),
            "last_message_id": messages[-1].id if messages else None,
        }

        return content

    def _calculate_importance(self, messages: list) -> float:
        """
        Calculate importance score for memory.

        Simple heuristic for now:
        - Base score: 1.0
        - Future: Consider message count, duration, sentiment, etc.

        Args:
            messages: List of Message instances

        Returns:
            Importance score (float, typically 0.0-10.0)
        """
        # Simple implementation: base score of 1.0
        # Future enhancements:
        # - Longer conversations = higher importance
        # - Recent conversations = higher importance
        # - Emotional content = higher importance
        base_score = 1.0

        # Bonus for longer conversations (cap at 2.0)
        message_count_bonus = min(len(messages) / 20.0, 1.0)

        importance = base_score + message_count_bonus

        logger.debug(
            "calculated_importance",
            message_count=len(messages),
            importance_score=importance,
        )

        return importance
