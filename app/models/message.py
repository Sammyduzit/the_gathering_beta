import enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class MessageType(enum.Enum):
    """Message type classification for system vs user messages."""

    TEXT = "text"
    SYSTEM = "system"


class Message(Base):
    """
    Universal message model supporting 3-type chat system.

    Business Rules:
    - XOR Constraint: Message belongs to EITHER room OR conversation (never both)
    - Room messages: Public, all room members can see
    - Conversation messages: Private/group, only participants can see
    - System messages: Automated notifications (join/leave events)

    Routing Logic:
    - room_id set, conversation_id NULL → Room-wide chat
    - conversation_id set, room_id NULL → Private/group chat
    - Both set or both NULL → Constraint violation
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(Enum(MessageType), nullable=False, default=MessageType.TEXT)
    sent_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True)

    sender = relationship("User", back_populates="sent_messages")
    room = relationship("Room", back_populates="room_messages")
    conversation = relationship("Conversation", back_populates="messages")

    translations = relationship("MessageTranslation", back_populates="message", lazy="dynamic")

    __table_args__ = (
        CheckConstraint(
            "(room_id is NULL) != (conversation_id IS NULL)",
            name="message_xor_room_conversation",
        ),
        Index("idx_conversation_messages", "conversation_id", "sent_at"),
        Index("idx_room_messages", "room_id", "sent_at"),
        Index("idx_user_messages", "sender_id", "sent_at"),
    )

    def __repr__(self):
        """
        String representation of message.
        :return: Formatted message info
        """
        target = f"room={self.room_id}" if self.room_id else f"conversation={self.conversation_id}"
        return f"<Message(id={self.id}, {target}, sender={self.sender_id})>"

    @property
    def is_room_message(self):
        """
        Check if message is for room-wide chat.
        :return: True if room message, False if conversation message
        """
        return self.room_id is not None

    @property
    def is_conversation_message(self):
        """
        Check if message is for private/group conversation.
        :return: True if conversation message, False if room message
        """
        return self.conversation_id is not None

    @property
    def chat_target(self):
        """
        Get the target of this message (room or conversation ID).
        :return: Dictionary with target type and ID
        """
        if self.is_room_message:
            return {"type": "room", "id": self.room_id}
        else:
            return {"type": "conversation", "id": self.conversation_id}
