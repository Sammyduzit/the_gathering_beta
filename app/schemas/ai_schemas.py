from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.constants import MAX_AI_MAX_TOKENS, MAX_AI_TEMPERATURE, MIN_AI_MAX_TOKENS, MIN_AI_TEMPERATURE
from app.core.validators import SanitizedString
from app.models.ai_entity import AIEntityStatus

if TYPE_CHECKING:
    from app.models.ai_entity import AIEntity


class AIEntityCreate(BaseModel):
    """Schema for creating a new AI entity."""

    name: SanitizedString = Field(min_length=1, max_length=100, description="Unique AI identifier")
    display_name: SanitizedString = Field(min_length=1, max_length=100, description="Display name for users")
    system_prompt: str = Field(min_length=1, max_length=5000, description="AI system prompt/instructions")
    model_name: SanitizedString = Field(min_length=1, max_length=100, description="LLM model name")
    temperature: float | None = Field(None, ge=MIN_AI_TEMPERATURE, le=MAX_AI_TEMPERATURE, description="LLM temperature")
    max_tokens: int | None = Field(None, ge=MIN_AI_MAX_TOKENS, le=MAX_AI_MAX_TOKENS, description="Max response tokens")
    config: dict | None = Field(None, description="Additional LangChain configuration")


class AIEntityUpdate(BaseModel):
    """Schema for updating an AI entity."""

    display_name: SanitizedString | None = Field(None, min_length=1, max_length=100)
    system_prompt: str | None = Field(None, min_length=1, max_length=5000)
    model_name: SanitizedString | None = Field(None, min_length=1, max_length=100)
    temperature: float | None = Field(None, ge=MIN_AI_TEMPERATURE, le=MAX_AI_TEMPERATURE)
    max_tokens: int | None = Field(None, ge=MIN_AI_MAX_TOKENS, le=MAX_AI_MAX_TOKENS)
    config: dict | None = None
    status: AIEntityStatus | None = Field(None, description="AI online/offline status")
    current_room_id: int | None = Field(
        None, description="Room assignment (None=leave room, int=assign to room, omit=no change)"
    )


class AIEntityResponse(BaseModel):
    """Schema for AI entity responses."""

    id: int
    name: str
    display_name: str
    system_prompt: str
    model_name: str
    temperature: float | None
    max_tokens: int | None
    config: dict | None
    status: str
    current_room_id: int | None
    current_room_name: str | None  # Populated from AIEntity.current_room_name @property
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AIInviteRequest(BaseModel):
    """Schema for inviting AI to a conversation."""

    ai_entity_id: int = Field(gt=0, description="ID of AI entity to invite")


class AIAvailableResponse(BaseModel):
    """Schema for available AI entities in a room."""

    id: int
    name: str
    display_name: str
    model_name: str
    status: str

    model_config = ConfigDict(from_attributes=True)
