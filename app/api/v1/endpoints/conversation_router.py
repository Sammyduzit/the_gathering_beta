import structlog
from arq.connections import ArqRedis
from fastapi import APIRouter, Body, Depends, status

from app.core.arq_pool import get_arq_pool
from app.core.auth_dependencies import get_current_active_user
from app.core.config import settings
from app.core.csrf_dependencies import validate_csrf
from app.models.user import User
from app.repositories.ai_entity_repository import AIEntityRepository
from app.repositories.repository_dependencies import get_ai_entity_repository
from app.schemas.chat_schemas import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListItemResponse,
    MessageCreate,
    MessageResponse,
    PaginatedMessagesResponse,
)
from app.services.conversation_service import ConversationService
from app.services.service_dependencies import get_conversation_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate = Body(...),
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
    _csrf: None = Depends(validate_csrf),
) -> dict:
    """
    Create private or group conversation.
    :param conversation_data: Conversation creation data
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :param conversation_service: Service instance handling conversation logic
    :return: Success response with conversation info
    """
    new_conversation = await conversation_service.create_conversation(
        current_user=current_user,
        participant_usernames=conversation_data.participant_usernames,
        conversation_type=conversation_data.conversation_type,
    )
    return {
        "message": f"{conversation_data.conversation_type.title()} conversation created successfully",
        "conversation_id": new_conversation.id,
        "participants": len(conversation_data.participant_usernames) + 1,
    }


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_conversation_message(
    conversation_id: int,
    message_data: MessageCreate = Body(...),
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
    ai_entity_repo: AIEntityRepository = Depends(get_ai_entity_repository),
    arq_pool: ArqRedis | None = Depends(get_arq_pool),
    _csrf: None = Depends(validate_csrf),
) -> MessageResponse:
    """
    Send message to conversation.
    Returns 201 Created immediately, AI response (if applicable) is processed asynchronously.
    :param conversation_id: Target conversation ID
    :param message_data: Message content
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :param ai_entity_repo: AI entity repository for checking AI participants
    :param arq_pool: ARQ Redis pool for AI response jobs
    :return: Created message object
    """
    # Send message immediately
    message_response = await conversation_service.send_message(
        current_user=current_user,
        conversation_id=conversation_id,
        content=message_data.content,
    )

    # Check if AI participant is in conversation
    ai_entity = await ai_entity_repo.get_ai_in_conversation(conversation_id)

    # Trigger AI response check if AI is present
    if ai_entity and settings.is_ai_available and arq_pool:
        try:
            job = await arq_pool.enqueue_job(
                "check_and_generate_ai_response",
                message_id=message_response.id,
                conversation_id=conversation_id,
                ai_entity_id=ai_entity.id,
            )
            logger.info(
                "ai_response_job_enqueued",
                job_id=job.job_id if job else None,
                message_id=message_response.id,
                conversation_id=conversation_id,
                ai_entity_id=ai_entity.id,
                ai_entity_name=ai_entity.name,
            )
        except Exception as e:
            logger.error(
                "ai_response_job_failed",
                error=str(e),
                message_id=message_response.id,
                conversation_id=conversation_id,
                ai_entity_id=ai_entity.id,
                exc_info=True,
            )
            # Don't fail the message send if AI job fails
            # Message was already saved successfully

    return message_response


@router.get("/{conversation_id}/messages", response_model=PaginatedMessagesResponse)
async def get_conversation_messages(
    conversation_id: int,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> PaginatedMessagesResponse:
    """
    Get conversation message history with pagination.
    Messages are sorted by sent_at descending (newest first).
    :param conversation_id: Conversation ID to get messages from
    :param page: Page number (starting at 1)
    :param page_size: Messages per page (max 100)
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :return: Paginated message response with metadata
    """
    messages, total_count = await conversation_service.get_messages(
        current_user=current_user,
        conversation_id=conversation_id,
        page=page,
        page_size=page_size,
    )

    # Calculate pagination metadata
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
    has_more = page < total_pages

    return PaginatedMessagesResponse(
        messages=messages,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_more=has_more,
    )


@router.get("/", response_model=list[ConversationListItemResponse])
async def get_user_conversations(
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> list[ConversationListItemResponse]:
    """
    Get all active conversations for current user.
    Includes room name, participant info, and latest message preview for list views.
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :return: List of conversation list items
    """
    return await conversation_service.get_user_conversations(current_user.id)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_detail(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationDetailResponse:
    """
    Get detailed conversation information.
    Includes full participant details, permissions, message count, and latest message.
    :param conversation_id: ID of the conversation
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :return: Detailed conversation data
    """
    return await conversation_service.get_conversation_detail(current_user, conversation_id)


@router.get("/{conversation_id}/participants", response_model=list[dict])
async def get_conversation_participants(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> list[dict]:
    """
    Get participants of a conversation.
    :param conversation_id: ID of the conversation
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :return: List of participant user dictionaries for the given conversation
    """
    return await conversation_service.get_participants(current_user=current_user, conversation_id=conversation_id)


@router.post("/{conversation_id}/participants")
async def add_participant_to_conversation(
    conversation_id: int,
    username: str = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
    _csrf: None = Depends(validate_csrf),
) -> dict:
    """
    Add participant (human or AI) to conversation.

    Works seamlessly for both:
    - username="alice" → Adds human user
    - username="sophia" → Adds AI entity (if it exists)

    User cannot distinguish between human and AI from an API perspective.

    :param conversation_id: Conversation ID
    :param username: Username of human or AI to add
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :return: Success response with participant info
    """
    return await conversation_service.add_participant(
        conversation_id=conversation_id,
        username=username,
        current_user=current_user,
    )


@router.delete("/{conversation_id}/participants/{username}")
async def remove_participant_from_conversation(
    conversation_id: int,
    username: str,
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
    _csrf: None = Depends(validate_csrf),
) -> dict:
    """
    Remove participant from conversation.

    Users can remove themselves (leave conversation).
    Only admins can remove other participants (human or AI).

    :param conversation_id: Conversation ID
    :param username: Username of human or AI to remove
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :return: Success response with removal info
    """
    return await conversation_service.remove_participant(
        conversation_id=conversation_id,
        username=username,
        current_user=current_user,
    )
