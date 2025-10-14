from abc import abstractmethod
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_cooldown import AICooldown

from .base_repository import BaseRepository


class IAICooldownRepository(BaseRepository[AICooldown]):
    """Interface for AI Cooldown repository."""

    @abstractmethod
    async def get_cooldown(
        self,
        ai_entity_id: int,
        room_id: int | None = None,
        conversation_id: int | None = None,
    ) -> AICooldown | None:
        """Get cooldown for specific AI entity in room or conversation."""
        pass

    @abstractmethod
    async def upsert_cooldown(
        self,
        ai_entity_id: int,
        room_id: int | None = None,
        conversation_id: int | None = None,
    ) -> AICooldown:
        """Atomic upsert of cooldown timestamp."""
        pass


class AICooldownRepository(IAICooldownRepository):
    """SQLAlchemy implementation of AI Cooldown repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def get_by_id(self, id: int) -> AICooldown | None:
        query = select(AICooldown).where(AICooldown.id == id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[AICooldown]:
        query = select(AICooldown).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_cooldown(
        self,
        ai_entity_id: int,
        room_id: int | None = None,
        conversation_id: int | None = None,
    ) -> AICooldown | None:
        """Get cooldown for specific AI entity in room or conversation."""
        query = select(AICooldown).where(
            AICooldown.ai_entity_id == ai_entity_id,
            AICooldown.room_id == room_id,
            AICooldown.conversation_id == conversation_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def upsert_cooldown(
        self,
        ai_entity_id: int,
        room_id: int | None = None,
        conversation_id: int | None = None,
    ) -> AICooldown:
        """Atomic upsert of cooldown timestamp."""
        now = datetime.now(timezone.utc)

        # Try to get existing cooldown
        existing = await self.get_cooldown(ai_entity_id, room_id, conversation_id)

        if existing:
            # Update existing
            existing.last_response_at = now
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            # Create new
            cooldown = AICooldown(
                ai_entity_id=ai_entity_id,
                room_id=room_id,
                conversation_id=conversation_id,
                last_response_at=now,
            )
            self.db.add(cooldown)
            await self.db.commit()
            await self.db.refresh(cooldown)
            return cooldown

    async def create(self, cooldown: AICooldown) -> AICooldown:
        self.db.add(cooldown)
        await self.db.commit()
        await self.db.refresh(cooldown)
        return cooldown

    async def update(self, cooldown: AICooldown) -> AICooldown:
        await self.db.commit()
        await self.db.refresh(cooldown)
        return cooldown

    async def delete(self, id: int) -> bool:
        cooldown = await self.get_by_id(id)
        if cooldown:
            await self.db.delete(cooldown)
            await self.db.commit()
            return True
        return False

    async def exists(self, id: int) -> bool:
        cooldown = await self.get_by_id(id)
        return cooldown is not None
