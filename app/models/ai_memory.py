from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AIMemory(Base):
    """AI conversation memory storage using PostgreSQL JSONB."""

    __tablename__ = "ai_memories"

    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("ai_entities.id", ondelete="CASCADE"), nullable=False)

    # Context linking
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True)

    # Memory data (AI-readable summary + structured JSONB content)
    summary = Column(Text, nullable=False)
    memory_content = Column(JSON().with_variant(JSONB(none_as_null=True), "postgresql"), nullable=False)

    # Retrieval metadata
    keywords = Column(JSON().with_variant(JSONB(none_as_null=True), "postgresql"), nullable=True)
    importance_score = Column(Float, nullable=False, default=1.0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    entity = relationship("AIEntity", back_populates="memories")

    __table_args__ = (
        Index("idx_ai_memory_entity_room", "entity_id", "room_id"),
        Index("idx_ai_memory_keywords", "keywords", postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<AIMemory(id={self.id}, entity_id={self.entity_id})>"
