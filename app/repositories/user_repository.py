from abc import abstractmethod
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.models.user import User
from .base_repository import BaseRepository


class IUserRepository(BaseRepository[User]):
    """Abstract interface for User repository."""

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        pass

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        pass

    @abstractmethod
    def get_active_users(self) -> List[User]:
        """Get all active users."""
        pass

    @abstractmethod
    def get_users_in_room(self, room_id: int) -> List[User]:
        """Get all users currently in a specific room."""
        pass

    @abstractmethod
    def email_exists(self, email: str) -> bool:
        """Check if email already exists."""
        pass

    @abstractmethod
    def username_exists(self, username: str) -> bool:
        """Check if username already exists."""
        pass


class UserRepository(IUserRepository):
    """SQLAlchemy implementation of User repository."""

    def __init__(self, db: Session):
        """
        Initialize with database session.
        :param db: SQLAlchemy database session
        """
        super().__init__(db)

    def get_by_id(self, id: int) -> Optional[User]:
        """Get user by ID."""
        query = select(User).where(User.id == id)
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        query = select(User).where(User.email == email)
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        query = select(User).where(User.username == username)
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Get all users with pagination."""
        query = select(User).limit(limit).offset(offset)
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_active_users(self) -> List[User]:
        """Get all active users."""
        query = select(User).where(User.is_active.is_(True))
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_users_in_room(self, room_id: int) -> List[User]:
        """Get all users currently in a specific room."""
        query = select(User).where(
            and_(User.current_room_id == room_id, User.is_active.is_(True))
        )
        result = self.db.execute(query)
        return list(result.scalars().all())

    def create(self, user: User) -> User:
        """Create new user."""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: User) -> User:
        """Update existing user."""
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, id: int) -> bool:
        """Delete user by ID (soft delete - set inactive)."""
        user = self.get_by_id(id)
        if user:
            user.is_active = False
            self.db.commit()
            return True
        return False

    def exists(self, id: int) -> bool:
        """Check if user exists by ID."""
        user = self.get_by_id(id)
        return user is not None

    def email_exists(self, email: str) -> bool:
        """Check if email already exists."""
        user = self.get_by_email(email)
        return user is not None

    def username_exists(self, username: str) -> bool:
        """Check if username already exists."""
        user = self.get_by_username(username)
        return user is not None
