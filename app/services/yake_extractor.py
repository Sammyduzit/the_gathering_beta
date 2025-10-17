"""
YAKE (Yet Another Keyword Extractor) implementation.

Provides lightweight unsupervised keyword extraction using statistical features.
No training, external corpus, or dictionaries required.
"""

import structlog
import yake

from app.interfaces.keyword_extractor import IKeywordExtractor, KeywordExtractionError

logger = structlog.get_logger(__name__)


class YakeKeywordExtractor(IKeywordExtractor):
    """YAKE-based keyword extractor implementation."""

    def __init__(
        self,
        language: str = "en",
        max_ngram_size: int = 2,
        deduplication_threshold: float = 0.9,
        window_size: int = 1,
    ):
        """
        Initialize YAKE keyword extractor.

        Args:
            language: Language code (default: 'en')
            max_ngram_size: Maximum n-gram size (1=unigrams, 2=bigrams, etc.)
            deduplication_threshold: Similarity threshold for deduplication (0.0-1.0)
            window_size: Context window size for co-occurrence
        """
        self.language = language
        self.max_ngram_size = max_ngram_size
        self.deduplication_threshold = deduplication_threshold
        self.window_size = window_size

        # Initialize YAKE extractor
        self.extractor = yake.KeywordExtractor(
            lan=language,
            n=max_ngram_size,
            dedupLim=deduplication_threshold,
            dedupFunc="seqm",
            windowsSize=window_size,
            top=20,  # Extract more, filter later
        )

    async def extract_keywords(
        self,
        text: str,
        max_keywords: int = 10,
        language: str = "en",
    ) -> list[str]:
        """
        Extract keywords from text using YAKE algorithm.

        Args:
            text: Text to extract keywords from
            max_keywords: Maximum number of keywords to extract
            language: Language code (ignored, uses instance language)

        Returns:
            List of extracted keywords (lowercase, normalized)
            Example: ['python', 'fastapi', 'sqlalchemy']

        Raises:
            KeywordExtractionError: If extraction fails
        """
        try:
            # Handle empty or very short text
            if not text or len(text.strip()) < 3:
                logger.debug("Text too short for keyword extraction")
                return []

            # Extract keywords with YAKE
            # Returns list of tuples: [(keyword, score), ...]
            # Lower score = more relevant
            raw_keywords = self.extractor.extract_keywords(text)

            # Normalize and filter keywords
            keywords = self._normalize_keywords(raw_keywords, max_keywords)

            logger.debug(
                "extracted_keywords",
                keyword_count=len(keywords),
                text_length=len(text),
                keywords=keywords,
            )

            return keywords

        except Exception as e:
            logger.error("keyword_extraction_failed", error=str(e))
            raise KeywordExtractionError(f"Failed to extract keywords: {str(e)}", original_error=e)

    def _normalize_keywords(self, raw_keywords: list[tuple], max_keywords: int) -> list[str]:
        """
        Normalize and filter extracted keywords.

        Args:
            raw_keywords: List of (keyword, score) tuples from YAKE
            max_keywords: Maximum number of keywords to return

        Returns:
            Filtered and normalized keyword list
        """
        normalized = []

        for keyword, score in raw_keywords:
            # Lowercase and strip whitespace
            kw = keyword.lower().strip()

            # Filter:
            # - Minimum 3 characters (avoid 'is', 'at', etc.)
            # - No pure numbers
            # - No duplicates
            if len(kw) >= 3 and not kw.isdigit() and kw not in normalized:
                normalized.append(kw)

            # Stop when we have enough
            if len(normalized) >= max_keywords:
                break

        return normalized
