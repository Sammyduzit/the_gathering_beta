from fastapi import Depends

from app.core.config import settings
from app.implementations.deepl_translator import DeepLTranslator
from app.interfaces.embedding_service import IEmbeddingService
from app.interfaces.keyword_extractor import IKeywordExtractor
from app.interfaces.memory_retriever import IMemoryRetriever
from app.interfaces.memory_summarizer import IMemorySummarizer
from app.interfaces.translator import TranslatorInterface
from app.repositories.ai_cooldown_repository import IAICooldownRepository
from app.repositories.ai_entity_repository import IAIEntityRepository
from app.repositories.ai_memory_repository import IAIMemoryRepository
from app.repositories.conversation_repository import IConversationRepository
from app.repositories.message_repository import IMessageRepository
from app.repositories.message_translation_repository import (
    IMessageTranslationRepository,
)
from app.repositories.repository_dependencies import (
    get_ai_cooldown_repository,
    get_ai_entity_repository,
    get_ai_memory_repository,
    get_conversation_repository,
    get_message_repository,
    get_message_translation_repository,
    get_room_repository,
    get_user_repository,
)
from app.repositories.room_repository import IRoomRepository
from app.repositories.user_repository import IUserRepository
from app.services.ai_entity_service import AIEntityService
from app.services.background_service import BackgroundService
from app.services.conversation_service import ConversationService
from app.services.heuristic_summarizer import HeuristicMemorySummarizer
from app.services.keyword_retriever import KeywordMemoryRetriever
from app.services.long_term_memory_service import LongTermMemoryService
from app.services.memory_builder_service import MemoryBuilderService
from app.services.openai_embedding_service import OpenAIEmbeddingService
from app.services.personality_memory_service import PersonalityMemoryService
from app.services.room_service import RoomService
from app.services.short_term_memory_service import ShortTermMemoryService
from app.services.text_chunking_service import TextChunkingService
from app.services.translation_service import TranslationService
from app.services.vector_memory_retriever import VectorMemoryRetriever
from app.services.yake_extractor import YakeKeywordExtractor


def get_deepl_translator() -> TranslatorInterface:
    """
    Create DeepL translator instance with API key from settings.
    :return: DeepL translator instance implementing TranslatorInterface
    """
    return DeepLTranslator(api_key=settings.deepl_api_key)


def get_translation_service(
    translator: TranslatorInterface = Depends(get_deepl_translator),
    message_repo: IMessageRepository = Depends(get_message_repository),
    translation_repo: IMessageTranslationRepository = Depends(get_message_translation_repository),
) -> TranslationService:
    """
    Create TranslationService instance with translator and repository dependencies.
    :param translator: Translator interface instance (DeepL implementation)
    :param message_repo: Message repository instance
    :param translation_repo: MessageTranslation repository instance
    :return: TranslationService instance
    """
    return TranslationService(
        translator=translator,
        message_repo=message_repo,
        translation_repo=translation_repo,
    )


def get_conversation_service(
    conversation_repo: IConversationRepository = Depends(get_conversation_repository),
    message_repo: IMessageRepository = Depends(get_message_repository),
    user_repo: IUserRepository = Depends(get_user_repository),
    room_repo: IRoomRepository = Depends(get_room_repository),
    translation_service: TranslationService = Depends(get_translation_service),
    ai_entity_repo: IAIEntityRepository = Depends(get_ai_entity_repository),
) -> ConversationService:
    """
    Create ConversationService instance with repository dependencies.
    :param conversation_repo: Conversation repository instance
    :param message_repo: Message repository instance
    :param user_repo: User repository instance
    :param room_repo: Room repository instance
    :param translation_service: Translation service instance
    :param ai_entity_repo: AI entity repository instance
    :return: ConversationService instance
    """
    return ConversationService(
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        user_repo=user_repo,
        room_repo=room_repo,
        translation_service=translation_service,
        ai_entity_repo=ai_entity_repo,
    )


def get_room_service(
    room_repo: IRoomRepository = Depends(get_room_repository),
    user_repo: IUserRepository = Depends(get_user_repository),
    message_repo: IMessageRepository = Depends(get_message_repository),
    conversation_repo: IConversationRepository = Depends(get_conversation_repository),
    message_translation_repo: IMessageTranslationRepository = Depends(get_message_translation_repository),
    translation_service: TranslationService = Depends(get_translation_service),
    ai_entity_repo: IAIEntityRepository = Depends(get_ai_entity_repository),
) -> RoomService:
    """
    Create RoomService instance with repository dependencies.
    :param room_repo: Room repository instance
    :param user_repo: User repository instance
    :param message_repo: Message repository instance
    :param conversation_repo: Conversation repository instance
    :param message_translation_repo: MessageTranslation repository instance
    :param translation_service: Translation service instance
    :param ai_entity_repo: AI entity repository instance
    :return: RoomService instance
    """
    return RoomService(
        room_repo=room_repo,
        user_repo=user_repo,
        message_repo=message_repo,
        conversation_repo=conversation_repo,
        message_translation_repo=message_translation_repo,
        translation_service=translation_service,
        ai_entity_repo=ai_entity_repo,
    )


def get_background_service(
    translation_service: TranslationService = Depends(get_translation_service),
    message_translation_repo: IMessageTranslationRepository = Depends(get_message_translation_repository),
) -> BackgroundService:
    """
    Create BackgroundService instance with service dependencies.
    :param translation_service: Translation service instance
    :param message_translation_repo: MessageTranslation repository instance
    :return: BackgroundService instance
    """
    return BackgroundService(
        translation_service=translation_service,
        message_translation_repo=message_translation_repo,
    )


def get_ai_entity_service(
    ai_entity_repo: IAIEntityRepository = Depends(get_ai_entity_repository),
    conversation_repo: IConversationRepository = Depends(get_conversation_repository),
    cooldown_repo: IAICooldownRepository = Depends(get_ai_cooldown_repository),
    room_repo: IRoomRepository = Depends(get_room_repository),
    message_repo: IMessageRepository = Depends(get_message_repository),
) -> AIEntityService:
    """
    Create AIEntityService instance with repository dependencies.
    :param ai_entity_repo: AI entity repository instance
    :param conversation_repo: Conversation repository instance
    :param cooldown_repo: AI cooldown repository instance
    :param room_repo: Room repository instance
    :param message_repo: Message repository instance
    :return: AIEntityService instance
    """
    return AIEntityService(
        ai_entity_repo=ai_entity_repo,
        conversation_repo=conversation_repo,
        cooldown_repo=cooldown_repo,
        room_repo=room_repo,
        message_repo=message_repo,
    )


def get_keyword_extractor() -> IKeywordExtractor:
    """
    Create keyword extractor implementation based on feature flags.

    Feature flags (future):
    - USE_LLM_KEYWORDS: Switch to LLM-based keyword extraction

    :return: Keyword extractor instance (default: YAKE)
    """
    # Future: Check settings.USE_LLM_KEYWORDS for LLM implementation
    return YakeKeywordExtractor()


def get_memory_summarizer() -> IMemorySummarizer:
    """
    Create memory summarizer implementation based on feature flags.

    Feature flags (future):
    - USE_LLM_SUMMARIZATION: Switch to LLM-based summarization

    :return: Memory summarizer instance (default: Heuristic)
    """
    # Future: Check settings.USE_LLM_SUMMARIZATION for LLM implementation
    return HeuristicMemorySummarizer()


def get_embedding_service() -> IEmbeddingService:
    """
    Create embedding service for vector search.

    :return: Embedding service instance
    """
    return OpenAIEmbeddingService(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )


def get_text_chunking_service() -> TextChunkingService:
    """
    Create text chunking service.

    :return: Text chunking service instance
    """
    return TextChunkingService(
        chunk_size=500,
        chunk_overlap=50,
    )


def get_memory_retriever(
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
    embedding_service: IEmbeddingService = Depends(get_embedding_service),
) -> IMemoryRetriever:
    """
    Create memory retriever implementation based on feature flags.

    :param memory_repo: AI memory repository instance
    :param embedding_service: Embedding service instance
    :return: Memory retriever instance (Vector if enabled, else Keyword)
    """
    if settings.enable_vector_search:
        return VectorMemoryRetriever(
            memory_repo=memory_repo,
            embedding_service=embedding_service,
        )
    else:
        return KeywordMemoryRetriever(memory_repo=memory_repo)


def get_memory_builder_service(
    message_repo: IMessageRepository = Depends(get_message_repository),
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
    entity_repo: IAIEntityRepository = Depends(get_ai_entity_repository),
    keyword_extractor: IKeywordExtractor = Depends(get_keyword_extractor),
    summarizer: IMemorySummarizer = Depends(get_memory_summarizer),
) -> MemoryBuilderService:
    """
    Create MemoryBuilderService instance with dependency injection.

    Dependencies are injected via factory functions that support feature flags:
    - keyword_extractor: YAKE (default) or LLM-based
    - summarizer: Heuristic (default) or LLM-based

    :param message_repo: Message repository instance
    :param memory_repo: AI memory repository instance
    :param entity_repo: AI entity repository instance
    :param keyword_extractor: Keyword extraction implementation
    :param summarizer: Summary generation implementation
    :return: MemoryBuilderService instance
    """
    return MemoryBuilderService(
        message_repo=message_repo,
        memory_repo=memory_repo,
        entity_repo=entity_repo,
        keyword_extractor=keyword_extractor,
        summarizer=summarizer,
    )


def get_short_term_memory_service(
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
) -> ShortTermMemoryService:
    """
    Create ShortTermMemoryService instance.

    :param memory_repo: AI memory repository instance
    :return: ShortTermMemoryService instance
    """
    return ShortTermMemoryService(memory_repo=memory_repo)


def get_long_term_memory_service(
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
    message_repo: IMessageRepository = Depends(get_message_repository),
    embedding_service: IEmbeddingService = Depends(get_embedding_service),
    chunking_service: TextChunkingService = Depends(get_text_chunking_service),
) -> LongTermMemoryService:
    """
    Create LongTermMemoryService instance.

    :param memory_repo: AI memory repository instance
    :param message_repo: Message repository instance
    :param embedding_service: Embedding service instance
    :param chunking_service: Text chunking service instance
    :return: LongTermMemoryService instance
    """
    return LongTermMemoryService(
        memory_repo=memory_repo,
        message_repo=message_repo,
        embedding_service=embedding_service,
        chunking_service=chunking_service,
    )


def get_personality_memory_service(
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
    embedding_service: IEmbeddingService = Depends(get_embedding_service),
    chunking_service: TextChunkingService = Depends(get_text_chunking_service),
) -> PersonalityMemoryService:
    """
    Create PersonalityMemoryService instance.

    :param memory_repo: AI memory repository instance
    :param embedding_service: Embedding service instance
    :param chunking_service: Text chunking service instance
    :return: PersonalityMemoryService instance
    """
    return PersonalityMemoryService(
        memory_repo=memory_repo,
        embedding_service=embedding_service,
        chunking_service=chunking_service,
    )
