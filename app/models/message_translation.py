from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class MessageTranslation(Base):
    """Translation storage for messages in different languages"""
    __tablename__ = "message_translation"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    target_language = Column(String(5), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    message = relationship("Message", back_populates="translations")

    __table_args__ = (
        Index(
            "idx_message_language_unique",
            "message_id",
            "target_language",
            unique=True
        ),
        Index("idx_message_translations", "message_id"),
        Index("idx_language_translations", "target_language"),
    )

    def __repr__(self):
        return f"<MessageTranslation(message_id={self.message_id}, lang={self.target_language}>"