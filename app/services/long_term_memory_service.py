import yake

from app.interfaces.embedding_service import EmbeddingServiceError, IEmbeddingService
from app.models.ai_memory import AIMemory
from app.repositories.ai_memory_repository import AIMemoryRepository
from app.repositories.message_repository import MessageRepository
from app.services.text_chunking_service import TextChunkingService


class LongTermMemoryService:
    """Service for creating long-term conversation archives."""

    def __init__(
        self,
        memory_repo: AIMemoryRepository,
        message_repo: MessageRepository,
        embedding_service: IEmbeddingService,
        chunking_service: TextChunkingService,
    ):
        self.memory_repo = memory_repo
        self.message_repo = message_repo
        self.embedding_service = embedding_service
        self.chunking_service = chunking_service
        self.keyword_extractor = yake.KeywordExtractor(
            lan="en",
            n=2,
            dedupLim=0.9,
            top=10,
        )

    async def create_long_term_archive(
        self,
        entity_id: int,
        user_id: int,
        conversation_id: int,
    ) -> list[AIMemory]:
        """
        Create long-term memory archive from entire conversation.

        - Fetches ALL messages from conversation
        - Chunks text into manageable pieces
        - Extracts keywords per chunk
        - Generates embeddings per chunk (batch)
        - Creates AIMemory per chunk

        Args:
            entity_id: AI entity ID
            user_id: User ID for user-specific memory
            conversation_id: Conversation ID

        Returns:
            List of created AIMemory instances (one per chunk)

        Raises:
            Exception: If embedding generation fails (fail fast)
        """
        # Fetch all messages from conversation
        messages, _ = await self.message_repo.get_conversation_messages(
            conversation_id=conversation_id,
            page=1,
            page_size=10000,  # High limit to get all
        )

        if not messages:
            return []

        # Combine all message content
        combined_text = "\n\n".join([f"{m.sender_user_id or 'AI'}: {m.content}" for m in messages])

        # Chunk text
        chunks = self.chunking_service.chunk_text(combined_text)

        if not chunks:
            return []

        # Extract keywords per chunk
        chunk_keywords = [self._extract_keywords(chunk) for chunk in chunks]

        # Generate embeddings per chunk (batch)
        try:
            embeddings = await self.embedding_service.embed_batch(chunks)
        except Exception as e:
            # Fail fast: Embedding error = Memory creation fails
            raise EmbeddingServiceError(f"Long-term memory creation failed: {e}", original_error=e)

        # Create AIMemory per chunk
        memories = []
        for i, (chunk, keywords, embedding) in enumerate(zip(chunks, chunk_keywords, embeddings)):
            summary = chunk[:200] + "..." if len(chunk) > 200 else chunk

            memory = AIMemory(
                entity_id=entity_id,
                user_id=user_id,
                conversation_id=conversation_id,
                summary=summary,
                memory_content={"full_text": chunk},
                keywords=keywords,
                importance_score=1.0,
                embedding=embedding,
                memory_metadata={
                    "type": "long_term",
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            )

            created = await self.memory_repo.create(memory)
            memories.append(created)

        return memories

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text using YAKE."""
        if not text or not text.strip():
            return []

        try:
            keywords = self.keyword_extractor.extract_keywords(text)
            return [kw[0] for kw in keywords]
        except Exception:
            return []
