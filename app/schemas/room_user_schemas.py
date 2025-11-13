from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserStatus


class RoomParticipantResponse(BaseModel):
    """
    Unified participant (human user or AI entity) in room context.
    Consistent with ConversationDetailResponse.participants structure.
    """

    id: int
    username: str = Field(description="Unique username for both humans and AI entities")
    avatar_url: str | None = Field(None, description="Avatar URL, null for AI entities")
    status: str = Field(description="Participant status: available/busy/away for humans, online for AI")
    is_ai: bool = Field(description="True if participant is an AI entity")
    last_active: datetime | None = Field(None, description="Last activity timestamp, null for AI entities")

    model_config = ConfigDict(from_attributes=True)


class RoomJoinResponse(BaseModel):
    """
    Response when user joins room.
    """

    message: str = Field(description="Success message")
    room_id: int = Field(description="ID of joined room")
    room_name: str = Field(description="Name of joined room")
    user_count: int = Field(description="Total users currently in room")


class RoomLeaveResponse(BaseModel):
    """
    Response when user leaves room.
    """

    message: str = Field(description="Success message")
    room_id: int = Field(description="ID of left room")
    room_name: str = Field(description="Name of left room")


class RoomParticipantsResponse(BaseModel):
    """
    All participants (humans + AI) currently in a room.
    Unified response including both human users and AI entities.
    """

    room_id: int
    room_name: str
    total_participants: int = Field(description="Total count of all participants (humans + AI)")
    participants: list[RoomParticipantResponse] = Field(description="Unified list of all room participants")


class UserStatusUpdate(BaseModel):
    """
    Schema for updating user status.
    """

    status: UserStatus = Field(description="New user status")
