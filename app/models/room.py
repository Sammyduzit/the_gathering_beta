from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Room(Base):
    """Room model"""

    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    max_users = Column(Integer, nullable=True)

    is_translation_enabled = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="current_room")
    ai_entities = relationship("AIEntity", back_populates="current_room", lazy="raise")
    conversations = relationship("Conversation", back_populates="room")
    room_messages = relationship("Message", back_populates="room", lazy="dynamic")

    def __repr__(self):
        return f"<Room(id={self.id}, name='{self.name}')>"
