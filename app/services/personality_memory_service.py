import yake

from app.interfaces.embedding_service import IEmbeddingService
from app.models.ai_memory import AIMemory
from app.repositories.ai_memory_repository import AIMemoryRepository
from app.services.text_chunking_service import TextChunkingService


class PersonalityMemoryService:
    """Service for uploading personality knowledge base (books, docs, etc)."""

    def __init__(
        self,
        memory_repo: AIMemoryRepository,
        embedding_service: IEmbeddingService,
        chunking_service: TextChunkingService,
    ):
        self.memory_repo = memory_repo
        self.embedding_service = embedding_service
        self.chunking_service = chunking_service
        self.keyword_extractor = yake.KeywordExtractor(
            lan="en",
            n=2,
            dedupLim=0.9,
            top=10,
        )

    async def upload_personality(
        self,
        entity_id: int,
        text: str,
        category: str,
        metadata: dict,
    ) -> list[AIMemory]:
        """
        Upload personality knowledge from text (books, documents, etc).

        - Global memory (user_id = NULL, conversation_id = NULL)
        - Chunks text into manageable pieces
        - Extracts keywords per chunk
        - Generates embeddings per chunk (batch)
        - Creates AIMemory per chunk

        Args:
            entity_id: AI entity ID
            text: Text content to upload
            category: Category (e.g., "books", "docs")
            metadata: Additional metadata (e.g., book_title, chapter)

        Returns:
            List of created AIMemory instances (one per chunk)

        Raises:
            Exception: If embedding generation fails (fail fast)
        """
        if not text or not text.strip():
            return []

        # Chunk text
        chunks = self.chunking_service.chunk_text(text)

        if not chunks:
            return []

        # Extract keywords per chunk
        chunk_keywords = [self._extract_keywords(chunk) for chunk in chunks]

        # Generate embeddings per chunk (batch)
        try:
            embeddings = await self.embedding_service.embed_batch(chunks)
        except Exception as e:
            # Fail fast: Embedding error = Personality upload fails
            raise Exception(f"Personality upload failed: {e}")

        # Create AIMemory per chunk
        memories = []
        for i, (chunk, keywords, embedding) in enumerate(zip(chunks, chunk_keywords, embeddings)):
            summary = chunk[:200] + "..." if len(chunk) > 200 else chunk

            memory = AIMemory(
                entity_id=entity_id,
                user_id=None,  # Global (not user-specific)
                conversation_id=None,  # Not conversation-bound
                summary=summary,
                memory_content={"full_text": chunk},
                keywords=keywords,
                importance_score=1.0,
                embedding=embedding,
                memory_metadata={
                    "type": "personality",
                    "category": category,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    **metadata,  # Include additional metadata
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
