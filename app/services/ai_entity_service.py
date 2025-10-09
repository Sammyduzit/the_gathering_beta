import structlog

from app.core.exceptions import (
    AIEntityNotFoundException,
    AIEntityOfflineException,
    ConversationNotFoundException,
    DuplicateResourceException,
    InvalidOperationException,
    RoomNotFoundException,
)
from app.models.ai_entity import AIEntity, AIEntityStatus
from app.repositories.ai_cooldown_repository import IAICooldownRepository
from app.repositories.ai_entity_repository import IAIEntityRepository
from app.repositories.conversation_repository import IConversationRepository
from app.repositories.room_repository import IRoomRepository

logger = structlog.get_logger(__name__)


class AIEntityService:
    """Service for AI entity business logic using Repository Pattern."""

    def __init__(
        self,
        ai_entity_repo: IAIEntityRepository,
        conversation_repo: IConversationRepository,
        cooldown_repo: IAICooldownRepository,
        room_repo: IRoomRepository,
    ):
        self.ai_entity_repo = ai_entity_repo
        self.conversation_repo = conversation_repo
        self.cooldown_repo = cooldown_repo
        self.room_repo = room_repo

    async def get_all_entities(self) -> list[AIEntity]:
        """Get all AI entities."""
        return await self.ai_entity_repo.get_all()

    async def get_available_entities(self) -> list[AIEntity]:
        """Get all available AI entities (online and not deleted)."""
        return await self.ai_entity_repo.get_available_entities()

    async def get_entity_by_id(self, entity_id: int) -> AIEntity:
        """Get AI entity by ID with validation."""
        entity = await self.ai_entity_repo.get_by_id(entity_id)
        if not entity:
            raise AIEntityNotFoundException(entity_id)
        return entity

    async def create_entity(
        self,
        name: str,
        display_name: str,
        system_prompt: str,
        model_name: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        config: dict | None = None,
    ) -> AIEntity:
        """Create new AI entity with validation."""
        if await self.ai_entity_repo.name_exists(name):
            raise DuplicateResourceException("AI entity", name)

        new_entity = AIEntity(
            name=name,
            display_name=display_name,
            system_prompt=system_prompt,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            config=config,
            status=AIEntityStatus.OFFLINE,
        )

        return await self.ai_entity_repo.create(new_entity)

    async def update_entity(
        self,
        entity_id: int,
        display_name: str | None = None,
        system_prompt: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        config: dict | None = None,
        status: AIEntityStatus | None = None,
        current_room_id: int | None = ...,  # ... as sentinel: not provided
    ) -> AIEntity:
        """Update AI entity with validation and room assignment.

        Args:
            status: If set to OFFLINE, AI will automatically leave current room
            current_room_id: Room assignment (None = leave room, int = assign to room, ... = no change)
        """
        entity = await self.get_entity_by_id(entity_id)

        # Handle status change (auto-leave room if set to OFFLINE)
        if status is not None and status != entity.status:
            if status == AIEntityStatus.OFFLINE and entity.current_room_id:
                await self._remove_from_room(entity)
            entity.status = status

        # Handle room assignment if explicitly provided
        if current_room_id is not ...:
            if current_room_id is None:
                # Remove from current room
                if entity.current_room_id:
                    await self._remove_from_room(entity)
            else:
                # Assign to new room
                await self._assign_to_room(entity, current_room_id)

        # Update other fields
        if display_name is not None:
            entity.display_name = display_name
        if system_prompt is not None:
            entity.system_prompt = system_prompt
        if model_name is not None:
            entity.model_name = model_name
        if temperature is not None:
            entity.temperature = temperature
        if max_tokens is not None:
            entity.max_tokens = max_tokens
        if config is not None:
            entity.config = config

        return await self.ai_entity_repo.update(entity)

    async def delete_entity(self, entity_id: int) -> dict:
        """Soft delete AI entity (set to OFFLINE)."""
        entity = await self.get_entity_by_id(entity_id)

        await self.ai_entity_repo.delete(entity_id)

        return {
            "message": f"AI entity '{entity.display_name}' has been deleted",
            "entity_id": entity_id,
        }

    async def get_available_in_room(self, room_id: int) -> list[AIEntity]:
        """Get AI entities available in a room (active and not in conversation)."""
        return await self.ai_entity_repo.get_available_in_room(room_id)

    async def invite_to_conversation(self, conversation_id: int, ai_entity_id: int) -> dict:
        """Invite AI entity to a conversation."""
        # Validate AI entity exists and is active
        entity = await self.get_entity_by_id(ai_entity_id)
        if entity.status != AIEntityStatus.ONLINE:
            raise AIEntityOfflineException(entity.display_name)

        # Validate conversation exists
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundException(conversation_id)

        # Check if AI is already in this conversation
        existing_ai = await self.ai_entity_repo.get_ai_in_conversation(conversation_id)
        if existing_ai:
            raise InvalidOperationException(
                f"AI entity '{existing_ai.display_name}' is already in this conversation"
            )

        # Add AI to conversation
        try:
            await self.conversation_repo.add_ai_participant(conversation_id, ai_entity_id)
        except ValueError as e:
            raise InvalidOperationException(str(e))

        return {
            "message": f"AI entity '{entity.display_name}' invited to conversation",
            "conversation_id": conversation_id,
            "ai_entity_id": ai_entity_id,
        }

    async def remove_from_conversation(self, conversation_id: int, ai_entity_id: int) -> dict:
        """Remove AI entity from a conversation."""
        # Validate AI entity exists
        entity = await self.get_entity_by_id(ai_entity_id)

        # Validate conversation exists
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundException(conversation_id)

        # Remove AI from conversation
        await self.conversation_repo.remove_ai_participant(conversation_id, ai_entity_id)

        return {
            "message": f"AI entity '{entity.display_name}' removed from conversation",
            "conversation_id": conversation_id,
            "ai_entity_id": ai_entity_id,
        }

    async def update_cooldown(
        self,
        ai_entity_id: int,
        room_id: int | None = None,
        conversation_id: int | None = None,
    ) -> None:
        """Update AI entity cooldown for rate limiting."""
        await self.cooldown_repo.upsert_cooldown(
            ai_entity_id=ai_entity_id,
            room_id=room_id,
            conversation_id=conversation_id,
        )

    async def _assign_to_room(self, entity: AIEntity, new_room_id: int) -> None:
        """Assign AI entity to a room with validation.

        Args:
            entity: AI entity to assign
            new_room_id: Target room ID

        Raises:
            RoomNotFoundException: If room doesn't exist
            InvalidOperationException: If room already has AI or AI is offline
        """
        # Validate new room exists
        new_room = await self.room_repo.get_by_id(new_room_id)
        if not new_room:
            raise RoomNotFoundException(new_room_id)

        # Check if new room already has AI
        if new_room.has_ai:
            raise InvalidOperationException(f"Room '{new_room.name}' already has an AI entity")

        # Check AI is ONLINE before joining
        if entity.status != AIEntityStatus.ONLINE:
            raise InvalidOperationException(
                f"AI entity '{entity.display_name}' must be ONLINE to join a room"
            )

        # Remove from old room if present
        if entity.current_room_id:
            old_room = await self.room_repo.get_by_id(entity.current_room_id)
            if old_room:
                old_room.has_ai = False

        # Assign to new room
        new_room.has_ai = True
        entity.current_room_id = new_room_id

        logger.info(
            "ai_assigned_to_room",
            ai_entity_id=entity.id,
            ai_name=entity.display_name,
            room_id=new_room_id,
            room_name=new_room.name,
        )

    async def _remove_from_room(self, entity: AIEntity) -> None:
        """Remove AI entity from current room.

        Args:
            entity: AI entity to remove from room
        """
        if not entity.current_room_id:
            return  # Already not in a room

        # Get current room and update has_ai flag
        room = await self.room_repo.get_by_id(entity.current_room_id)
        if room:
            room.has_ai = False

        logger.info(
            "ai_removed_from_room",
            ai_entity_id=entity.id,
            ai_name=entity.display_name,
            room_id=entity.current_room_id,
            room_name=room.name if room else "unknown",
        )

        # Clear room assignment
        entity.current_room_id = None
