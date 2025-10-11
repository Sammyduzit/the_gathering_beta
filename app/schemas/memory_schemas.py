"""Pydantic schemas for AI Memory API requests and responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    """Schema for creating a new AI memory."""

    entity_id: int = Field(gt=0, description="AI entity ID")
    conversation_id: int | None = Field(None, description="Conversation ID (XOR with room_id)")
    room_id: int | None = Field(None, description="Room ID (XOR with conversation_id, unused for now)")
    summary: str = Field(min_length=1, max_length=500, description="Memory summary (1-500 chars)")
    memory_content: dict = Field(description="Structured memory content (participants, topic, etc.)")
    keywords: list[str] | None = Field(None, description="Keywords (auto-extracted if None)")
    importance_score: float = Field(default=1.0, ge=0.0, le=10.0, description="Importance score (0-10)")


class MemoryUpdate(BaseModel):
    """Schema for updating an existing AI memory (partial update)."""

    summary: str | None = Field(None, min_length=1, max_length=500, description="Memory summary")
    memory_content: dict | None = Field(None, description="Structured memory content")
    keywords: list[str] | None = Field(None, description="Keywords (re-extracted if summary changes)")
    importance_score: float | None = Field(None, ge=0.0, le=10.0, description="Importance score")


class MemoryResponse(BaseModel):
    """Schema for AI memory responses."""

    id: int
    entity_id: int
    conversation_id: int | None
    room_id: int | None
    summary: str
    memory_content: dict
    keywords: list[str] | None
    importance_score: float
    embedding: dict | None
    access_count: int
    metadata: dict | None
    created_at: datetime
    last_accessed: datetime

    model_config = ConfigDict(from_attributes=True)


class MemoryListResponse(BaseModel):
    """Schema for paginated memory list responses."""

    memories: list[MemoryResponse]
    total: int = Field(description="Total number of memories")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, le=100, description="Items per page")
    total_pages: int = Field(description="Total number of pages")

    model_config = ConfigDict(from_attributes=True)
