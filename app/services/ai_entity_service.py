import logging

from fastapi import HTTPException, status

from app.models.ai_entity import AIEntity, AIEntityStatus
from app.repositories.ai_entity_repository import IAIEntityRepository
from app.repositories.conversation_repository import IConversationRepository

logger = logging.getLogger(__name__)


class AIEntityService:
    """Service for AI entity business logic using Repository Pattern."""

    def __init__(
        self,
        ai_entity_repo: IAIEntityRepository,
        conversation_repo: IConversationRepository,
    ):
        self.ai_entity_repo = ai_entity_repo
        self.conversation_repo = conversation_repo

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI entity with id {entity_id} not found",
            )
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
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"AI entity with name '{name}' already exists",
            )

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
    ) -> AIEntity:
        """Update AI entity with validation."""
        entity = await self.get_entity_by_id(entity_id)

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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"AI entity '{entity.display_name}' is not online",
            )

        # Validate conversation exists
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation with id {conversation_id} not found",
            )

        # Check if AI is already in this conversation
        existing_ai = await self.ai_entity_repo.get_ai_in_conversation(conversation_id)
        if existing_ai:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"AI entity '{existing_ai.display_name}' is already in this conversation",
            )

        # Add AI to conversation
        try:
            await self.conversation_repo.add_ai_participant(conversation_id, ai_entity_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation with id {conversation_id} not found",
            )

        # Remove AI from conversation
        await self.conversation_repo.remove_ai_participant(conversation_id, ai_entity_id)

        return {
            "message": f"AI entity '{entity.display_name}' removed from conversation",
            "conversation_id": conversation_id,
            "ai_entity_id": ai_entity_id,
        }
