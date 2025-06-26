from fastapi import APIRouter, Depends, status, Body
from app.core.auth_dependencies import get_current_active_user, get_current_admin_user
from app.models.user import User
from app.schemas.chat_schemas import MessageResponse, MessageCreate
from app.schemas.room_schemas import RoomResponse, RoomCreate
from app.schemas.room_user_schemas import (
    RoomJoinResponse,
    RoomLeaveResponse,
    RoomUsersListResponse,
    UserStatusUpdate,
)
from app.services.room_service import RoomService
from app.services.service_dependencies import get_room_service


router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("/", response_model=list[RoomResponse])
async def get_all_rooms(
    current_user: User = Depends(get_current_active_user),
    room_service: RoomService = Depends(get_room_service),
) -> list[RoomResponse]:
    """
    Get all active rooms.
    :param current_user: Current authenticated user
    :param room_service: Service instance handling room logic
    :return: List of active rooms
    """
    return room_service.get_all_rooms()


@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    room_data: RoomCreate,
    current_admin: User = Depends(get_current_admin_user),
    room_service: RoomService = Depends(get_room_service),
) -> RoomResponse:
    """
    Create a new room.
    :param room_data: Room creation data
    :param current_admin: Current authenticated admin
    :param room_service: Service instance handling room logic
    :return: Created room object
    """
    return room_service.create_room(
        name=room_data.name,
        description=room_data.description,
        max_users=room_data.max_users,
    )


@router.put("/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: int,
    room_data: RoomCreate,
    current_admin: User = Depends(get_current_admin_user),
    room_service: RoomService = Depends(get_room_service),
) -> RoomResponse:
    """
    Update existing room data.
    :param room_id: ID of the room to update
    :param room_data: Room data to update
    :param current_admin: Current authenticated admin
    :param room_service: Service instance handling room logic
    :return: Updated room object
    """
    return room_service.update_room(
        room_id=room_id,
        name=room_data.name,
        description=room_data.description,
        max_users=room_data.max_users,
    )


@router.delete("/{room_id}")
async def delete_room(
    room_id: int,
    current_admin: User = Depends(get_current_admin_user),
    room_service: RoomService = Depends(get_room_service),
) -> dict:
    """
    Close room with cleanup, kick users and archive conversations.
    :param room_id: ID of room to delete
    :param current_admin: Current authenticated admin
    :param room_service: Service instance handling room logic
    :return: Cleanup summary with statistics
    """
    return room_service.delete_room(room_id)


@router.get("/count")
async def get_room_count(
    current_user: User = Depends(get_current_active_user),
    room_service: RoomService = Depends(get_room_service),
) -> dict:
    """
    Get count of active rooms.
    :param current_user: Current authenticated user
    :param room_service: Service instance handling room logic
    :return: Dictionary with room count
    """
    return room_service.get_room_count()


@router.get("/health")
async def rooms_health():
    """Health check"""
    return {"status": "rooms endpoint working"}


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room_by_id(
    room_id: int,
    current_user: User = Depends(get_current_active_user),
    room_service: RoomService = Depends(get_room_service),
) -> RoomResponse:
    """
    Get single room by ID.
    :param room_id: ID of room
    :param current_user: Current authenticated user
    :param room_service: Service instance handling room logic
    :return: Room object
    """
    return room_service.get_room_by_id(room_id)


@router.post("/{room_id}/join", response_model=RoomJoinResponse)
async def join_room(
    room_id: int,
    current_user: User = Depends(get_current_active_user),
    room_service: RoomService = Depends(get_room_service),
) -> RoomJoinResponse:
    """
    User joins room.
    :param room_id: ID of room to join
    :param current_user: Current authenticated user
    :param room_service: Service instance handling room logic
    :return: Join confirmation with room info
    """
    return room_service.join_room(current_user, room_id)


@router.post("/{room_id}/leave", response_model=RoomLeaveResponse)
async def leave_room(
    room_id: int,
    current_user: User = Depends(get_current_active_user),
    room_service: RoomService = Depends(get_room_service),
) -> RoomLeaveResponse:
    """
    User leaves room.
    :param room_id: ID of room to leave
    :param current_user: Current authenticated user
    :param room_service: Service instance handling room logic
    :return: Leave confirmation
    """
    return room_service.leave_room(current_user, room_id)


@router.get("/{room_id}/users", response_model=RoomUsersListResponse)
async def get_room_users(
    room_id: int,
    current_user: User = Depends(get_current_active_user),
    room_service: RoomService = Depends(get_room_service),
) -> RoomUsersListResponse:
    """
    Get list of users currently in a room.
    :param room_id: Room ID
    :param current_user: Current authenticated user
    :param room_service: Service instance handling room logic
    :return: List of users in room
    """
    return room_service.get_room_users(room_id)


@router.patch("/users/status")
async def update_user_status(
    status_update: UserStatusUpdate,
    current_user: User = Depends(get_current_active_user),
    room_service: RoomService = Depends(get_room_service),
) -> dict:
    """
    Update current user status.
    :param status_update: New status data
    :param current_user: Current authenticated user
    :param room_service: Service instance handling room logic
    :return: Status update confirmation
    """
    return room_service.update_user_status(current_user, status_update.status)


@router.post("/{room_id}/messages", response_model=MessageResponse)
async def send_room_message(
    room_id: int,
    message_data: MessageCreate = Body(...),
    current_user: User = Depends(get_current_active_user),
    room_service: RoomService = Depends(get_room_service),
) -> MessageResponse:
    """
    Send message to room, visible for every member.
    :param room_id: Target room ID
    :param message_data: Message content
    :param current_user: Current authenticated user
    :param room_service: Service instance handling room logic
    :return: Created message object
    """
    return room_service.send_room_message(current_user, room_id, message_data.content)


@router.get("/{room_id}/messages", response_model=list[MessageResponse])
async def get_room_messages(
    room_id: int,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_active_user),
    room_service: RoomService = Depends(get_room_service),
) -> list[MessageResponse]:
    """
    Get room message history.
    :param room_id: Room ID to get messages from
    :param page: Page number
    :param page_size: Messages per page
    :param current_user: Current authenticated User
    :param room_service: Service instance handling room logic
    :return: List of room messages
    """
    messages, total_count = room_service.get_room_messages(
        current_user, room_id, page, page_size
    )
    return messages
