from sqlalchemy import Column, Integer, Index, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


from app.core.database import Base


class ConversationParticipant(Base):
    """
    Junction table managing user participation in conversations.

    Business Rules:
    - Private conversations: exactly 2 participants
    - Group conversations: 3+ participants
    - Users can join/leave conversations (temporal participation)
    - Prevents duplicate participation via unique constraint
    """

    __tablename__ = "conversation_participants"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    joined_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    left_at = Column(DateTime(timezone=True), nullable=True)

    conversation = relationship("Conversation", back_populates="participants")
    user = relationship("User", back_populates="conversation_participations")

    __table_args__ = (
        Index(
            "idx_conversation_user_unique", "conversation_id", "user_id", unique=True
        ),
        Index("idx_user_participation_history", "user_id", "joined_at"),
    )

    def __repr__(self):
        return f"<ConversationParticipant(conversation={self.conversation_id}, user={self.user_id})>"
