from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

from app.models.user import UserStatus


class RoomUserResponse(BaseModel):
    """
    User information within room context.
    """

    id: int
    username: str
    avatar_url: str | None = None
    status: str = Field(description="User status: available, busy, away")
    last_active: datetime

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


class RoomUsersListResponse(BaseModel):
    """
    List of users currently in a room.
    """

    room_id: int
    room_name: str
    total_users: int
    users: list[RoomUserResponse]


class UserStatusUpdate(BaseModel):
    """
    Schema for updating user status.
    """

    status: UserStatus = Field(description="New user status")
