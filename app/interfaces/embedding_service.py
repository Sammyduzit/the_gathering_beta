from abc import ABC, abstractmethod


class IEmbeddingService(ABC):
    """Interface for text embedding services."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in a batch.

        Args:
            texts: List of texts to embed (max 100)

        Returns:
            List of embedding vectors
        """
        pass
