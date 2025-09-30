from fastapi import APIRouter, Body, Depends, status

from app.core.auth_dependencies import get_current_active_user
from app.models.user import User
from app.schemas.chat_schemas import ConversationCreate, MessageCreate, MessageResponse
from app.services.conversation_service import ConversationService
from app.services.service_dependencies import get_conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate = Body(...),
    current_user: User = Depends(get_current_active_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
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
) -> MessageResponse:
    """
    Send message to conversation.
    :param conversation_id: Target conversation ID
    :param message_data: Message content
    :param current_user: Current authenticated user
    :param conversation_service: Service instance handling conversation logic
    :return: Created message object
    """
    return await conversation_service.send_message(
        current_user=current_user,
        conversation_id=conversation_id,
        content=message_data.content,
    )


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
