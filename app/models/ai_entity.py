"""
AI Entity model for LangChain-powered chat agents.

Follows User model pattern with configuration for OpenAI/LangChain integration.
"""

import enum

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AIEntityStatus(enum.Enum):
    """AI entity status."""

    ACTIVE = "active"  # Can be invited to conversations
    OFFLINE = "offline"  # Admin deactivated


class AIEntity(Base):
    """
    AI entity configuration for LangChain-powered chat agents.

    Similar to User model structure - represents a single AI personality/agent that can:
    - Join rooms and respond to messages
    - Maintain conversation memory
    - Have configurable personality/behavior via system prompts
    """

    __tablename__ = "ai_entities"

    # Primary fields (same pattern as User model)
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

    # Status fields (same pattern as User/Room models)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships (async-safe: lazy="raise" prevents accidental lazy loading in async context)
    memories = relationship("AIMemory", back_populates="entity", lazy="raise")

    def __repr__(self):
        return f"<AIEntity(id={self.id}, name='{self.name}')>"
