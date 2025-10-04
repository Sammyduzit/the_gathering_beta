from abc import abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_entity import AIEntity, AIEntityStatus

from .base_repository import BaseRepository


class IAIEntityRepository(BaseRepository[AIEntity]):
    """Interface for AI Entity repository."""

    @abstractmethod
    async def get_by_name(self, name: str) -> AIEntity | None:
        """Get AI entity by unique name."""
        pass

    @abstractmethod
    async def get_active_entities(self) -> list[AIEntity]:
        """Get all active AI entities."""
        pass

    @abstractmethod
    async def name_exists(self, name: str, exclude_id: int | None = None) -> bool:
        """Check if name exists (for validation)."""
        pass


class AIEntityRepository(IAIEntityRepository):
    """SQLAlchemy implementation of AI Entity repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def get_by_id(self, id: int) -> AIEntity | None:
        query = select(AIEntity).where(AIEntity.id == id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> AIEntity | None:
        query = select(AIEntity).where(AIEntity.name == name)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[AIEntity]:
        query = select(AIEntity).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_entities(self) -> list[AIEntity]:
        query = select(AIEntity).where(AIEntity.status == AIEntityStatus.ACTIVE)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, entity: AIEntity) -> AIEntity:
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)
        return entity

    async def update(self, entity: AIEntity) -> AIEntity:
        await self.db.commit()
        await self.db.refresh(entity)
        return entity

    async def delete(self, id: int) -> bool:
        """Soft delete - set offline."""
        entity = await self.get_by_id(id)
        if entity:
            entity.status = AIEntityStatus.OFFLINE
            await self.db.commit()
            return True
        return False

    async def exists(self, id: int) -> bool:
        entity = await self.get_by_id(id)
        return entity is not None

    async def name_exists(self, name: str, exclude_id: int | None = None) -> bool:
        query = select(AIEntity).where(AIEntity.name == name)
        if exclude_id:
            query = query.where(AIEntity.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
