"""
AI Entity model for LangChain-powered chat agents.

Follows User model pattern with configuration for OpenAI/LangChain integration.
"""

import enum

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.core.constants import DEFAULT_AI_MAX_TOKENS, DEFAULT_AI_MODEL, DEFAULT_AI_TEMPERATURE
from app.core.database import Base


class AIEntityStatus(enum.Enum):
    """AI entity online status."""

    ONLINE = "online"
    OFFLINE = "offline"


class AIResponseStrategy(str, enum.Enum):
    """AI response behavior strategies."""

    ROOM_MENTION_ONLY = "room_mention_only"
    ROOM_PROBABILISTIC = "room_probabilistic"
    ROOM_ACTIVE = "room_active"
    CONV_EVERY_MESSAGE = "conv_every_message"
    CONV_ON_QUESTIONS = "conv_on_questions"
    CONV_SMART = "conv_smart"


class AIEntity(Base):
    """AI entity - equal to User in The Gathering world."""

    __tablename__ = "ai_entities"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # LangChain/OpenAI Configuration
    system_prompt = Column(Text, nullable=False)
    model_name = Column(String(100), nullable=False, default=DEFAULT_AI_MODEL)
    temperature = Column(Float, nullable=False, default=DEFAULT_AI_TEMPERATURE)
    max_tokens = Column(Integer, nullable=False, default=DEFAULT_AI_MAX_TOKENS)

    # Response Strategies
    room_response_strategy = Column(
        Enum(AIResponseStrategy),
        nullable=False,
        default=AIResponseStrategy.ROOM_MENTION_ONLY,
        index=True,
    )
    conversation_response_strategy = Column(
        Enum(AIResponseStrategy),
        nullable=False,
        default=AIResponseStrategy.CONV_ON_QUESTIONS,
        index=True,
    )
    response_probability = Column(
        Float,
        nullable=False,
        default=0.3,
    )

    # Flexible config storage (JSONB for additional LangChain parameters)
    config = Column(JSON().with_variant(JSONB(none_as_null=True), "postgresql"), nullable=True)

    status = Column(
        Enum(AIEntityStatus),
        nullable=False,
        default=AIEntityStatus.OFFLINE,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True, index=True)
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

    # Cooldown Tracking
    cooldowns = relationship(
        "AICooldown",
        back_populates="ai_entity",
        lazy="raise",
        cascade="all, delete-orphan",
    )

    @validates("response_probability")
    def validate_probability(self, key, value):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"response_probability must be 0.0-1.0, got {value}")
        return value

    @validates("temperature")
    def validate_temperature(self, key, value):
        if value is not None and not 0.0 <= value <= 2.0:
            raise ValueError(f"temperature must be 0.0-2.0, got {value}")
        return value

    def __repr__(self):
        return f"<AIEntity(id={self.id}, name='{self.name}')>"
