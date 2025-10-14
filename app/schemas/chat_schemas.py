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


class ParticipantInfo(BaseModel):
    """
    Participant information for conversation responses.
    """

    id: int
    username: str
    avatar_url: str | None = None
    status: str
    is_ai: bool

    model_config = ConfigDict(from_attributes=True)


class ConversationPermissions(BaseModel):
    """
    User permissions for a conversation.
    """

    can_post: bool = Field(description="User can send messages")
    can_manage_participants: bool = Field(description="User can add/remove participants")
    can_leave: bool = Field(description="User can leave conversation")


class ConversationListItemResponse(BaseModel):
    """
    Conversation list item response for overview pages.
    Compact format with essential metadata.
    """

    id: int
    type: str = Field(description="Conversation type: private or group")
    room_id: int
    room_name: str | None = Field(None, description="Name of the room this conversation belongs to")
    participants: list[str] = Field(description="List of participant usernames (excluding current user)")
    participant_count: int = Field(description="Total number of participants")
    created_at: datetime
    latest_message_at: datetime | None = Field(None, description="Timestamp of most recent message")
    latest_message_preview: str | None = Field(None, description="Preview of latest message (first 50 chars)")


class ConversationDetailResponse(BaseModel):
    """
    Detailed conversation response for conversation detail pages.
    Includes full participant info, permissions, and message metadata.
    """

    id: int
    type: str = Field(description="Conversation type: private or group")
    room_id: int
    room_name: str | None = Field(None, description="Name of the room this conversation belongs to")
    is_active: bool
    created_at: datetime

    # Participants
    participants: list[ParticipantInfo] = Field(description="Full participant details")
    participant_count: int

    # Message metadata
    message_count: int = Field(description="Total number of messages in conversation")
    latest_message: MessageResponse | None = Field(None, description="Most recent message")

    # Permissions
    permissions: ConversationPermissions = Field(description="Current user's permissions")
