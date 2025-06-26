from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository providing common CRUD operations."""

    def __init__(self, db: Session):
        """
        Initialize repository with database session.
        :param db: SQLAlchemy database session
        """
        self.db = db

    @abstractmethod
    def get_by_id(self, id: int) -> Optional[T]:
        """
        Get entity by ID.
        :param id: Entity ID
        :return: Entity or None if not found
        """
        pass

    @abstractmethod
    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """
        Get all entities with pagination.
        :param limit: Maximum number of entities to return
        :param offset: Number of entities to skip
        :return: List of entities
        """
        pass

    @abstractmethod
    def create(self, entity: T) -> T:
        """
        Create new entity
        :param entity: Entity to create
        :return: Created entity with generated ID
        """
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """
        Update existing entity.
        :param entity: Entity to update
        :return: Updated entity
        """
        pass

    @abstractmethod
    def delete(self, id: int) -> bool:
        """
        Delete entity by ID.
        :param id: Entity ID to delete
        :return: True if deleted, False if not found
        """
        pass

    @abstractmethod
    def exists(self, id: int) -> bool:
        """
        Check if entity exists by ID.
        :param id: Entity ID to check
        :return: True if exists, False otherwise
        """
        pass
