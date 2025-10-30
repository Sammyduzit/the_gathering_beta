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

from app.core.constants import ONDELETE_CASCADE, ONDELETE_RESTRICT, ONDELETE_SET_NULL
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
    - XOR Constraint: Sender is EITHER user OR AI entity (never both)
    - Room messages: Public, all room members can see
    - Conversation messages: Private/group, only participants can see
    - System messages: Automated notifications (join/leave events)
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)

    # Polymorphic sender (User XOR AI)
    sender_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete=ONDELETE_SET_NULL),
        nullable=True,
    )
    sender_ai_id = Column(
        Integer,
        ForeignKey("ai_entities.id", ondelete=ONDELETE_SET_NULL),
        nullable=True,
    )

    content = Column(Text, nullable=False)
    message_type = Column(Enum(MessageType), nullable=False, default=MessageType.TEXT)
    sent_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    room_id = Column(Integer, ForeignKey("rooms.id", ondelete=ONDELETE_SET_NULL), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete=ONDELETE_CASCADE), nullable=True)

    # Threading Support (Reply-To)
    in_reply_to_message_id = Column(
        Integer,
        ForeignKey("messages.id", ondelete=ONDELETE_RESTRICT),
        nullable=True,
        index=True,
    )

    # Polymorphic relationships
    sender_user = relationship(
        "User",
        back_populates="sent_messages",
        foreign_keys=[sender_user_id],
        lazy="raise",
    )
    sender_ai = relationship(
        "AIEntity",
        back_populates="sent_messages",
        foreign_keys=[sender_ai_id],
        lazy="raise",
    )

    room = relationship("Room", back_populates="room_messages")
    conversation = relationship("Conversation", back_populates="messages")
    translations = relationship("MessageTranslation", back_populates="message", lazy="dynamic")

    # Self-Referential Relationship for Threading
    in_reply_to = relationship(
        "Message",
        remote_side=[id],
        backref="replies",
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint(
            "(room_id is NULL) != (conversation_id IS NULL)",
            name="message_xor_room_conversation",
        ),
        CheckConstraint(
            "(sender_user_id IS NULL) != (sender_ai_id IS NULL)",
            name="message_xor_sender_user_ai",
        ),
        Index("idx_conversation_messages", "conversation_id", "sent_at"),
        Index("idx_room_messages", "room_id", "sent_at"),
        Index("idx_user_messages", "sender_user_id", "sent_at"),
        Index("idx_ai_messages", "sender_ai_id", "sent_at"),
        Index("idx_reply_to_message", "in_reply_to_message_id"),
    )

    @property
    def sender_id(self) -> int:
        """Get sender ID regardless of type (User or AI)."""
        return self.sender_user_id if self.sender_user_id else self.sender_ai_id

    @property
    def sender_username(self) -> str:
        """Get sender username regardless of type (user.username or ai.display_name)."""
        if self.sender_user_id:
            return self.sender_user.username
        return self.sender_ai.display_name

    @property
    def is_from_ai(self) -> bool:
        """Check if message is from AI entity."""
        return self.sender_ai_id is not None

    @property
    def is_room_message(self):
        """Check if message is for room-wide chat."""
        return self.room_id is not None

    @property
    def is_conversation_message(self):
        """Check if message is for private/group conversation."""
        return self.conversation_id is not None

    @property
    def chat_target(self):
        """Get the target of this message (room or conversation ID)."""
        if self.is_room_message:
            return {"type": "room", "id": self.room_id}
        return {"type": "conversation", "id": self.conversation_id}

    def __repr__(self):
        target = f"room={self.room_id}" if self.room_id else f"conversation={self.conversation_id}"
        sender_type = "ai" if self.is_from_ai else "user"
        return f"<Message(id={self.id}, {target}, sender={sender_type}:{self.sender_id})>"
