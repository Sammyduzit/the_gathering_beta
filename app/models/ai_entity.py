"""
AI Entity model for LangChain-powered chat agents.

Follows User model pattern with configuration for OpenAI/LangChain integration.
"""

import enum

from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AIEntityStatus(enum.Enum):
    """AI entity status."""

    ACTIVE = "active"
    OFFLINE = "offline"


class AIEntity(Base):
    """AI entity - equal to User in The Gathering world."""

    __tablename__ = "ai_entities"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # LangChain/OpenAI Configuration
    system_prompt = Column(Text, nullable=False)
    model_name = Column(String(100), nullable=False, default="gpt-4")
    temperature = Column(Float, nullable=False, default=0.7)
    max_tokens = Column(Integer, nullable=False, default=1024)

    # Flexible config storage (JSONB for additional LangChain parameters)
    config = Column(JSON().with_variant(JSONB(none_as_null=True), "postgresql"), nullable=True)

    status = Column(
        Enum(AIEntityStatus),
        nullable=False,
        default=AIEntityStatus.OFFLINE,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Room presence
    current_room_id = Column(
        Integer,
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    current_room = relationship("Room", back_populates="ai_entities")
    memories = relationship("AIMemory", back_populates="entity", lazy="raise")
    sent_messages = relationship(
        "Message",
        back_populates="sender_ai",
        foreign_keys="Message.sender_ai_id",
        lazy="raise",
    )
    conversation_participations = relationship(
        "ConversationParticipant",
        back_populates="ai_entity",
        foreign_keys="ConversationParticipant.ai_entity_id",
        lazy="raise",
    )

    def __repr__(self):
        return f"<AIEntity(id={self.id}, name='{self.name}')>"
