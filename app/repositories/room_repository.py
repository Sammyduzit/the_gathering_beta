from abc import abstractmethod
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from app.models.room import Room
from app.models.user import User
from app.repositories.base_repository import BaseRepository


class IRoomRepository(BaseRepository[Room]):
    """Abstract interface for Room repository."""

    @abstractmethod
    def get_active_rooms(self) -> List[Room]:
        """Get all active rooms."""
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Room]:
        """Get room by name."""
        pass

    @abstractmethod
    def name_exists(self, name: str, exclude_room_id: Optional[int] = None) -> bool:
        """Check if room name already exists."""
        pass

    @abstractmethod
    def get_user_count(self, room_id: int) -> int:
        """Get count of users currently in room."""
        pass

    @abstractmethod
    def get_users_in_room(self, room_id: int) -> List[User]:
        """Get all users currently in a specific room."""
        pass

    @abstractmethod
    def soft_delete(self, room_id: int) -> bool:
        """Soft delete room (set inactive)."""
        pass


class RoomRepository(IRoomRepository):
    """SQLAlchemy implementation of Room repository."""

    def __init__(self, db: Session):
        """
        Initialize with database session.
        :param db: SQLAlchemy database session
        """
        super().__init__(db)

    def get_by_id(self, id: int) -> Optional[Room]:
        """Get room by ID."""
        query = select(Room).where(and_(Room.id == id, Room.is_active.is_(True)))
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_active_rooms(self) -> List[Room]:
        """Get all active rooms."""
        query = select(Room).where(Room.is_active.is_(True))
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_by_name(self, name: str) -> Optional[Room]:
        """Get room by name."""
        query = select(Room).where(and_(Room.name == name, Room.is_active.is_(True)))
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def name_exists(self, name: str, exclude_room_id: Optional[int] = None) -> bool:
        """Check if room name already exists."""
        query = select(Room).where(and_(Room.name == name, Room.is_active.is_(True)))

        if exclude_room_id:
            query = query.where(Room.id != exclude_room_id)

        result = self.db.execute(query)
        existing_room = result.scalar_one_or_none()
        return existing_room is not None

    def get_user_count(self, room_id: int) -> int:
        """Get count of users currently in room."""
        user_count_query = select(func.count(User.id)).where(
            User.current_room_id == room_id
        )
        result = self.db.execute(user_count_query)
        return result.scalar() or 0

    def get_users_in_room(self, room_id: int) -> List[User]:
        """Get all users currently in a specific room."""
        query = (
            select(User)
            .where(and_(User.current_room_id == room_id, User.is_active.is_(True)))
            .order_by(User.username)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Room]:
        """Get all rooms with pagination."""
        query = select(Room).limit(limit).offset(offset)
        result = self.db.execute(query)
        return list(result.scalars().all())

    def create(self, room: Room) -> Room:
        """Create new room."""
        self.db.add(room)
        self.db.commit()
        self.db.refresh(room)
        return room

    def update(self, room: Room) -> Room:
        """Update existing room."""
        self.db.commit()
        self.db.refresh(room)
        return room

    def delete(self, id: int) -> bool:
        """Hard delete room by ID."""
        room = self.get_by_id(id)
        if room:
            self.db.delete(room)
            self.db.commit()
            return True
        return False

    def soft_delete(self, room_id: int) -> bool:
        """Soft delete room (set inactive)."""
        room = self.get_by_id(room_id)
        if room:
            room.is_active = False
            self.db.commit()
            return True
        return False

    def exists(self, id: int) -> bool:
        """Check if room exists by ID."""
        room = self.get_by_id(id)
        return room is not None
