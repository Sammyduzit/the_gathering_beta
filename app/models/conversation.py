import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ConversationType(enum.Enum):
    """Conversation types"""

    PRIVATE = "private"
    GROUP = "group"


class Conversation(Base):
    """Conversation Model"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=False)
    conversation_type = Column(Enum(ConversationType), nullable=False, default=ConversationType.PRIVATE)
    max_participants = Column(Integer, nullable=True)  # 2 for private, NULL for group chat

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    room = relationship("Room", back_populates="conversations")
    participants = relationship("ConversationParticipant", back_populates="conversation")
    messages = relationship("Message", back_populates="conversation", lazy="dynamic")

    def __repr__(self):
        return f"<Conversation(id={self.id}, type={self.conversation_type}, room_id={self.room_id})>"
