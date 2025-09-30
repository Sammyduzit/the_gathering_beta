from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.validators import SanitizedString


class MessageCreate(BaseModel):
    """
    Schema for creating a room message.
    """

    content: SanitizedString = Field(min_length=1, max_length=500, description="Message content")


class MessageResponse(BaseModel):
    """
    Message response.
    """

    id: int
    sender_id: int
    sender_username: str
    content: str
    sent_at: datetime

    room_id: int | None = Field(None, description="Room ID for room-wide chat")
    conversation_id: int | None = Field(None, description="Conversation ID for private/group chat")

    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    """
    Schema for creating conversations.
    """

    participant_usernames: list[str] = Field(
        min_length=1,
        max_length=20,
        description="List of usernames to include in conversation",
    )
    conversation_type: str = Field(description="'private' (2 users) or 'group' (2+ users)")


class ConversationResponse(BaseModel):
    """
    Conversation response.
    """

    id: int
    conversation_type: str
    room_id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict()
