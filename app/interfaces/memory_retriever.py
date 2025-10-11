"""
Memory Retriever interface for retrieving AI memories from storage.

This interface abstracts memory retrieval functionality, allowing different
retrieval strategies (keyword-based, vector-based, hybrid) to be used
interchangeably through dependency injection.
"""

from abc import ABC, abstractmethod

from app.models.ai_memory import AIMemory


class IMemoryRetriever(ABC):
    """Abstract interface for AI memory retrieval services."""

    @abstractmethod
    async def retrieve_candidates(
        self,
        entity_id: int,
        query: str | None = None,
        keywords: list[str] | None = None,
        limit: int = 20,
    ) -> list[AIMemory]:
        """
        Retrieve memory candidates for further filtering/ranking.

        This method over-fetches candidates that can be filtered and ranked
        by subsequent verifier stages.

        Args:
            entity_id: AI entity ID to retrieve memories for
            query: Optional query text for semantic search (used by vector retrievers)
            keywords: Optional keywords for keyword-based filtering
            limit: Maximum number of candidates to retrieve (default: 20)

        Returns:
            List of memory candidates (may contain more than needed for filtering)
            Memories are NOT pre-filtered by relevance - that's the verifier's job

        Raises:
            MemoryRetrievalError: If retrieval fails
        """
        pass


class MemoryRetrievalError(Exception):
    """Exception raised when memory retrieval operations fail."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error
