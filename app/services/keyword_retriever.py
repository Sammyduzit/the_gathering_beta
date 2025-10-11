"""
Keyword-based Memory Retriever implementation.

Provides keyword-based memory retrieval from database using repository pattern.
Future-proof design allows easy extension with vector search.
"""

import structlog

from app.interfaces.memory_retriever import IMemoryRetriever, MemoryRetrievalError
from app.models.ai_memory import AIMemory
from app.repositories.ai_memory_repository import IAIMemoryRepository

logger = structlog.get_logger(__name__)


class KeywordMemoryRetriever(IMemoryRetriever):
    """Keyword-based memory retriever implementation."""

    def __init__(self, memory_repo: IAIMemoryRepository):
        """
        Initialize keyword retriever with memory repository.

        Args:
            memory_repo: AI memory repository instance
        """
        self.memory_repo = memory_repo

    async def retrieve_candidates(
        self,
        entity_id: int,
        query: str | None = None,
        keywords: list[str] | None = None,
        limit: int = 20,
    ) -> list[AIMemory]:
        """
        Retrieve memory candidates using keyword-based filtering.

        Strategy:
        1. If keywords provided: Use repository's search_by_keywords()
        2. Else: Use repository's get_entity_memories() (importance + recency)

        Args:
            entity_id: AI entity ID to retrieve memories for
            query: Optional query text (ignored by keyword retriever, used by vector retrievers)
            keywords: Optional keywords for keyword-based filtering
            limit: Maximum number of candidates to retrieve (default: 20)

        Returns:
            List of memory candidates ordered by relevance
            - With keywords: Ordered by importance_score
            - Without keywords: Ordered by importance_score DESC, created_at DESC

        Raises:
            MemoryRetrievalError: If retrieval fails
        """
        try:
            if keywords:
                # Keyword-based search
                memories = await self.memory_repo.search_by_keywords(
                    entity_id=entity_id,
                    keywords=keywords,
                    limit=limit,
                )

                logger.debug(
                    "retrieved_memories_by_keywords",
                    entity_id=entity_id,
                    keywords=keywords,
                    count=len(memories),
                )
            else:
                # Fallback: Get all memories ordered by importance + recency
                memories = await self.memory_repo.get_entity_memories(
                    entity_id=entity_id,
                    room_id=None,  # Get all, not room-specific
                    limit=limit,
                )

                logger.debug(
                    "retrieved_memories_all",
                    entity_id=entity_id,
                    count=len(memories),
                )

            return memories

        except Exception as e:
            logger.error("memory_retrieval_failed", entity_id=entity_id, error=str(e))
            raise MemoryRetrievalError(f"Failed to retrieve memories: {str(e)}", original_error=e)
