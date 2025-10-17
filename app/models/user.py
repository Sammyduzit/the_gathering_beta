import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UserStatus(enum.Enum):
    """User presence status"""

    AVAILABLE = "available"
    BUSY = "busy"
    AWAY = "away"


class User(Base):
    """User model"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    avatar_url = Column(String(500), nullable=True)
    preferred_language = Column(String(5), nullable=True, default="en")
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.AVAILABLE)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), server_default=func.now())
    is_admin = Column(Boolean, nullable=False, default=False)

    current_room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    current_room = relationship("Room", back_populates="users")
    conversation_participations = relationship("ConversationParticipant", back_populates="user")
    sent_messages = relationship(
        "Message",
        back_populates="sender_user",
        foreign_keys="Message.sender_user_id",
        lazy="raise",
    )

    def __repr__(self):
        return f"<User (id={self.id}, username='{self.username}')>"
