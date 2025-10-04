from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ConversationParticipant(Base):
    """
    Junction table managing user/AI participation in conversations.

    Business Rules:
    - Polymorphic: User OR AI entity (XOR)
    - Private conversations: exactly 2 participants
    - Group conversations: 3+ participants
    - Participants can join/leave conversations (temporal participation)
    - Farewell tracking for AI entities
    """

    __tablename__ = "conversation_participants"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Polymorphic: User OR AI (XOR constraint)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    ai_entity_id = Column(
        Integer,
        ForeignKey("ai_entities.id", ondelete="CASCADE"),
        nullable=True,
    )

    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)

    # Farewell tracking for AI (prevents duplicate goodbyes)
    farewell_sent = Column(Boolean, nullable=False, default=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="participants")
    user = relationship("User", back_populates="conversation_participations")
    ai_entity = relationship("AIEntity", back_populates="conversation_participations")

    __table_args__ = (
        CheckConstraint(
            "(user_id IS NULL) != (ai_entity_id IS NULL)",
            name="participant_xor_user_ai",
        ),
        Index("idx_conversation_user", "conversation_id", "user_id"),
        Index("idx_conversation_ai", "conversation_id", "ai_entity_id"),
        Index("idx_user_participation_history", "user_id", "joined_at"),
        Index("idx_active_participants", "conversation_id", "left_at"),
    )

    @property
    def participant_name(self) -> str:
        """Get participant name regardless of User or AI."""
        if self.user_id:
            return self.user.username
        return self.ai_entity.display_name

    @property
    def is_ai(self) -> bool:
        """Check if participant is AI."""
        return self.ai_entity_id is not None

    @property
    def participant_id(self) -> int:
        """Get ID regardless of type."""
        return self.user_id if self.user_id else self.ai_entity_id

    def __repr__(self):
        participant_type = "ai" if self.is_ai else "user"
        return (
            f"<ConversationParticipant(conversation={self.conversation_id}, {participant_type}={self.participant_id})>"
        )
