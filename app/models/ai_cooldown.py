"""AI Cooldown Model - Separate table for performance & atomicity."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AICooldown(Base):
    """AI Cooldown tracking for rate limiting."""

    __tablename__ = "ai_cooldowns"

    id = Column(Integer, primary_key=True)

    ai_entity_id = Column(
        Integer,
        ForeignKey("ai_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Context: EITHER Room OR Conversation (XOR enforced by unique constraint)
    room_id = Column(
        Integer,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    last_response_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Relationships
    ai_entity = relationship("AIEntity", back_populates="cooldowns")
    room = relationship("Room")
    conversation = relationship("Conversation")

    __table_args__ = (
        UniqueConstraint(
            "ai_entity_id",
            "room_id",
            "conversation_id",
            name="uq_ai_cooldown_context",
        ),
    )

    def __repr__(self):
        context = f"room={self.room_id}" if self.room_id else f"conv={self.conversation_id}"
        return f"<AICooldown(ai={self.ai_entity_id}, {context}, last={self.last_response_at})>"
