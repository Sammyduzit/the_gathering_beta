from pgvector.sqlalchemy import Vector
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
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    # Context linking
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True)

    # Memory data (AI-readable summary + structured JSONB content)
    summary = Column(Text, nullable=False)
    memory_content = Column(JSON().with_variant(JSONB(none_as_null=True), "postgresql"), nullable=False)

    # Retrieval metadata
    keywords = Column(JSON().with_variant(JSONB(none_as_null=True), "postgresql"), nullable=True)
    importance_score = Column(Float, nullable=False, default=1.0)

    # Vector search support (pgvector for semantic search)
    embedding = Column(Vector(1536), nullable=True)

    # Access tracking for importance adjustment
    access_count = Column(Integer, nullable=False, default=0)

    # Flexible metadata (extractor version, creation method, etc.)
    memory_metadata = Column(
        JSON().with_variant(JSONB(none_as_null=True), "postgresql"),
        nullable=True,
        comment="Stores extractor_used, summarizer_used, version, confidence_score, etc.",
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    entity = relationship("AIEntity", back_populates="memories")

    __table_args__ = (
        Index("idx_ai_memory_entity_room", "entity_id", "room_id"),
        Index("idx_ai_memory_keywords", "keywords", postgresql_using="gin"),
        Index("idx_ai_memory_access_count", "access_count"),
        Index("ai_memories_user_type_conv_idx", "user_id", "memory_metadata", "conversation_id"),
        Index("ai_memories_entity_user_idx", "entity_id", "user_id"),
        Index("ai_memories_created_at_idx", "created_at"),
        Index("ai_memories_embedding_idx", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}),
    )

    def __repr__(self):
        return f"<AIMemory(id={self.id}, entity_id={self.entity_id})>"
