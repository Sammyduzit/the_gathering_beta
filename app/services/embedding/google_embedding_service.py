import structlog
from google import genai
from google.genai import types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.interfaces.embedding_service import IEmbeddingService

logger = structlog.get_logger(__name__)


class GoogleEmbeddingService(IEmbeddingService):
    """Google Gemini embedding service using gemini-embedding-001."""

    def __init__(self, api_key: str, model: str = "gemini-embedding-001", dimensions: int = 1536):
        """
        Initialize Google Gemini embedding service.

        Args:
            api_key: Google API key
            model: Embedding model name (default: gemini-embedding-001)
            dimensions: Embedding dimensions (default: 1536, supported: 768, 1536, 3072)
        """
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text with retry logic.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            Exception: If embedding fails after retries
        """
        try:
            response = self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error("embedding_failed", text_length=len(text), error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in a batch.

        Note: Google Gemini API supports batch embedding via the contents parameter.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            Exception: If batch embedding fails after retries
            ValueError: If batch is empty
        """
        if not texts:
            raise ValueError("Batch cannot be empty")

        try:
            response = self.client.models.embed_content(
                model=self.model,
                contents=texts,
                config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
            )
            return [emb.values for emb in response.embeddings]
        except Exception as e:
            logger.error("batch_embedding_failed", batch_size=len(texts), error=str(e))
            raise
