from arq.connections import ArqRedis
from fastapi import APIRouter, Body, Depends, status

from app.core.arq_pool import get_arq_pool
from app.core.auth_dependencies import get_current_active_user
from app.core.config import settings
from app.core.csrf_dependencies import validate_csrf
from app.models.user import User
from app.repositories.ai_entity_repository import AIEntityRepository
from app.repositories.repository_dependencies import get_ai_entity_repository
from app.schemas.chat_schemas import ConversationCreate, MessageCreate, MessageResponse
from app.services.conversation_service import ConversationService
from app.services.service_dependencies import get_conversation_service

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


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
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
    ARQ task triggers AI response if AI participant is present.
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
        await arq_pool.enqueue_job(
            "check_and_generate_ai_response",
            message_id=message_response["id"],
            conversation_id=conversation_id,
            ai_entity_id=ai_entity.id,
        )

    return message_response


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: int,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> list[MessageResponse]:
    """
    Get conversation message history.
    :param conversation_id: Conversation ID to get messages from
    :param page: Page number
    :param page_size: Messages per page
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :return: List of conversation messages
    """
    messages, total_count = await conversation_service.get_messages(
        current_user=current_user,
        conversation_id=conversation_id,
        page=page,
        page_size=page_size,
    )

    return messages


@router.get("/", response_model=list[dict])
async def get_user_conversations(
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> list[dict]:
    """
    Get all active conversations for current user.
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :return: List of conversation dictionaries the user is part of
    """
    return await conversation_service.get_user_conversations(current_user.id)


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
